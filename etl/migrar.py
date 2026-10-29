"""Aplica en orden los .sql de la carpeta sql/ que falten en sql_versiones."""

import re
from pathlib import Path

from etl.conexiones import conexion_dw

CARPETA_SQL = Path(__file__).resolve().parent.parent / "sql"

PATRON_VERSION = re.compile(r"^(\d+)_.*\.sql$")


def pendientes() -> list[tuple[int, Path]]:
    """Migraciones del repo que aún no aparecen en sql_versiones, en orden."""
    with conexion_dw() as cn, cn.cursor() as cur:
        cur.execute("SELECT version FROM sql_versiones")
        aplicadas = {fila[0] for fila in cur.fetchall()}

    migraciones = []
    for archivo in sorted(CARPETA_SQL.glob("*.sql")):
        coincidencia = PATRON_VERSION.match(archivo.name)
        if coincidencia and int(coincidencia.group(1)) not in aplicadas:
            migraciones.append((int(coincidencia.group(1)), archivo))

    return migraciones


def migrar() -> list[int]:
    """Aplica las migraciones pendientes, cada una en su transacción."""
    aplicadas = []

    for version, archivo in pendientes():
        with conexion_dw() as cn, cn.cursor() as cur:
            # Las migraciones crean la estructura con nombres cualificados y
            # ejecutan con search_path en public, de modo que el resultado
            # sea idéntico en instalaciones nuevas y ya migradas.
            cur.execute("SET search_path TO public")
            cur.execute(archivo.read_text(encoding="utf-8"))
            cur.execute(
                "INSERT INTO sql_versiones (version, archivo) VALUES (%s, %s)",
                (version, archivo.name),
            )
        aplicadas.append(version)

    return aplicadas


if __name__ == "__main__":
    for version in migrar():
        print(f"aplicada sql_versiones {version}")
