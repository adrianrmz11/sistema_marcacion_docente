-- Ejecutar una sola vez antes de iniciar la aplicación con reconocimiento facial
ALTER TABLE marcacion_docente
    ADD mensaje_procesado NVARCHAR(500) NULL;
