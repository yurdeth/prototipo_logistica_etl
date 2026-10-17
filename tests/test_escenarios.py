"""Los escenarios son la demostración: sin bloqueo el grafo elige la directa;
con la conexión bloqueada se desvía por Sonsonate; con congestión mantiene la
ruta pero paga la penalización. Y cada corrida queda registrada en el DW."""

from etl.config import ajustes
from etl.load.escenarios import ejecutar_escenarios, leer_conexiones, ruta_optima
from neo4j import GraphDatabase
import psycopg

ID_CONGESTIONADO = 1  # SS -> SAN, según el parámetro conexion_congestion de la red


def test_la_ruta_base_es_la_directa():
    resultado = ruta_optima(leer_conexiones(), "SUC-SSS", "SUC-SAN")

    assert resultado["ruta"] == "SUC-SSS -> SUC-SAN"


def test_con_la_conexion_bloqueada_se_desvia_por_sonsonate():
    resultado = ruta_optima(leer_conexiones(), "SUC-SSS", "SUC-SAN", excluir_ids={ID_CONGESTIONADO})

    assert "SUC-SON" in resultado["ruta"]
    assert resultado["km"] > 49  # el desvío cuesta kilómetros


def test_con_congestion_mantiene_la_ruta_y_paga_la_penalizacion():
    conexiones = leer_conexiones()
    base = ruta_optima(conexiones, "SUC-SSS", "SUC-SAN")
    congestión = ruta_optima(conexiones, "SUC-SSS", "SUC-SAN", penalizar={ID_CONGESTIONADO: 15})

    assert congestión["ruta"] == base["ruta"]
    assert congestión["minutos"] == base["minutos"] + 15


def test_los_escenarios_quedan_registrados_en_el_dw():
    ejecutar_escenarios()

    with psycopg.connect(
        host=ajustes().dw_db_host,
        port=ajustes().dw_db_port,
        dbname=ajustes().dw_db_database,
        user=ajustes().dw_db_username,
        password=ajustes().dw_db_password,
    ) as cn, cn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM resultado_escenario"
            " WHERE escenario IN ('base', 'bloqueo', 'congestion')"
        )
        (total,) = cur.fetchone()
        assert total >= 3

        cur.execute(
            "SELECT ruta FROM resultado_escenario"
            " WHERE escenario = 'bloqueo' ORDER BY id DESC LIMIT 1"
        )
        (ruta_bloqueo,) = cur.fetchone()
        assert "SUC-SON" in ruta_bloqueo
