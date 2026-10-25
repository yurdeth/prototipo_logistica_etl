"""Aplica en orden los .sql pendientes y registra las versiones ejecutadas."""

import re
from pathlib import Path

from etl.conexiones import conexion_dw

CARPETA_SQL = Path(__file__).resolve().parent.parent / "sql"
PATRON_VERSION = re.compile(r"^(\d+)_.*\.sql$")


def inicializar_control() -> None:
    """Crea la tabla de control si todavía no existe."""
    with conexion_dw() as cn, cn.cursor() as cur:
        # Registra la versión, el archivo ejecutado y la fecha de aplicación
        cur.execute("""
            CREATE TABLE IF NOT EXISTS public.sql_versiones (
                version INTEGER PRIMARY KEY,
                archivo TEXT NOT NULL,
                aplicada_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)


def pendientes() -> list[tuple[int, Path]]:
    """Migraciones del repo que aún no aparecen en sql_versiones, en orden."""
    with conexion_dw() as cn, cn.cursor() as cur:
        cur.execute("SELECT version FROM public.sql_versiones")
        aplicadas = {fila[0] for fila in cur.fetchall()}

    migraciones = []
    # Identifica los archivos SQL numerados que todavía no se han ejecutado.
    for archivo in sorted(CARPETA_SQL.glob("*.sql")):
        coincidencia = PATRON_VERSION.match(archivo.name)
        if coincidencia and int(coincidencia.group(1)) not in aplicadas:
            migraciones.append((int(coincidencia.group(1)), archivo))

    return migraciones


def migrar() -> list[int]:
    """Aplica las migraciones pendientes, cada una en su transacción."""
    inicializar_control()
    aplicadas = []

    for version, archivo in pendientes():
        with conexion_dw() as cn, cn.cursor() as cur:
            # Ejecuta el SQL y registra su versión en la misma transacción.
            cur.execute(archivo.read_text(encoding="utf-8"))
            cur.execute(
                "INSERT INTO public.sql_versiones (version, archivo) VALUES (%s, %s)",
                (version, archivo.name),
            )
        aplicadas.append(version)

    return aplicadas


if __name__ == "__main__":
    # Informa las migraciones que se aplicaron correctamente.
    for version in migrar():
        print(f"Aplicada migración {version}")