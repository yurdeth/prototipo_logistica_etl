"""El grafo cargado: 8 sucursales y 11 conexiones, y MERGE no duplica —
re-corrida deja exactamente el mismo grafo."""

from etl.config import ajustes
from etl.load.grafo import cargar_grafo
from neo4j import GraphDatabase
import pytest


@pytest.fixture(scope="module")
def driver():
    a = ajustes()
    with GraphDatabase.driver(a.neo4j_uri, auth=(a.neo4j_user, a.neo4j_password)) as d:
        yield d


def test_el_grafo_tiene_la_red_completa(driver):
    cargar_grafo()

    with driver.session() as s:
        nodos = s.run("MATCH (s:Sucursal) RETURN count(s) AS n").single()["n"]
        aristas = s.run("MATCH ()-[r:CONECTA]->() RETURN count(r) AS n").single()["n"]

    assert nodos == 8
    assert aristas == 11


def test_recorrida_no_duplica_nada(driver):
    cargar_grafo()
    cargar_grafo()

    with driver.session() as s:
        nodos = s.run("MATCH (s:Sucursal) RETURN count(s) AS n").single()["n"]
        aristas = s.run("MATCH ()-[r:CONECTA]->() RETURN count(r) AS n").single()["n"]
        sin_codigo = s.run("MATCH (s:Sucursal) WHERE s.codigo IS NULL RETURN count(s) AS n").single()["n"]

    assert nodos == 8
    assert aristas == 11
    assert sin_codigo == 0


def test_las_aristas_traen_pesos_reales_y_activa():
    # el tramo SS→Santa Ana debe existir con distancia geodésica y activa=true
    with GraphDatabase.driver(ajustes().neo4j_uri, auth=(ajustes().neo4j_user, ajustes().neo4j_password)) as d:
        with d.session() as s:
            registro = s.run(
                "MATCH (:Sucursal {codigo: 'SUC-SSS'})-[c:CONECTA]->(:Sucursal {codigo: 'SUC-SAN'})"
                " RETURN c.distancia_km AS km, c.activa AS activa"
            ).single()

    assert registro is not None
    assert 40 < registro["km"] < 70  # recta SS–Santa Ana ≈ 54 km
    assert registro["activa"] is True
