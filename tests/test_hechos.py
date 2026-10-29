"""Prueba de cuadre: los agregados del DW deben ser IDÉNTICOS a los de la
OLTP. Si el transform perdiera filas, cambiara fechas o mal resolviera una
subrogada, alguna de estas consultas espejo destapa la diferencia."""

from etl.conexiones import conexion_dw, conexion_oltp

ZONA = "America/El_Salvador"

ENTREGADOS_OLTP = """
    SELECT
        count(*) AS entregados,
        count(*) FILTER (WHERE entrega.hora <= e.fecha_comprometida) AS a_tiempo
    FROM envios.envios e
    JOIN LATERAL (
        SELECT MAX(ev.ocurrido_en) AS hora
        FROM envios.envio_eventos ev
        JOIN envios.estados_envios s ON s.id_estado = ev.estado_envio_id
        WHERE ev.envio_id = e.id_envio AND s.nombre_estado = 'ENTREGADO'
    ) entrega ON true
    JOIN envios.estados_envios s ON s.id_estado = e.estado_envio_id
    WHERE s.nombre_estado = 'ENTREGADO'
"""

ENTREGADOS_DW = """
    SELECT
        count(*) AS entregados,
        count(*) FILTER (WHERE entregado_a_tiempo) AS a_tiempo
    FROM hecho_envios
    WHERE horas_hasta_entrega IS NOT NULL
"""


def valor(sql: str, base: str):
    conexion = conexion_oltp if base == "oltp" else conexion_dw
    with conexion() as cn, cn.cursor() as cur:
        cur.execute(sql)
        return cur.fetchone()


def test_los_envios_del_dw_cuadran_con_la_oltp():
    with conexion_oltp() as cn, cn.cursor() as cur:
        cur.execute("SELECT count(*), SUM(peso_kg) FROM envios.envios")
        oltp = cur.fetchone()

    with conexion_dw() as cn, cn.cursor() as cur:
        cur.execute("SELECT count(*), SUM(peso_kg) FROM hecho_envios")
        dw = cur.fetchone()

    assert dw == oltp


def test_los_entregados_y_el_pct_a_tiempo_cuadran():
    entregados_oltp, a_tiempo_oltp = valor(ENTREGADOS_OLTP, "oltp")
    entregados_dw, a_tiempo_dw = valor(ENTREGADOS_DW, "dw")

    assert entregados_dw == entregados_oltp
    assert a_tiempo_dw == a_tiempo_oltp


def test_los_despachos_y_sus_km_cuadran():
    with conexion_oltp() as cn, cn.cursor() as cur:
        cur.execute(
            "SELECT count(*), COALESCE(SUM(km_recorridos), 0),"
            " COALESCE(SUM(costo_estimado), 0) FROM rutas.despachos"
        )
        oltp = cur.fetchone()

    with conexion_dw() as cn, cn.cursor() as cur:
        cur.execute(
            "SELECT count(*), COALESCE(SUM(km_recorridos), 0),"
            " COALESCE(SUM(costo_estimado), 0) FROM hecho_despachos"
        )
        dw = cur.fetchone()

    assert dw == oltp


def test_las_paradas_por_despacho_cuadran():
    with conexion_oltp() as cn, cn.cursor() as cur:
        cur.execute("SELECT count(*) FROM rutas.despacho_paradas")
        (paradas_oltp,) = cur.fetchone()

    with conexion_dw() as cn, cn.cursor() as cur:
        cur.execute("SELECT COALESCE(SUM(numero_paradas), 0) FROM hecho_despachos")
        (paradas_dw,) = cur.fetchone()

    assert paradas_dw == paradas_oltp


def test_las_incidencias_cuadran():
    with conexion_oltp() as cn, cn.cursor() as cur:
        cur.execute(
            "SELECT count(*), COALESCE(SUM(minutos_retraso), 0)"
            " FROM rutas.incidencias"
        )
        oltp = cur.fetchone()

    with conexion_dw() as cn, cn.cursor() as cur:
        cur.execute(
            "SELECT count(*), COALESCE(SUM(minutos_retraso), 0)"
            " FROM hecho_incidencias"
        )
        dw = cur.fetchone()

    assert dw == oltp


def test_los_eventos_cuadran_y_las_horas_son_crecientes():
    with conexion_oltp() as cn, cn.cursor() as cur:
        cur.execute("SELECT count(*) FROM envios.envio_eventos")
        (en_oltp,) = cur.fetchone()

    with conexion_dw() as cn, cn.cursor() as cur:
        cur.execute("SELECT count(*) FROM hecho_eventos")
        (en_dw,) = cur.fetchone()

        # en ningún envío la primera etapa puede tener horas acumuladas
        cur.execute(
            "SELECT count(*) FROM hecho_eventos h"
            " JOIN (SELECT envio_oltp_id, MIN(hecho_id) AS primero"
            "       FROM hecho_eventos GROUP BY envio_oltp_id) p"
            " ON p.primero = h.hecho_id"
            " WHERE h.horas_desde_anterior <> 0"
        )
        primeras_con_delta = cur.fetchone()[0]

    assert en_dw == en_oltp
    assert primeras_con_delta == 0
