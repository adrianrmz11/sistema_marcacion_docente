CREATE TABLE marcacion_docentes_usuario (
    cusuario   INT           IDENTITY(1,1) PRIMARY KEY,
    usuario    VARCHAR(50)   NOT NULL UNIQUE,
    clave_hash VARCHAR(255)  NOT NULL,
    nombre     VARCHAR(100)  NOT NULL,
    activo     BIT           NOT NULL DEFAULT 1
);

-- Usuario de ejemplo
-- Generar el hash desde Python: werkzeug.security.generate_password_hash('<clave-segura>')
-- y reemplazar el valor abajo antes de ejecutar.
-- INSERT INTO marcacion_docentes_usuario (usuario, clave_hash, nombre)
-- VALUES ('admin', '<hash_aqui>', 'Administrador');
