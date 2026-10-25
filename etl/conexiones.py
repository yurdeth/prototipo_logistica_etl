"""Conexiones a las bases del pipeline: OLTP (solo lectura) y DW (escritura)."""

import psycopg

from etl.config import ajustes
from neo4j import GraphDatabase


def conexion_oltp() -> psycopg.Connection:
    """Conexión de solo lectura a la operación; readonly a nivel de sesión
    además del permiso del rol: doble candado contra escritura accidental."""
    a = ajustes()

    return psycopg.connect(
        host=a.etl_db_host,
        port=a.etl_db_port,
        dbname=a.etl_db_database,
        user=a.etl_db_username,
        password=a.etl_db_password,
        # Evita escrituras accidentales a nivel de sesión.
        options="-c default_transaction_read_only=on",
    )


def conexion_dw() -> psycopg.Connection:
    a = ajustes()

    return psycopg.connect(
        host=a.dw_db_host,
        port=a.dw_db_port,
        dbname=a.dw_db_database,
        user=a.dw_db_username,
        password=a.dw_db_password,
    )

def conexion_neo4j():
    """Driver de Neo4j; úsalo con `with` para que se cierre solo."""
    a = ajustes()
    driver = GraphDatabase.driver(a.neo4j_uri, auth=(a.neo4j_user, a.neo4j_password))
    # Comprueba que Neo4j esté disponible antes de continuar.
    driver.verify_connectivity()
    return driver
