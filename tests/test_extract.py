"""El extract copia la OLTP completa a staging: los conteos deben cuadrar
tabla por tabla en cada corrida. Sin cuadre, todo el DW posterior miente."""

from etl.conexiones import conexion_dw, conexion_oltp
from etl.extract.consultas import CONSULTAS
from etl.extract.extractor import extraer_todo


def test_extract_cuadra_los_conteos_con_la_oltp():
    resumen = extraer_todo()

    with conexion_oltp() as cn_oltp, cn_oltp.cursor() as cur_oltp, \
         conexion_dw() as cn_dw, cn_dw.cursor() as cur_dw:

        for tabla, consulta in CONSULTAS.items():
            cur_oltp.execute(f"SELECT count(*) FROM ({consulta}) fuente")  # noqa: S608
            (en_oltp,) = cur_oltp.fetchone()

            cur_dw.execute(f"SELECT count(*) FROM {tabla}")  # noqa: S608
            (en_staging,) = cur_dw.fetchone()

            assert en_staging == en_oltp, f"{tabla}: staging {en_staging} != OLTP {en_oltp}"


def test_extract_trae_datos_reales():
    resumen = extraer_todo()

    # la operación demo no está vacía; si algún día lo estuviera, este test
    # avisa antes de que el transform construya un DW fantasma
    assert resumen["st_envios"] > 0
    assert resumen["st_envio_eventos"] > resumen["st_envios"]  # el rastro mínimo es >1 evento por envío
    assert resumen["st_conexiones"] > 0


def test_extract_es_recorrible_dos_veces():
    # corrida duplicada: staging se trunca y rellena, no se acumula
    primera = extraer_todo()
    segunda = extraer_todo()

    assert primera == segunda
