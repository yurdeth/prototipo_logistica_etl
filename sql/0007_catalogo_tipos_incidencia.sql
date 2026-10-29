-- 0007_catalogo_tipos_incidencia.sql
-- staging.st_tipos_incidencias: el catálogo completo de tipos (6 miembros),
-- para que dim_tipo_incidencia tenga todos los tipos del catálogo y no solo
-- los que aparecen en las incidencias registradas de la corrida actual.

CREATE TABLE IF NOT EXISTS staging.st_tipos_incidencias (
    id_tipo      integer PRIMARY KEY,
    nombre_tipo  text NOT NULL
);
