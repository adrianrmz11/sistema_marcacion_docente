from flask import Blueprint, render_template, request, Response, jsonify, session, redirect, url_for
from modules.db_connection import get_cursor
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date
from functools import wraps

marcaciones_bp = Blueprint('marcaciones', __name__)


def login_requerido(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('admin_usuario'):
            return redirect(url_for('marcaciones.login_admin'))
        return f(*args, **kwargs)
    return wrapper


# ── AUTH ──────────────────────────────────────────────────────────────────────

@marcaciones_bp.route('/marcaciones/login', methods=['GET', 'POST'])
def login_admin():
    error = None
    if request.method == 'POST':
        usuario = request.form.get('usuario', '').strip()
        clave   = request.form.get('clave', '')

        cursor = get_cursor()
        cursor.execute(
            "SELECT cusuario, clave_hash, nombre FROM marcacion_docentes_usuario "
            "WHERE usuario = ? AND activo = 1",
            (usuario,),
        )
        row = cursor.fetchone()
        cursor.close()

        if row and check_password_hash(row[1], clave):
            session['admin_usuario'] = usuario
            session['admin_nombre']  = row[2]
            return redirect(url_for('marcaciones.listar_marcaciones'))

        error = 'Usuario o contraseña incorrectos.'

    return render_template('marcaciones_login.html', error=error)


@marcaciones_bp.route('/marcaciones/logout')
def logout_admin():
    session.pop('admin_usuario', None)
    session.pop('admin_nombre', None)
    return redirect(url_for('marcaciones.login_admin'))


# ── LISTADO ───────────────────────────────────────────────────────────────────

@marcaciones_bp.route('/marcaciones')
@login_requerido
def listar_marcaciones():
    fecha     = request.args.get('fecha') or date.today().isoformat()
    cprofesor = request.args.get('cprofesor', '').strip()

    cursor = get_cursor()
    params = (fecha, cprofesor) if cprofesor else (fecha,)
    cursor.execute(
        """
        SELECT
            md.cmarcacion,
            pr.cprofesor,
            p.dpersona,
            md.fecha,
            md.tipo_marcacion,
            md.estado,
            md.distancia,
            md.mensaje_procesado
        FROM marcacion_docente md
        INNER JOIN profesor pr ON md.cprofesor = pr.cprofesor
        INNER JOIN persona  p  ON pr.cpersona  = p.cpersona
        WHERE CONVERT(date, md.fecha) = ?
        """ + ("AND pr.cprofesor = ?" if cprofesor else "") + """
        ORDER BY md.fecha DESC
        """,
        params,
    )

    marcaciones = []
    for row in cursor.fetchall():
        marcaciones.append({
            'cmarcacion': row[0],
            'cprofesor':  row[1],
            'nombre':     row[2],
            'fecha_full': row[3].strftime('%d/%m/%Y %H:%M:%S') if row[3] else '-',
            'tipo_raw':   row[4],
            'tipo':       'Entrada' if row[4] == 'E' else 'Salida',
            'estado':     row[5] or 'PENDIENTE',
            'distancia':  f"{row[6]:.0f} m" if row[6] is not None else '-',
            'mensaje':    row[7] or '-',
        })
    cursor.close()

    contadores = {
        'total':     len(marcaciones),
        'aprobado':  sum(1 for m in marcaciones if m['estado'] == 'APROBADO'),
        'pendiente': sum(1 for m in marcaciones if m['estado'] in ('PENDIENTE', 'PROCESANDO')),
        'rechazado': sum(1 for m in marcaciones if m['estado'] == 'RECHAZADO'),
    }

    return render_template(
        'marcaciones.html',
        marcaciones=marcaciones,
        contadores=contadores,
        fecha=fecha,
        cprofesor=cprofesor,
        admin_nombre=session.get('admin_nombre'),
    )


# ── FOTO ──────────────────────────────────────────────────────────────────────

@marcaciones_bp.route('/marcaciones/foto/<int:cmarcacion>')
@login_requerido
def foto_marcacion(cmarcacion):
    cursor = get_cursor()
    cursor.execute(
        "SELECT tfoto FROM marcacion_docente WHERE cmarcacion = ?", (cmarcacion,)
    )
    row = cursor.fetchone()
    cursor.close()

    if not row or not row[0]:
        return Response(status=404)

    return Response(bytes(row[0]), mimetype='image/jpeg')


# ── VERIFICACIÓN MANUAL ───────────────────────────────────────────────────────

@marcaciones_bp.route('/marcaciones/verificar/<int:cmarcacion>', methods=['POST'])
@login_requerido
def verificar_marcacion(cmarcacion):
    data   = request.get_json()
    estado = (data or {}).get('estado', '')
    motivo = (data or {}).get('motivo', '').strip()

    if estado not in ('APROBADO', 'RECHAZADO'):
        return jsonify({'ok': False, 'error': 'Estado inválido'}), 400

    if estado == 'RECHAZADO' and not motivo:
        return jsonify({'ok': False, 'error': 'El motivo es requerido para rechazar'}), 400

    cursor = get_cursor()
    cursor.execute(
        "UPDATE marcacion_docente SET estado = ?, mensaje_procesado = ? WHERE cmarcacion = ?",
        (estado, motivo or f'Verificación manual: {estado.lower()}', cmarcacion),
    )
    cursor.commit()
    cursor.close()

    return jsonify({'ok': True, 'estado': estado, 'motivo': motivo})


# ── UTILIDAD: crear usuario desde consola ────────────────────────────────────
# Ejecutar una vez: python -c "from routers.marcaciones import crear_usuario; crear_usuario('admin','<clave-segura>','Administrador')"

def crear_usuario(usuario, clave, nombre):
    cursor = get_cursor()
    cursor.execute(
        "INSERT INTO marcacion_docentes_usuario (usuario, clave_hash, nombre) VALUES (?, ?, ?)",
        (usuario, generate_password_hash(clave), nombre),
    )
    cursor.commit()
    cursor.close()
    print(f"Usuario '{usuario}' creado.")
