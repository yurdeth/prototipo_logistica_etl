"""El cuadre final reporta las tres fronteras y cuadra tras una corrida."""

from etl.verify.cuadre import ESCENARIOS, cuadrar


def test_cuadre_cuadra_tras_la_corrida():
    reporte = cuadrar()

    assert reporte["correcto"] is True
    for tabla, fila in reporte["tablas"].items():
        assert fila["oltp"] == fila["staging"], f"{tabla} difiere entre OLTP y staging"
    for hecho, fila in reporte["hechos"].items():
        assert fila["staging"] == fila["hecho"], f"{hecho} difiere de su fuente"
    for nombre, fila in reporte["agregados"].items():
        assert fila["oltp"] == fila["dw"], f"agregado {nombre} difiere entre OLTP y DW"


def test_la_ultima_corrida_dejo_los_tres_escenarios():
    reporte = cuadrar()

    # el orden del registro es del más reciente al más antiguo
    assert set(reporte["escenarios"]["registrados"]) == set(ESCENARIOS)
    assert reporte["escenarios"]["esperados"] == list(ESCENARIOS)
