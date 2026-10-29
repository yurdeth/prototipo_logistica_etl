-- 0006_incidencias_y_paradas.sql
-- El análisis de incidencias (tasa por despacho y retraso promedio por
-- incidencia) se resuelve en el propio almacén con una dimensión y un hecho
-- nuevos; el conteo de paradas pasa a ser medida de hecho_despachos. Las
-- fuentes ya llegaban a staging (st_incidencias, st_despacho_paradas):
-- este paso solo las integra al modelo estrella.

CREATE TABLE IF NOT EXISTS dw.dim_tipo_incidencia (
    id_tipo_incidencia_sk   integer PRIMARY KEY,
    id_tipo_incidencia_oltp integer NOT NULL UNIQUE,
    nombre_tipo             text NOT NULL
);

ALTER TABLE dw.hecho_despachos
    ADD COLUMN IF NOT EXISTS numero_paradas integer NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS dw.hecho_incidencias (
    hecho_id            bigint PRIMARY KEY,
    id_incidencia_oltp  integer NOT NULL UNIQUE,
    tiempo_sk           integer NOT NULL REFERENCES dw.dim_tiempo(id_tiempo),
    tipo_incidencia_sk  integer NOT NULL REFERENCES dw.dim_tipo_incidencia(id_tipo_incidencia_sk),
    id_despacho_oltp    integer,
    id_envio_oltp       integer,
    minutos_retraso     integer NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_hecho_incidencias_tiempo   ON dw.hecho_incidencias (tiempo_sk);
CREATE INDEX IF NOT EXISTS idx_hecho_incidencias_tipo     ON dw.hecho_incidencias (tipo_incidencia_sk);
CREATE INDEX IF NOT EXISTS idx_hecho_incidencias_despacho ON dw.hecho_incidencias (id_despacho_oltp);
