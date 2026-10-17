-- 0004_resultados_rutas.sql
-- Registro de rutas calculadas por los escenarios (append-only: es un log,
-- cada corrida agrega su fila con fecha; nunca se edita ni borra).

CREATE TABLE IF NOT EXISTS resultado_escenario (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    escenario     text NOT NULL,          -- base | bloqueo | congestion
    origen        text NOT NULL,
    destino       text NOT NULL,
    ruta          text NOT NULL,          -- códigos de sucursal separados por '->'
    km_totales    numeric(10,2) NOT NULL,
    minutos_totales integer NOT NULL,
    tramo_afectado text,
    penalizacion_min integer NOT NULL DEFAULT 0,
    calculado_en  timestamptz NOT NULL DEFAULT now()
);
