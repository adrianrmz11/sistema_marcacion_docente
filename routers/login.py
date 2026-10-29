from flask import Blueprint, jsonify, redirect, render_template, request, url_for
from modules.db_connection import get_cursor
import base64
import numpy as np
import tempfile
import os
from math import radians, sin, cos, sqrt, atan2
import cv2
from deepface import DeepFace

login_bp = Blueprint('login', __name__)


@login_bp.route('/api/verificar-paso1', methods=['POST'])
def verificar_paso1():
    """
    Valida credenciales del docente y verifica si ya completó entrada y salida
    aprobadas hoy. Responde JSON {ok, error} sin registrar ninguna marcación.
    """
    codigo = (request.form.get('codigo') or '').strip()
    clave  = request.form.get('clave') or ''

    if not codigo or not clave:
        return jsonify({'ok': False, 'error': 'Ingrese código y clave.'})

    cursor = get_cursor()
    try:
        cursor.execute(
            "SELECT a.cprofesor FROM profesor a "
            "INNER JOIN persona b ON a.cpersona = b.cpersona "
            "WHERE a.cprofesor = ? AND b.tclave_sil = ?",
            (codigo, clave),
        )
        docente = cursor.fetchone()

        if docente is None:
            return jsonify({'ok': False, 'error': 'Código o clave incorrectos.'})

        cursor.execute(
            "SELECT COUNT(*) FROM marcacion_docente "
            "WHERE cprofesor = ? "
            "AND CONVERT(date, fecha) = CONVERT(date, GETDATE()) "
            "AND estado = 'APROBADO'",
            (docente[0],),
        )
        aprobadas = cursor.fetchone()[0]

        if aprobadas >= 2:
            return jsonify({
                'ok': False,
                'error': 'Ya completó sus dos marcaciones del día (entrada y salida).',
            })

        return jsonify({'ok': True})
    finally:
        cursor.close()


@login_bp.route('/api/verificar-live', methods=['POST'])
def verificar_live():
    """
    Recibe un frame del video (base64 JPEG) y ejecuta solo el anti-spoofing
    de DeepFace. Devuelve JSON {is_real, message} para feedback en tiempo real.
    No registra asistencia.
    """
    foto = request.form.get('foto', '')
    if not foto or ',' not in foto:
        return jsonify({'is_real': False, 'message': 'Sin imagen'})

    try:
        _, foto_data = foto.split(',', 1)
        foto_bytes = base64.b64decode(foto_data)
        nparr = np.frombuffer(foto_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            return jsonify({'is_real': False, 'message': 'No se pudo procesar la imagen'})

        fd, tmp_path = tempfile.mkstemp(suffix='.jpg')
        try:
            os.close(fd)
            cv2.imwrite(tmp_path, img)

            faces = DeepFace.extract_faces(
                img_path=tmp_path,
                anti_spoofing=True,
                enforce_detection=True,
                detector_backend='opencv',
            )

            for face in faces:
                if not face.get('is_real', True):
                    score = face.get('antispoof_score', 0.0)
                    return jsonify({
                        'is_real': False,
                        'score': round(score, 3),
                        'message': 'Imagen impresa o pantalla detectada',
                    })

            return jsonify({'is_real': True, 'message': 'Rostro real confirmado'})

        except Exception as e:
            err = str(e).lower()
            if any(k in err for k in ('face could not', 'no face', '0 face', 'cannot find')):
                return jsonify({'is_real': False, 'message': 'No se detectó un rostro. Acérquese a la cámara.'})
            return jsonify({'is_real': False, 'message': 'Error en verificación de rostro'})

        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    except Exception:
        return jsonify({'is_real': False, 'message': 'Error inesperado en la verificación'})


def is_within_radius(user_lat, user_lon, target_lat, target_lon, radius_meters):
    R = 6371000
    dlat = radians(target_lat - user_lat)
    dlon = radians(target_lon - user_lon)
    a = (
        sin(dlat / 2) ** 2
        + cos(radians(user_lat)) * cos(radians(target_lat)) * sin(dlon / 2) ** 2
    )
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    distancia = R * c
    return distancia <= radius_meters, distancia


@login_bp.route('/marcarDocente', methods=['POST'])
def login():
    codigo = request.form.get('codigo') or None
    clave = request.form.get('clave') or None
    latitud = request.form.get('latitud') or None
    longitud = request.form.get('longitud') or None
    foto = request.form.get('foto_docente') or None
    foto_bytes = None

    if foto is not None:
        _, foto_data = foto.split(',', 1)
        foto_bytes = base64.b64decode(foto_data)

    if not codigo or not clave:
        return render_template('index.html', error='Por favor, ingrese código y clave')

    cursor = get_cursor()
    cursor.execute(
        "SELECT * FROM profesor a INNER JOIN persona b ON a.cpersona = b.cpersona "
        "WHERE a.cprofesor = ? AND b.tclave_sil = ?",
        (codigo, clave),
    )
    datos_docente = cursor.fetchone()
    cursor.close()

    if datos_docente is None:
        return render_template('index.html', error='Código o clave incorrectos')

    if latitud is None or longitud is None:
        return redirect(url_for('hello', error='No se pudo obtener ubicación'))

    LAT_UNI = -25.27477255313027
    LON_UNI = -57.5941949334686

    ubicacion_permitida, distancia = is_within_radius(
        float(latitud), float(longitud), LAT_UNI, LON_UNI, 1000
    )

    if not ubicacion_permitida:
        return redirect(
            url_for(
                'hello',
                error=f'No se encuentra dentro del área permitida para marcar asistencia. ({distancia:.2f} m)',
            )
        )

    cursor = get_cursor()

    cursor.execute(
        "SELECT tipo_marcacion, estado FROM marcacion_docente "
        "WHERE cprofesor = ? AND CONVERT(date, fecha) = CONVERT(date, GETDATE()) "
        "ORDER BY fecha DESC",
        (datos_docente.cprofesor,),
    )
    marcaciones_hoy = cursor.fetchall()

    aprobadas = [m for m in marcaciones_hoy if m[1] == 'APROBADO']
    en_proceso = any(m[1] in ('PENDIENTE', 'PROCESANDO') for m in marcaciones_hoy)

    if len(aprobadas) >= 2:
        cursor.close()
        return redirect(url_for('hello', error='Ya completó sus dos marcaciones del día (entrada y salida).'))

    if en_proceso:
        cursor.close()
        return redirect(url_for('hello', error='Tiene una marcación pendiente de verificación. Espere a que sea procesada.'))

    tipo_marcacion = 'S' if len(aprobadas) == 1 else 'E'

    query_datos = """
        SELECT DISTINCT cinstitucion, cprograma, cperiodo, ccurso, cbloque, cprofesor
        FROM bloque_sesion_prof
        WHERE cprofesor = ? AND cprograma = 5 AND ndia = DATEPART(WEEKDAY, GETDATE())
          AND cperiodo = (
              SELECT MAX(cperiodo) FROM bloque_sesion_prof
              WHERE cprofesor = ? AND cprograma = 5 AND ndia = DATEPART(WEEKDAY, GETDATE())
          )
        ORDER BY cperiodo DESC
    """
    cursor.execute(query_datos, (datos_docente.cprofesor, datos_docente.cprofesor))
    datos = cursor.fetchone()

    query_insert = """
        INSERT INTO marcacion_docente (
            cinstitucion, cprograma, cperiodo, ccurso, cbloque, cprofesor,
            fecha, estado, tipo_marcacion, latitud, longitud, distancia, tfoto
        )
        VALUES (?, ?, ?, ?, ?, ?, GETDATE(), ?, ?, ?, ?, ?, ?)
    """
    cursor.execute(
        query_insert,
        (
            datos[0], datos[1], datos[2], datos[3], datos[4], datos[5],
            'PENDIENTE', tipo_marcacion,
            latitud, longitud, distancia, foto_bytes,
        ),
    )
    cursor.commit()
    cursor.close()

    return redirect(url_for('hello', success='Asistencia registrada correctamente. La verificación de su asistencia se está procesando en segundo plano.'))
