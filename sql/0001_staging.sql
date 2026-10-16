-- 0001_staging.sql
-- Esquema de trabajo del ETL: copias planas de la OLTP por corrida.
-- Idempotente: los CREATE son IF NOT EXISTS y la tabla de versiones también.
-- Aplicar como etl_writer contra prototipo_logistica_dw (lo hace etl/migrar.py).

CREATE SCHEMA IF NOT EXISTS staging;

CREATE TABLE IF NOT EXISTS sql_versiones (
    version     integer PRIMARY KEY,
    archivo     text NOT NULL,
    aplicado_en timestamptz NOT NULL DEFAULT now()
);

-- etl_reader lee el DW para las verificaciones de cuadre (también las tablas futuras)
ALTER DEFAULT PRIVILEGES FOR ROLE etl_writer IN SCHEMA public GRANT SELECT ON TABLES TO etl_reader;
ALTER DEFAULT PRIVILEGES FOR ROLE etl_writer IN SCHEMA staging GRANT SELECT ON TABLES TO etl_reader;
