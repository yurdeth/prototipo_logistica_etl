"""Contrato de permisos del DW: etl_writer escribe solo en el DW,
etl_reader lo lee para los cuadres y ninguno de los dos toca lo que no debe.
Si un candado se afloja, este test falla antes de que cargue un dato."""

import psycopg
import pytest

from etl.config import ajustes
from etl.conexiones import conexion_dw


def test_etl_writer_crea_y_escribe_en_el_dw():
    try:
        with conexion_dw() as cn, cn.cursor() as cur:
            cur.execute("CREATE TABLE IF NOT EXISTS staging.prueba_permisos (id int)")
            cur.execute("INSERT INTO staging.prueba_permisos VALUES (1)")
            cur.execute("SELECT count(*) FROM staging.prueba_permisos")
            (total,) = cur.fetchone()

        assert total == 1
    finally:
        with conexion_dw() as cn, cn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS staging.prueba_permisos")


def test_etl_writer_no_puede_entrar_a_la_oltp():
    a = ajustes()

    # CONNECT revocado para etl_writer en la base operacional; PostgreSQL
    # lo rechaza como error de privilegio o de conexión según el camino
    with pytest.raises((psycopg.errors.InsufficientPrivilege, psycopg.OperationalError)):
        psycopg.connect(
            host=a.etl_db_host,
            port=a.etl_db_port,
            dbname=a.etl_db_database,
            user=a.dw_db_username,
            password=a.dw_db_password,
            connect_timeout=5,
        )


def test_etl_reader_lee_el_dw():
    # el mismo rol que lee la OLTP verifica los cuadres contra el DW
    with psycopg.connect(
        host=ajustes().dw_db_host,
        port=ajustes().dw_db_port,
        dbname=ajustes().dw_db_database,
        user=ajustes().etl_db_username,
        password=ajustes().etl_db_password,
    ) as cn, cn.cursor() as cur:
        cur.execute("SELECT count(*) FROM sql_versiones")
        (total,) = cur.fetchone()
        assert total >= 1


def test_las_migraciones_son_idempotentes():
    from etl.migrar import migrar

    assert migrar() == []  # re-corrida: nada pendiente, nada duplicado
