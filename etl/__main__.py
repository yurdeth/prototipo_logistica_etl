"""Corrida completa del ETL en un solo comando: `python -m etl`.

Ejecuta en orden las etapas del pipeline y reporta los conteos de cada una.
Si una etapa falla, la corrida se detiene ahí mismo sin ejecutar las
siguientes; cada etapa es responsable de su propia transacción, y las que
dependen del estado anterior (dimensiones antes que hechos, grafo antes que
escenarios) se ejecutan en este orden por construcción. La corrida termina
con la verificación de cuadre: si alguna frontera difiere, el proceso sale
con error.
"""

import sys
import time

from etl.extract.extractor import extraer_todo
from etl.load.escenarios import ejecutar_escenarios
from etl.load.grafo import cargar_grafo
from etl.migrar import migrar
from etl.transform.dimensiones import cargar_dimensiones
from etl.transform.hechos import cargar_hechos
from etl.verify.cuadre import cuadrar


def correr_todo() -> dict[str, dict]:
    """Ejecuta la corrida completa y devuelve el reporte por etapa."""
    reporte: dict[str, dict] = {}

    def etapa(nombre: str, funcion):
        inicio = time.perf_counter()
        resultado = funcion()
        reporte[nombre] = {
            "resultado": resultado,
            "segundos": round(time.perf_counter() - inicio, 2),
        }
        print(f"\n[{nombre}] terminó en {reporte[nombre]['segundos']} s")

    etapa("migraciones", migrar)
    print(f"  aplicadas: {reporte['migraciones']['resultado'] or 'ninguna (al día)'}")

    etapa("extract", extraer_todo)
    for tabla, filas in reporte["extract"]["resultado"].items():
        print(f"  {tabla:24} {filas:>7} filas")

    etapa("dimensiones", cargar_dimensiones)
    for tabla, filas in reporte["dimensiones"]["resultado"].items():
        print(f"  {tabla:24} {filas:>7}")

    etapa("hechos", cargar_hechos)
    for tabla, filas in reporte["hechos"]["resultado"].items():
        print(f"  {tabla:24} {filas:>7}")

    etapa("grafo", cargar_grafo)
    for tipo, filas in reporte["grafo"]["resultado"].items():
        print(f"  {tipo:24} {filas:>7} escritos")

    etapa("escenarios", ejecutar_escenarios)
    for escenario in reporte["escenarios"]["resultado"]:
        nota = (
            f" (tramo afectado: {escenario['tramo_afectado']})"
            if escenario["tramo_afectado"]
            else ""
        )
        km = "sin ruta" if escenario["km_totales"] is None else f"{escenario['km_totales']} km"
        minutos = "sin ruta" if escenario["minutos_totales"] is None else f"{escenario['minutos_totales']} min"
        print(
            f"  {escenario['escenario']:11} {escenario['origen']} → {escenario['destino']}:"
            f" {escenario['ruta']}, {km}, {minutos}{nota}"
        )

    etapa("verificación", cuadrar)
    verificacion = reporte["verificación"]["resultado"]
    for tabla, fila in verificacion["tablas"].items():
        marca = "ok" if fila["oltp"] == fila["staging"] else "DIFIERE"
        print(f"  {tabla:24} oltp {fila['oltp']:>7}  staging {fila['staging']:>7}  {marca}")
    for hecho, fila in verificacion["hechos"].items():
        marca = "ok" if fila["staging"] == fila["hecho"] else "DIFIERE"
        print(f"  {hecho:24} staging {fila['staging']:>7}  hecho {fila['hecho']:>7}  {marca}")
    for nombre, fila in verificacion["agregados"].items():
        marca = "ok" if fila["oltp"] == fila["dw"] else "DIFIERE"
        print(f"  {nombre:32} oltp {fila['oltp']}  dw {fila['dw']}  {marca}")
    print(
        "  escenarios de la corrida:",
        ", ".join(verificacion["escenarios"]["registrados"]) or "(ninguno)",
    )

    if not verificacion["correcto"]:
        print("\nCUADRE FINAL: DIFIERE — la corrida termina con error")
        sys.exit(1)

    print("\nCUADRE FINAL: ok")
    return reporte


if __name__ == "__main__":
    correr_todo()
