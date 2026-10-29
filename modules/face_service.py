import os
import tempfile
import numpy as np

FOTOS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'fotos_docente')


def _get_reference_path(teacher_id):
    """Return path to teacher reference photo, or None if not found."""
    for ext in ('jpg', 'jpeg', 'png', 'webp'):
        path = os.path.join(FOTOS_DIR, f"{teacher_id}.{ext}")
        if os.path.exists(path):
            return path
    return None


def verify_face(photo_bytes, teacher_id):
    """
    Verify teacher identity by comparing captured photo against stored reference.

    Steps:
      1. Anti-spoofing: detect printed photos / screen replays (MiniFASNet via DeepFace).
      2. Face comparison: Facenet512 cosine distance.

    Returns:
        (estado: str, mensaje: str)
        estado is one of: 'APROBADO', 'RECHAZADO', 'PENDIENTE'
    """
    if not photo_bytes:
        return 'PENDIENTE', 'No se capturó foto para verificación'

    ref_path = _get_reference_path(teacher_id)
    if ref_path is None:
        return 'PENDIENTE', 'Sin foto de referencia registrada para este docente'

    try:
        import cv2
        from deepface import DeepFace
    except ImportError:
        return 'PENDIENTE', 'Módulo de reconocimiento facial no disponible (instale deepface y opencv-python)'

    nparr = np.frombuffer(photo_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return 'RECHAZADO', 'No se pudo procesar la imagen capturada'

    fd, tmp_path = tempfile.mkstemp(suffix='.jpg')
    try:
        os.close(fd)
        cv2.imwrite(tmp_path, img)

        # ── 1. ANTI-SPOOFING ──────────────────────────────────────────────────
        # Detects printed photos, tablets/screens held to the camera.
        # Uses the MiniFASNet model included with deepface (auto-downloaded on first run).
        try:
            faces = DeepFace.extract_faces(
                img_path=tmp_path,
                anti_spoofing=True,
                enforce_detection=True,
                detector_backend='opencv',
            )
            for face in faces:
                if not face.get('is_real', True):
                    score = face.get('antispoof_score', 0.0)
                    return (
                        'RECHAZADO',
                        f'Intento de suplantación detectado: imagen impresa o en pantalla '
                        f'(confianza: {score:.0%})',
                    )
        except Exception as e:
            err = str(e).lower()
            if any(k in err for k in ('face could not', 'no face', '0 face', 'cannot find')):
                return 'RECHAZADO', 'No se detectó un rostro en la imagen capturada'
            # Fail-closed: si el modelo no puede correr por cualquier razón, rechazar.
            return 'RECHAZADO', 'No se pudo completar la verificación anti-suplantación. Intente de nuevo.'

        # ── 2. FACE COMPARISON ────────────────────────────────────────────────
        result = DeepFace.verify(
            img1_path=tmp_path,
            img2_path=ref_path,
            model_name='Facenet512',
            enforce_detection=True,
            distance_metric='cosine',
            detector_backend='opencv',
        )

        if result['verified']:
            similarity = round((1 - result['distance']) * 100, 1)
            return 'APROBADO', f'Verificación facial exitosa (similitud: {similarity}%)'

        return 'RECHAZADO', 'El rostro no coincide con el docente registrado'

    except Exception as e:
        msg = str(e).lower()
        if any(k in msg for k in ('face could not', 'no face', '0 face', 'cannot find')):
            return 'RECHAZADO', 'No se detectó un rostro válido en la imagen'
        return 'PENDIENTE', 'Error en el proceso de verificación facial'

    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
