"""Prueba de la frontera rectora del proyecto: el ETL lee la operación y
NUNCA escribe en ella. La sesión es readonly y el rol etl_reader no tiene
permisos de escritura; si cualquiera de los dos candados fallara, este test
grita."""

import psycopg
import pytest

from etl.conexiones import conexion_oltp

TABLAS_CLAVE = [
    "envios.envios",
    "envios.envio_eventos",
    "envios.clientes",
    "rutas.despachos",
    "rutas.conexiones",
]


def test_lee_las_tablas_clave_de_la_oltp():
    with conexion_oltp() as cn, cn.cursor() as cur:
        for tabla in TABLAS_CLAVE:
            cur.execute(f"SELECT count(*) FROM {tabla}")  # noqa: S608
            (total,) = cur.fetchone()
            assert total >= 0


def test_etl_reader_no_puede_escribir_en_la_oltp():
    with conexion_oltp() as cn, cn.cursor() as cur:
        # Readonly de sesión (ReadOnlySqlTransaction) o de rol (InsufficientPrivilege):
        # cualquiera de los dos candados basta para rechazar la escritura.
        with pytest.raises((psycopg.errors.ReadOnlySqlTransaction, psycopg.errors.InsufficientPrivilege)):
            cur.execute(
                "INSERT INTO envios.clientes (nombre, tipo_cliente, territorio_id)"
                " VALUES ('prueba etl', 'PERSONA', 1)"
            )
