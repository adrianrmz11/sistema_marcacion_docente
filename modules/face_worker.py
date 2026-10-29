import threading
import time
import logging

from modules.db_connection import get_cursor
from modules.face_service import verify_face

logger = logging.getLogger(__name__)

_POLL_INTERVAL = 5  # segundos entre polls cuando la cola está vacía


def _reset_stale_processing():
    """Al arrancar, vuelve al estado pendiente cualquier registro que quedó en PROCESANDO
    por un reinicio abrupto del servidor."""
    try:
        cursor = get_cursor()
        cursor.execute(
            "UPDATE marcacion_docente SET estado = 'PENDIENTE' "
            "WHERE estado = 'PROCESANDO'"
        )
        cursor.commit()
        cursor.close()
    except Exception:
        logger.exception("No se pudo limpiar registros PROCESANDO al arrancar")


def _worker_loop():
    _reset_stale_processing()
    logger.info("Worker de verificación facial listo")

    while True:
        try:
            # Reclama atómicamente un registro pendiente para evitar doble procesamiento
            cursor = get_cursor()
            cursor.execute("""
                UPDATE TOP(1) marcacion_docente
                SET estado = 'PROCESANDO'
                OUTPUT INSERTED.cmarcacion, INSERTED.cprofesor
                WHERE estado = 'PENDIENTE'
            """)
            row = cursor.fetchone()
            cursor.commit()
            cursor.close()

            if row is None:
                time.sleep(_POLL_INTERVAL)
                continue

            cmarcacion, cprofesor = row[0], row[1]

            # Lee la foto en una consulta separada (VARBINARY puede ser grande)
            cursor = get_cursor()
            cursor.execute(
                "SELECT tfoto FROM marcacion_docente WHERE cmarcacion = ?",
                (cmarcacion,),
            )
            photo_row = cursor.fetchone()
            cursor.close()

            tfoto = bytes(photo_row[0]) if photo_row and photo_row[0] else None

            try:
                estado, mensaje = verify_face(tfoto, cprofesor)
            except Exception:
                logger.exception("verify_face falló para marcación %s", cmarcacion)
                estado = 'PENDIENTE'
                mensaje = 'Error interno durante verificación, reintentando'

            cursor = get_cursor()
            cursor.execute(
                "UPDATE marcacion_docente SET estado = ?, mensaje_procesado = ? "
                "WHERE cmarcacion = ?",
                (estado, mensaje, cmarcacion),
            )
            cursor.commit()
            cursor.close()

            logger.info("Marcación %s → %s | %s", cmarcacion, estado, mensaje)

        except Exception:
            logger.exception("Error en el loop del worker facial")
            time.sleep(_POLL_INTERVAL)


def start_face_worker():
    t = threading.Thread(target=_worker_loop, daemon=True, name="face-worker")
    t.start()
