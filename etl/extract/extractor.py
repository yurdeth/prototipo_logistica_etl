"""Extract: copia cada fuente de la OLTP a su tabla de staging en el DW.

El volumen del prototipo (decenas de miles de filas) se mueve con COPY, que
es el camino rápido de PostgreSQL; el corte es siempre completo: staging se
trunca y se rellena entero en cada corrida.
"""

import psycopg

from etl.conexiones import conexion_dw, conexion_oltp
from etl.extract.consultas import CONSULTAS


def extraer_tabla(nombre_tabla: str, cur_oltp: psycopg.Cursor, cur_dw: psycopg.Cursor) -> int:
    """Trunca la tabla de staging y la llena con COPY desde la OLTP.
    Devuelve la cantidad de filas copiadas."""

    columnas = _columnas_de(cur_dw, nombre_tabla)

    cur_dw.execute(f"TRUNCATE TABLE {nombre_tabla}")  # noqa: S608

    cur_oltp.execute(CONSULTAS[nombre_tabla])

    with cur_dw.copy(f"COPY {nombre_tabla} ({', '.join(columnas)}) FROM STDIN") as copia:  # noqa: S608
        for fila in cur_oltp:
            copia.write_row(fila)

    cur_dw.execute(f"SELECT count(*) FROM {nombre_tabla}")  # noqa: S608
    (total,) = cur_dw.fetchone()
    return int(total)


def _columnas_de(cur_dw: psycopg.Cursor, nombre_tabla: str) -> list[str]:
    cur_dw.execute(
        "SELECT column_name FROM information_schema.columns"
        " WHERE table_schema = 'public' AND table_name = %s"
        " ORDER BY ordinal_position",
        (nombre_tabla,),
    )
    return [fila[0] for fila in cur_dw.fetchall()]


def extraer_todo() -> dict[str, int]:
    """Ejecuta el extract completo; devuelve filas copiadas por tabla."""
    resumen: dict[str, int] = {}

    with conexion_oltp() as cn_oltp, cn_oltp.cursor() as cur_oltp, \
         conexion_dw() as cn_dw, cn_dw.cursor() as cur_dw:

        for nombre_tabla in CONSULTAS:
            resumen[nombre_tabla] = extraer_tabla(nombre_tabla, cur_oltp, cur_dw)

    return resumen


if __name__ == "__main__":
    for tabla, filas in extraer_todo().items():
        print(f"{tabla:24} {filas:>7} filas")
