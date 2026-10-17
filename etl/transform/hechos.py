"""Transform (parte 2): carga los hechos del estrella desde staging.

Foto completa por corrida (decisión aprobada): los hechos se truncan y se
reconstruyen enteros desde staging, porque un envío cambia de estado en la
OLTP y el DW no actualiza: cada corrida produce la versión vigente.
Las medidas condicionales (entrega, a tiempo) quedan NULL mientras el envío
no cierra; las FKs usan el miembro 0 de dim_tiempo para "sin fecha".
"""

import psycopg

from etl.conexiones import conexion_dw

ZONA_LOCAL = "America/El_Salvador"

SQL_HECHO_ENVIOS = """
    INSERT INTO hecho_envios (
        hecho_id, id_envio_oltp, codigo_guia,
        tiempo_registro_sk, tiempo_comprometida_sk, tiempo_entrega_sk,
        estado_sk, remitente_sk, destinatario_sk, sucursal_origen_sk,
        territorio_destino_sk, peso_kg, volumen_m3, prioridad,
        horas_hasta_entrega, entregado_a_tiempo)
    SELECT
        ROW_NUMBER() OVER (ORDER BY e.id_envio),
        e.id_envio, e.codigo_guia,
        tr.id_tiempo, tc.id_tiempo,
        COALESCE(te.id_tiempo, 0),
        est.id_estado_sk,
        cr.id_cliente_sk, cd.id_cliente_sk,
        suc.id_sucursal_sk, ter.id_territorio_sk,
        e.peso_kg, e.volumen_m3, e.prioridad,
        CASE WHEN entrega.hora IS NOT NULL
             THEN ROUND(EXTRACT(epoch FROM (entrega.hora - e.fecha_registro)) / 3600.0, 2)
        END,
        CASE WHEN entrega.hora IS NOT NULL
             THEN entrega.hora <= e.fecha_comprometida
        END
    FROM st_envios e
    JOIN dim_tiempo tr ON tr.fecha = (e.fecha_registro AT TIME ZONE %(zona)s)::date
    JOIN dim_tiempo tc ON tc.fecha = (e.fecha_comprometida AT TIME ZONE %(zona)s)::date
    JOIN dim_estado est ON est.id_estado_oltp = e.estado_id
    JOIN dim_cliente cr ON cr.id_cliente_oltp = e.cliente_remitente_id
    JOIN dim_cliente cd ON cd.id_cliente_oltp = e.cliente_destinatario_id
    JOIN dim_sucursal suc ON suc.id_sucursal_oltp = e.sucursal_origen_id
    JOIN dim_territorio ter ON ter.id_territorio_oltp = e.territorio_destino_id
    LEFT JOIN (
        SELECT ev.envio_id, MAX(ev.ocurrido_en) AS hora
        FROM st_envio_eventos ev
        WHERE ev.nombre_estado = 'ENTREGADO'
        GROUP BY ev.envio_id
    ) entrega ON entrega.envio_id = e.id_envio
    LEFT JOIN dim_tiempo te ON te.fecha = (entrega.hora AT TIME ZONE %(zona)s)::date
"""

SQL_HECHO_DESPACHOS = """
    INSERT INTO hecho_despachos (
        hecho_id, id_despacho_oltp, tiempo_sk, sucursal_sk, conductor_sk,
        vehiculo_sk, estado_despacho, km_planificados, km_recorridos,
        costo_estimado, minutos_retraso, peso_asignado_kg, entregas_completadas)
    SELECT
        ROW_NUMBER() OVER (ORDER BY d.id_despacho),
        d.id_despacho,
        t.id_tiempo,
        suc.id_sucursal_sk,
        con.id_conductor_sk,
        veh.id_vehiculo_sk,
        d.nombre_estado,
        d.km_planificados, d.km_recorridos, d.costo_estimado,
        COALESCE(inc.retraso, 0),
        COALESCE(par.peso, 0),
        COALESCE(par.entregadas, 0)
    FROM st_despachos d
    JOIN dim_tiempo t ON t.fecha = d.fecha
    JOIN dim_sucursal suc ON suc.id_sucursal_oltp = d.sucursal_origen_id
    JOIN dim_conductor con ON con.id_empleado_oltp = d.conductor_empleado_id
    JOIN dim_vehiculo veh ON veh.id_vehiculo_oltp = d.vehiculo_id
    LEFT JOIN (
        SELECT despacho_id, SUM(minutos_retraso) AS retraso
        FROM st_incidencias
        WHERE despacho_id IS NOT NULL
        GROUP BY despacho_id
    ) inc ON inc.despacho_id = d.id_despacho
    LEFT JOIN (
        SELECT p.despacho_id,
               SUM(e.peso_kg) AS peso,
               COUNT(*) FILTER (WHERE e.nombre_estado = 'ENTREGADO') AS entregadas
        FROM st_despacho_paradas p
        JOIN st_envios e ON e.id_envio = p.envio_id
        GROUP BY p.despacho_id
    ) par ON par.despacho_id = d.id_despacho
"""

SQL_HECHO_EVENTOS = """
    INSERT INTO hecho_eventos (
        hecho_id, id_evento_oltp, envio_oltp_id, estado_sk, tiempo_sk,
        horas_desde_anterior, horas_desde_registro, nota)
    SELECT
        ROW_NUMBER() OVER (ORDER BY ev.id_evento),
        ev.id_evento, ev.envio_id, est.id_estado_sk, t.id_tiempo,
        COALESCE(ROUND(EXTRACT(epoch FROM (
            ev.ocurrido_en - LAG(ev.ocurrido_en) OVER ventana)) / 3600.0, 2), 0),
        COALESCE(ROUND(EXTRACT(epoch FROM (
            ev.ocurrido_en - FIRST_VALUE(ev.ocurrido_en) OVER ventana)) / 3600.0, 2), 0),
        ev.nota
    FROM st_envio_eventos ev
    JOIN dim_estado est ON est.id_estado_oltp = ev.estado_id
    JOIN dim_tiempo t ON t.fecha = (ev.ocurrido_en AT TIME ZONE %(zona)s)::date
    WINDOW ventana AS (PARTITION BY ev.envio_id ORDER BY ev.id_evento)
"""

HECHOS = [
    ("hecho_envios", SQL_HECHO_ENVIOS),
    ("hecho_despachos", SQL_HECHO_DESPACHOS),
    ("hecho_eventos", SQL_HECHO_EVENTOS),
]


def cargar_hechos() -> dict[str, int]:
    """Reconstruye los 3 hechos desde staging; devuelve filas por hecho."""
    cargadas: dict[str, int] = {}

    with conexion_dw() as cn, cn.cursor() as cur:
        for tabla, sql in HECHOS:
            cur.execute(f"TRUNCATE TABLE {tabla}")  # noqa: S608
            cur.execute(sql, {"zona": ZONA_LOCAL})
            cargadas[tabla] = cur.rowcount

    return cargadas


if __name__ == "__main__":
    for tabla, filas in cargar_hechos().items():
        print(f"{tabla:20} {filas:>7} filas")
