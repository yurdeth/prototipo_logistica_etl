"""La corrida completa ejecuta las seis etapas en orden y reporta conteos."""

from etl import __main__ as orquestador

ETAPAS_ESPERADAS = [
    "migraciones",
    "extract",
    "dimensiones",
    "hechos",
    "grafo",
    "escenarios",
]


def test_corrida_completa_ejecuta_todas_las_etapas():
    reporte = orquestador.correr_todo()

    assert list(reporte) == ETAPAS_ESPERADAS
    assert reporte["extract"]["resultado"]["st_envios"] > 0
    assert reporte["hechos"]["resultado"]["hecho_envios"] > 0
    assert len(reporte["escenarios"]["resultado"]) == 3


def test_corrida_es_idempotente_en_dimensiones():
    orquestador.correr_todo()
    reporte = orquestador.correr_todo()

    # segunda corrida: foto completa de hechos pero ninguna dimensión nueva
    for tabla, filas in reporte["dimensiones"]["resultado"].items():
        if not tabla.endswith("_total"):
            assert filas == 0, f"{tabla} no debería agregar filas en la segunda corrida"
    assert reporte["hechos"]["resultado"]["hecho_envios"] > 0
