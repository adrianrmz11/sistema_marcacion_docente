# marcacion_docente

Marcación de asistencia docente con verificación facial (Flask + DeepFace + SQL Server).

## Configuración

Copia `.env.example` y define las variables de entorno (la app no arranca sin `SECRET_KEY`):

| Variable | Descripción |
|---|---|
| `SECRET_KEY` | Clave de sesión. Genérala con `python -c "import secrets; print(secrets.token_hex(32))"` |
| `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | Conexión a SQL Server (usa un usuario con permisos mínimos) |
| `FLASK_DEBUG` | `1` solo en desarrollo local |
| `APP_HOST` | Interfaz de escucha (por defecto `127.0.0.1`) |

## Fotos de referencia

Coloca las fotos de los docentes en `fotos_docente/<id>.jpg`. Son datos biométricos:
están excluidas por `.gitignore` y **no deben subirse al repositorio**.

## Usuario administrador

Ejecuta `sql_migrations/` y luego crea el usuario:

```
python -c "from routers.marcaciones import crear_usuario; crear_usuario('admin','<clave-segura>','Administrador')"
```
