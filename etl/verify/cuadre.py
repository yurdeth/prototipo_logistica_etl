"""Verify: cuadre final de la corrida, reportado al concluir el proceso.

Compara tres fronteras:

  OLTP ↔ staging      cada consulta de extract contra el conteo de su st_*
  staging ↔ hechos    cada fuente contra el hecho que la reconstruye
  escenarios          la última corrida debe dejar los tres (base, bloqueo,
                      congestión) registrados en resultado_escenario

Devuelve un reporte con los conteos y `correcto` en True solo si todas las
fronteras cuadran; el orquestador lo imprime al cierre y termina con error
si algo no cuadra.
"""

from etl.conexiones import conexion_dw, conexion_oltp
from etl.extract.consultas import CONSULTAS

# fuente de staging → hecho que la reconstruye
FUENTES_HECHOS = [
    ("st_envios", "hecho_envios"),
    ("st_despachos", "hecho_despachos"),
    ("st_envio_eventos", "hecho_eventos"),
]

ESCENARIOS = ("base", "bloqueo", "congestion")
# el registro es append-only y se consulta del más reciente al más antiguo


def _contar_oltp(cur) -> dict[str, int]:
    """Conteo por fuente usando las mismas consultas del extract."""
    conteos: dict[str, int] = {}
    for tabla, consulta in CONSULTAS.items():
        cur.execute(f"SELECT count(*) FROM ({consulta}) fuente")  # noqa: S608
        conteos[tabla] = int(cur.fetchone()[0])
    return conteos


def _contar_dw(cur) -> tuple[dict[str, int], dict[str, int], list[str]]:
    """Conteos de staging y de hechos, más los escenarios de la última corrida."""
    staging: dict[str, int] = {}
    for tabla in CONSULTAS:
        cur.execute(f"SELECT count(*) FROM {tabla}")  # noqa: S608
        staging[tabla] = int(cur.fetchone()[0])

    hechos: dict[str, int] = {}
    for _, hecho in FUENTES_HECHOS:
        cur.execute(f"SELECT count(*) FROM {hecho}")  # noqa: S608
        hechos[hecho] = int(cur.fetchone()[0])

    cur.execute(
        "SELECT escenario FROM resultado_escenario"
        " ORDER BY calculado_en DESC, id DESC"
        f" LIMIT {len(ESCENARIOS)}"
    )
    escenarios = [fila[0] for fila in cur.fetchall()]

    return staging, hechos, escenarios


def cuadrar() -> dict:
    """Ejecuta el cuadre completo; `correcto` resume las tres fronteras."""
    with conexion_oltp() as cn_oltp, cn_oltp.cursor() as cur_oltp, \
         conexion_dw() as cn_dw, cn_dw.cursor() as cur_dw:

        oltp = _contar_oltp(cur_oltp)
        staging, hechos, escenarios = _contar_dw(cur_dw)

    tablas = {
        tabla: {"oltp": oltp[tabla], "staging": staging[tabla]}
        for tabla in CONSULTAS
    }
    frontera_hechos = {
        hecho: {"staging": staging[fuente], "hecho": hechos[hecho]}
        for fuente, hecho in FUENTES_HECHOS
    }
    escenarios_ok = set(escenarios) == set(ESCENARIOS)

    return {
        "tablas": tablas,
        "hechos": frontera_hechos,
        "escenarios": {"esperados": list(ESCENARIOS), "registrados": escenarios},
        "correcto": all(
            fila["oltp"] == fila["staging"] for fila in tablas.values()
        )
        and all(fila["staging"] == fila["hecho"] for fila in frontera_hechos.values())
        and escenarios_ok,
    }


if __name__ == "__main__":
    reporte = cuadrar()
    for tabla, fila in reporte["tablas"].items():
        marca = "ok" if fila["oltp"] == fila["staging"] else "DIFIERE"
        print(f"{tabla:24} oltp {fila['oltp']:>7}  staging {fila['staging']:>7}  {marca}")
    for hecho, fila in reporte["hechos"].items():
        marca = "ok" if fila["staging"] == fila["hecho"] else "DIFIERE"
        print(f"{hecho:24} staging {fila['staging']:>7}  hecho {fila['hecho']:>7}  {marca}")
    print(
        "escenarios:",
        ", ".join(reporte["escenarios"]["registrados"]) or "(ninguno)",
        "— ok" if reporte["correcto"] else "— DIFIERE",
    )
    raise SystemExit(0 if reporte["correcto"] else 1)
