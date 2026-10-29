"""Transform (parte 1): carga las dimensiones del estrella desde staging.

Estrategia idempotente por natural key: cada INSERT agrega únicamente las
filas cuyo identificador de la OLTP aún no existe en la dimensión, con
subrogada = (máximo actual) + row_number. Re-corrida no duplica ni renumera.
"""

import psycopg

from etl.conexiones import conexion_dw

ZONA_LOCAL = "America/El_Salvador"

# orden de carga: territorio/estado/tiempo antes de quienes los referencian
CARGAS = [
    "dim_territorio",
    "dim_estado",
    "dim_tiempo",
    "dim_cliente",
    "dim_sucursal",
    "dim_vehiculo",
    "dim_conductor",
    "dim_tipo_incidencia",
]

SQL: dict[str, str] = {
    "dim_territorio": """
        INSERT INTO dim_territorio (id_territorio_sk, id_territorio_oltp, nombre_territorio)
        SELECT (SELECT COALESCE(MAX(id_territorio_sk), 0) FROM dim_territorio)
               + ROW_NUMBER() OVER (ORDER BY t.id_territorio),
               t.id_territorio, t.nombre_territorio
        FROM st_territorios t
        WHERE NOT EXISTS (SELECT 1 FROM dim_territorio d
                          WHERE d.id_territorio_oltp = t.id_territorio)
    """,
    "dim_estado": """
        INSERT INTO dim_estado (id_estado_sk, id_estado_oltp, nombre_estado)
        SELECT (SELECT COALESCE(MAX(id_estado_sk), 0) FROM dim_estado)
               + ROW_NUMBER() OVER (ORDER BY e.id_estado),
               e.id_estado, e.nombre_estado
        FROM st_estados_envios e
        WHERE NOT EXISTS (SELECT 1 FROM dim_estado d
                          WHERE d.id_estado_oltp = e.id_estado)
    """,
    "dim_tiempo": """
        INSERT INTO dim_tiempo (id_tiempo, fecha, anio, trimestre, mes,
                                nombre_mes, dia_semana, nombre_dia,
                                es_fin_de_semana)
        SELECT to_char(f, 'YYYYMMDD')::int, f::date,
               EXTRACT(year FROM f)::int,
               EXTRACT(quarter FROM f)::int,
               EXTRACT(month FROM f)::int,
               to_char(f, 'TMMonth'),
               EXTRACT(isodow FROM f)::int,
               to_char(f, 'TMDay'),
               EXTRACT(isodow FROM f) IN (6, 7)
        FROM (
            SELECT generate_series(
                (SELECT min(fecha) FROM fechas_corte),
                (SELECT max(fecha) FROM fechas_corte),
                interval '1 day')::timestamptz AS f
        ) serie
        WHERE NOT EXISTS (SELECT 1 FROM dim_tiempo d WHERE d.id_tiempo = to_char(f, 'YYYYMMDD')::int)
    """,
    "dim_cliente": """
        INSERT INTO dim_cliente (id_cliente_sk, id_cliente_oltp, nombre,
                                 tipo_cliente, territorio_sk)
        SELECT (SELECT COALESCE(MAX(id_cliente_sk), 0) FROM dim_cliente)
               + ROW_NUMBER() OVER (ORDER BY c.id_cliente),
               c.id_cliente, c.nombre, c.tipo_cliente,
               (SELECT d.id_territorio_sk FROM dim_territorio d
                WHERE d.id_territorio_oltp = c.territorio_id)
        FROM st_clientes c
        WHERE NOT EXISTS (SELECT 1 FROM dim_cliente d
                          WHERE d.id_cliente_oltp = c.id_cliente)
    """,
    "dim_sucursal": """
        INSERT INTO dim_sucursal (id_sucursal_sk, id_sucursal_oltp, codigo,
                                  nombre, territorio_sk, latitud, longitud)
        SELECT (SELECT COALESCE(MAX(id_sucursal_sk), 0) FROM dim_sucursal)
               + ROW_NUMBER() OVER (ORDER BY s.id_sucursal),
               s.id_sucursal, s.codigo, s.nombre_sucursal,
               (SELECT d.id_territorio_sk FROM dim_territorio d
                WHERE d.id_territorio_oltp = s.territorio_id),
               s.latitud, s.longitud
        FROM st_sucursales s
        WHERE NOT EXISTS (SELECT 1 FROM dim_sucursal d
                          WHERE d.id_sucursal_oltp = s.id_sucursal)
    """,
    "dim_vehiculo": """
        INSERT INTO dim_vehiculo (id_vehiculo_sk, id_vehiculo_oltp, placa,
                                  tipo, capacidad_kg, consumo_km_gal)
        SELECT (SELECT COALESCE(MAX(id_vehiculo_sk), 0) FROM dim_vehiculo)
               + ROW_NUMBER() OVER (ORDER BY v.id_vehiculo),
               v.id_vehiculo, v.placa, v.tipo_nombre, v.capacidad_kg,
               v.consumo_km_gal
        FROM st_vehiculos v
        WHERE NOT EXISTS (SELECT 1 FROM dim_vehiculo d
                          WHERE d.id_vehiculo_oltp = v.id_vehiculo)
    """,
    "dim_conductor": """
        INSERT INTO dim_conductor (id_conductor_sk, id_empleado_oltp,
                                   nombre_completo, numero_licencia,
                                   sucursal_base)
        SELECT (SELECT COALESCE(MAX(id_conductor_sk), 0) FROM dim_conductor)
               + ROW_NUMBER() OVER (ORDER BY e.id_empleado),
               e.id_empleado, e.nombres || ' ' || e.apellidos,
               e.numero_licencia, s.nombre_sucursal
        FROM st_empleados e
        JOIN st_sucursales s ON s.id_sucursal = e.sucursal_id
        WHERE e.numero_licencia IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM dim_conductor d
                          WHERE d.id_empleado_oltp = e.id_empleado)
    """,
    "dim_tipo_incidencia": """
        INSERT INTO dim_tipo_incidencia (id_tipo_incidencia_sk,
                                         id_tipo_incidencia_oltp, nombre_tipo)
        SELECT (SELECT COALESCE(MAX(id_tipo_incidencia_sk), 0) FROM dim_tipo_incidencia)
               + ROW_NUMBER() OVER (ORDER BY t.id_tipo),
               t.id_tipo, t.nombre_tipo
        FROM st_tipos_incidencias t
        WHERE NOT EXISTS (SELECT 1 FROM dim_tipo_incidencia d
                          WHERE d.id_tipo_incidencia_oltp = t.id_tipo)
    """,
}

# fechas que alimentan dim_tiempo, en hora local del país
FECHAS_DE_LA_OPERACION = """
    SELECT DISTINCT (fecha_registro AT TIME ZONE %s)::date AS fecha FROM st_envios
    UNION
    SELECT DISTINCT (fecha_comprometida AT TIME ZONE %s)::date FROM st_envios
    UNION
    SELECT DISTINCT (ocurrido_en AT TIME ZONE %s)::date FROM st_envio_eventos
    UNION
    SELECT DISTINCT fecha FROM st_despachos
    UNION
    SELECT DISTINCT (ocurrio_en AT TIME ZONE %s)::date FROM st_incidencias
"""


def cargar_dimensiones() -> dict[str, int]:
    """Carga las 8 dimensiones; devuelve filas insertadas por dimensión."""
    insertadas: dict[str, int] = {}

    with conexion_dw() as cn, cn.cursor() as cur:
        cur.execute(
            "CREATE TEMP TABLE fechas_corte AS " + FECHAS_DE_LA_OPERACION,
            (ZONA_LOCAL, ZONA_LOCAL, ZONA_LOCAL, ZONA_LOCAL),
        )

        for tabla in CARGAS:
            cur.execute(SQL[tabla])
            insertadas[tabla] = cur.rowcount
            cur.execute(f"SELECT count(*) FROM {tabla}")  # noqa: S608
            insertadas[tabla + "_total"] = cur.fetchone()[0]

    return insertadas


if __name__ == "__main__":
    for tabla, filas in cargar_dimensiones().items():
        print(f"{tabla:24} {filas:>7}")
