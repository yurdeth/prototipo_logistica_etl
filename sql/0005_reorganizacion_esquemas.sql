-- 0005_reorganizacion_esquemas.sql
-- Organiza físicamente el almacén en sus dos esquemas: las copias planas de
-- la operación en staging y el modelo estrella (dimensiones, hechos y el
-- registro de escenarios) en dw. En instalaciones ya migradas mueve las
-- tablas desde public; si ya están en su esquema, cada movimiento es un
-- no-op (IF EXISTS). Limpia además el rastro de un diseño previo: dim_ruta
-- y las columnas ruta_sk / distancia_optima_grafo_km de hecho_despachos,
-- que ningún proceso poblaba.

CREATE SCHEMA IF NOT EXISTS dw;

-- copias de la operación → staging
ALTER TABLE IF EXISTS public.st_territorios      SET SCHEMA staging;
ALTER TABLE IF EXISTS public.st_sucursales       SET SCHEMA staging;
ALTER TABLE IF EXISTS public.st_clientes        SET SCHEMA staging;
ALTER TABLE IF EXISTS public.st_estados_envios   SET SCHEMA staging;
ALTER TABLE IF EXISTS public.st_vehiculos        SET SCHEMA staging;
ALTER TABLE IF EXISTS public.st_empleados        SET SCHEMA staging;
ALTER TABLE IF EXISTS public.st_conexiones       SET SCHEMA staging;
ALTER TABLE IF EXISTS public.st_envios           SET SCHEMA staging;
ALTER TABLE IF EXISTS public.st_envio_eventos    SET SCHEMA staging;
ALTER TABLE IF EXISTS public.st_despachos        SET SCHEMA staging;
ALTER TABLE IF EXISTS public.st_despacho_paradas SET SCHEMA staging;
ALTER TABLE IF EXISTS public.st_incidencias      SET SCHEMA staging;

-- modelo estrella y registro de escenarios → dw
ALTER TABLE IF EXISTS public.dim_tiempo            SET SCHEMA dw;
ALTER TABLE IF EXISTS public.dim_estado            SET SCHEMA dw;
ALTER TABLE IF EXISTS public.dim_territorio        SET SCHEMA dw;
ALTER TABLE IF EXISTS public.dim_cliente           SET SCHEMA dw;
ALTER TABLE IF EXISTS public.dim_sucursal          SET SCHEMA dw;
ALTER TABLE IF EXISTS public.dim_vehiculo          SET SCHEMA dw;
ALTER TABLE IF EXISTS public.dim_conductor         SET SCHEMA dw;
ALTER TABLE IF EXISTS public.dim_ruta              SET SCHEMA dw;
ALTER TABLE IF EXISTS public.hecho_envios          SET SCHEMA dw;
ALTER TABLE IF EXISTS public.hecho_despachos       SET SCHEMA dw;
ALTER TABLE IF EXISTS public.hecho_eventos         SET SCHEMA dw;
ALTER TABLE IF EXISTS public.resultado_escenario   SET SCHEMA dw;

-- rastro de diseño previo: nadie poblaba esta dimensión ni estas columnas
ALTER TABLE dw.hecho_despachos DROP COLUMN IF EXISTS ruta_sk;
ALTER TABLE dw.hecho_despachos DROP COLUMN IF EXISTS distancia_optima_grafo_km;
DROP TABLE IF EXISTS dw.dim_ruta;

-- un resultado sin ruta posible se registra sin totales, no como costo cero
ALTER TABLE dw.resultado_escenario ALTER COLUMN km_totales DROP NOT NULL;
ALTER TABLE dw.resultado_escenario ALTER COLUMN minutos_totales DROP NOT NULL;

-- el lector de cuadres y el tablero acceden a los dos esquemas
GRANT USAGE ON SCHEMA staging, dw TO etl_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA staging, dw TO etl_reader;
ALTER DEFAULT PRIVILEGES FOR ROLE etl_writer IN SCHEMA dw
    GRANT SELECT ON TABLES TO etl_reader;
