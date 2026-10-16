-- 0003_staging_tablas.sql
-- Copias planas de la OLTP, una por fuente, con los datos ya aplanados que
-- consumen dimensiones y hechos (los JOIN con catálogos se hacen en el
-- extract, no en el transform). TRUNCATE por corrida: staging no conserva
-- historial, el DW sí.

CREATE TABLE IF NOT EXISTS st_territorios (
    id_territorio integer PRIMARY KEY,
    nombre_territorio text NOT NULL,
    tipo_territorio text NOT NULL
);

CREATE TABLE IF NOT EXISTS st_sucursales (
    id_sucursal integer PRIMARY KEY,
    codigo text NOT NULL,
    nombre_sucursal text NOT NULL,
    territorio_id integer NOT NULL,
    latitud numeric(9,6),
    longitud numeric(9,6),
    activa boolean NOT NULL
);

CREATE TABLE IF NOT EXISTS st_clientes (
    id_cliente integer PRIMARY KEY,
    nombre text NOT NULL,
    tipo_cliente text NOT NULL,
    contacto text,
    territorio_id integer NOT NULL
);

CREATE TABLE IF NOT EXISTS st_estados_envios (
    id_estado integer PRIMARY KEY,
    nombre_estado text NOT NULL
);

CREATE TABLE IF NOT EXISTS st_vehiculos (
    id_vehiculo integer PRIMARY KEY,
    placa text NOT NULL,
    tipo_nombre text NOT NULL,
    capacidad_kg numeric(10,2),
    consumo_km_gal numeric(5,2),
    sucursal_id integer NOT NULL
);

CREATE TABLE IF NOT EXISTS st_empleados (
    id_empleado integer PRIMARY KEY,
    nombres text NOT NULL,
    apellidos text NOT NULL,
    numero_licencia text,
    sucursal_id integer NOT NULL,
    activo boolean NOT NULL
);

CREATE TABLE IF NOT EXISTS st_conexiones (
    id_conexion integer PRIMARY KEY,
    origen_sucursal_id integer NOT NULL,
    destino_sucursal_id integer NOT NULL,
    distancia_km numeric(10,2) NOT NULL,
    tiempo_min integer NOT NULL,
    activa boolean NOT NULL
);

CREATE TABLE IF NOT EXISTS st_envios (
    id_envio integer PRIMARY KEY,
    codigo_guia text NOT NULL,
    cliente_remitente_id integer NOT NULL,
    cliente_destinatario_id integer NOT NULL,
    sucursal_origen_id integer NOT NULL,
    territorio_destino_id integer NOT NULL,
    direccion_destino text NOT NULL,
    peso_kg numeric(10,2) NOT NULL,
    volumen_m3 numeric(10,2),
    estado_id integer NOT NULL,
    nombre_estado text NOT NULL,
    prioridad text NOT NULL,
    fecha_registro timestamptz NOT NULL,
    fecha_comprometida timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS st_envio_eventos (
    id_evento bigint PRIMARY KEY,
    envio_id integer NOT NULL,
    estado_id integer NOT NULL,
    nombre_estado text NOT NULL,
    ocurrido_en timestamptz NOT NULL,
    nota text
);

CREATE TABLE IF NOT EXISTS st_despachos (
    id_despacho integer PRIMARY KEY,
    sucursal_origen_id integer NOT NULL,
    conductor_empleado_id integer NOT NULL,
    vehiculo_id integer NOT NULL,
    fecha date NOT NULL,
    estado_id integer NOT NULL,
    nombre_estado text NOT NULL,
    km_planificados numeric(10,2),
    km_recorridos numeric(10,2),
    costo_estimado numeric(10,2)
);

CREATE TABLE IF NOT EXISTS st_despacho_paradas (
    id_parada integer PRIMARY KEY,
    despacho_id integer NOT NULL,
    envio_id integer NOT NULL,
    orden smallint NOT NULL,
    hora_estimada timestamptz,
    hora_real timestamptz
);

CREATE TABLE IF NOT EXISTS st_incidencias (
    id_incidencia integer PRIMARY KEY,
    tipo_incidencia_id integer NOT NULL,
    nombre_tipo text NOT NULL,
    despacho_id integer,
    envio_id integer,
    ocurrio_en timestamptz NOT NULL,
    descripcion text,
    minutos_retraso integer NOT NULL DEFAULT 0
);
