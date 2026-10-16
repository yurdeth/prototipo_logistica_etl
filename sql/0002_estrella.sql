-- 0002_estrella.sql
-- Modelo estrella Kimball del DW. Decisión de carga (aprobada): foto completa
-- por corrida — los hechos se reconstruyen desde staging en cada ejecución,
-- las dimensiones crecen por natural key (idempotentes).
--
-- Convención de claves: *_sk = subrogada del DW; *_oltp = identificador de la
-- operación. dim_tiempo.id_tiempo = 0 es el miembro "sin fecha" para hechos
-- cuyo evento aún no ocurre (envío no entregado), evitando nulos en las FKs.

-- ── Dimensiones ──

CREATE TABLE IF NOT EXISTS dim_tiempo (
    id_tiempo        integer PRIMARY KEY,          -- AAAAMMDD; 0 = sin fecha
    fecha            date UNIQUE,                  -- NULL en el miembro 0
    anio             integer NOT NULL,
    trimestre        integer NOT NULL,
    mes              integer NOT NULL,
    nombre_mes       text NOT NULL,
    dia_semana       integer NOT NULL,             -- 1=lunes … 7=domingo
    nombre_dia       text NOT NULL,
    es_fin_de_semana boolean NOT NULL
);

-- Miembro "sin fecha" para hechos con evento aún no ocurrido (sin nulos en FKs)
INSERT INTO dim_tiempo (id_tiempo, fecha, anio, trimestre, mes, nombre_mes, dia_semana, nombre_dia, es_fin_de_semana)
VALUES (0, NULL, 0, 0, 0, '(sin fecha)', 0, '(sin fecha)', false)
ON CONFLICT (id_tiempo) DO NOTHING;

CREATE TABLE IF NOT EXISTS dim_estado (
    id_estado_sk    integer PRIMARY KEY,
    id_estado_oltp  integer NOT NULL UNIQUE,
    nombre_estado   text NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_territorio (
    id_territorio_sk    integer PRIMARY KEY,
    id_territorio_oltp  integer NOT NULL UNIQUE,
    nombre_territorio   text NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_cliente (
    id_cliente_sk    integer PRIMARY KEY,
    id_cliente_oltp  integer NOT NULL UNIQUE,
    nombre           text NOT NULL,
    tipo_cliente     text NOT NULL,
    territorio_sk    integer NOT NULL REFERENCES dim_territorio(id_territorio_sk)
);

CREATE TABLE IF NOT EXISTS dim_sucursal (
    id_sucursal_sk   integer PRIMARY KEY,
    id_sucursal_oltp integer NOT NULL UNIQUE,
    codigo           text NOT NULL,
    nombre           text NOT NULL,
    territorio_sk    integer NOT NULL REFERENCES dim_territorio(id_territorio_sk),
    latitud          numeric(9,6),
    longitud         numeric(9,6)
);

CREATE TABLE IF NOT EXISTS dim_vehiculo (
    id_vehiculo_sk   integer PRIMARY KEY,
    id_vehiculo_oltp integer NOT NULL UNIQUE,
    placa            text NOT NULL,
    tipo             text NOT NULL,
    capacidad_kg     numeric(10,2),
    consumo_km_gal   numeric(5,2)
);

CREATE TABLE IF NOT EXISTS dim_conductor (
    id_conductor_sk   integer PRIMARY KEY,
    id_empleado_oltp  integer NOT NULL UNIQUE,
    nombre_completo   text NOT NULL,
    numero_licencia   text,
    sucursal_base     text
);

CREATE TABLE IF NOT EXISTS dim_ruta (
    id_ruta_sk       integer PRIMARY KEY,
    id_conexion_oltp integer NOT NULL UNIQUE,
    origen           text NOT NULL,
    destino          text NOT NULL,
    distancia_km     numeric(10,2) NOT NULL,
    tiempo_min       integer NOT NULL
);

-- ── Hechos ──
-- Medidas condicionales (horas_hasta_entrega, entregado_a_tiempo,
-- distancia_optima_grafo_km) admiten NULL mientras el hecho no cierra;
-- las FKs nunca son nulas gracias al miembro 0 de dim_tiempo.

CREATE TABLE IF NOT EXISTS hecho_envios (
    hecho_id             bigint PRIMARY KEY,
    id_envio_oltp        integer NOT NULL UNIQUE,
    codigo_guia          text NOT NULL,
    tiempo_registro_sk   integer NOT NULL REFERENCES dim_tiempo(id_tiempo),
    tiempo_comprometida_sk integer NOT NULL REFERENCES dim_tiempo(id_tiempo),
    tiempo_entrega_sk    integer NOT NULL DEFAULT 0 REFERENCES dim_tiempo(id_tiempo),
    estado_sk            integer NOT NULL REFERENCES dim_estado(id_estado_sk),
    remitente_sk         integer NOT NULL REFERENCES dim_cliente(id_cliente_sk),
    destinatario_sk      integer NOT NULL REFERENCES dim_cliente(id_cliente_sk),
    sucursal_origen_sk   integer NOT NULL REFERENCES dim_sucursal(id_sucursal_sk),
    territorio_destino_sk integer NOT NULL REFERENCES dim_territorio(id_territorio_sk),
    peso_kg              numeric(10,2) NOT NULL,
    volumen_m3           numeric(10,2),
    prioridad            text NOT NULL,
    horas_hasta_entrega  numeric(10,2),
    entregado_a_tiempo   boolean
);

CREATE TABLE IF NOT EXISTS hecho_despachos (
    hecho_id                   bigint PRIMARY KEY,
    id_despacho_oltp           integer NOT NULL UNIQUE,
    tiempo_sk                  integer NOT NULL REFERENCES dim_tiempo(id_tiempo),
    sucursal_sk                integer NOT NULL REFERENCES dim_sucursal(id_sucursal_sk),
    conductor_sk               integer NOT NULL REFERENCES dim_conductor(id_conductor_sk),
    vehiculo_sk                integer NOT NULL REFERENCES dim_vehiculo(id_vehiculo_sk),
    ruta_sk                    integer REFERENCES dim_ruta(id_ruta_sk),
    estado_despacho            text NOT NULL,
    km_planificados            numeric(10,2),
    km_recorridos              numeric(10,2),
    distancia_optima_grafo_km  numeric(10,2),
    costo_estimado             numeric(10,2),
    minutos_retraso            integer NOT NULL DEFAULT 0,
    peso_asignado_kg           numeric(12,2) NOT NULL DEFAULT 0,
    entregas_completadas       integer NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS hecho_eventos (
    hecho_id              bigint PRIMARY KEY,
    id_evento_oltp        bigint NOT NULL UNIQUE,
    envio_oltp_id         integer NOT NULL,
    estado_sk             integer NOT NULL REFERENCES dim_estado(id_estado_sk),
    tiempo_sk             integer NOT NULL REFERENCES dim_tiempo(id_tiempo),
    horas_desde_anterior  numeric(10,2) NOT NULL DEFAULT 0,
    horas_desde_registro  numeric(10,2) NOT NULL DEFAULT 0,
    nota                  text
);

-- Índices de consulta típicos de los tableros
CREATE INDEX IF NOT EXISTS idx_hecho_envios_entrega ON hecho_envios (tiempo_entrega_sk);
CREATE INDEX IF NOT EXISTS idx_hecho_envios_estado ON hecho_envios (estado_sk);
CREATE INDEX IF NOT EXISTS idx_hecho_despachos_tiempo ON hecho_despachos (tiempo_sk);
CREATE INDEX IF NOT EXISTS idx_hecho_eventos_envio ON hecho_eventos (envio_oltp_id);
