"""Verify: cuadre final de la corrida, reportado al concluir el proceso.

Compara tres fronteras de conteos, una frontera de agregados y los escenarios:

  OLTP ↔ staging      cada consulta de extract contra el conteo de su st_*
  staging ↔ hechos    cada fuente contra el hecho que la reconstruye
  agregados           sumas espejo OLTP ↔ DW: envíos (conteo y peso),
                      entregados y a tiempo, despachos (conteo, km y costo)
                      e incidencias (conteo y minutos de retraso)
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
    ("st_incidencias", "hecho_incidencias"),
]

# agregados espejo OLTP ↔ DW: mismas filas y mismos totales, no solo conteos
ENTREGADOS_OLTP = """
    SELECT
        count(*) AS entregados,
        count(*) FILTER (WHERE entrega.hora <= e.fecha_comprometida) AS a_tiempo
    FROM envios.envios e
    JOIN LATERAL (
        SELECT MAX(ev.ocurrido_en) AS hora
        FROM envios.envio_eventos ev
        JOIN envios.estados_envios s ON s.id_estado = ev.estado_envio_id
        WHERE ev.envio_id = e.id_envio AND s.nombre_estado = 'ENTREGADO'
    ) entrega ON true
    JOIN envios.estados_envios s ON s.id_estado = e.estado_envio_id
    WHERE s.nombre_estado = 'ENTREGADO'
"""

ENTREGADOS_DW = """
    SELECT
        count(*) AS entregados,
        count(*) FILTER (WHERE entregado_a_tiempo) AS a_tiempo
    FROM hecho_envios
    WHERE horas_hasta_entrega IS NOT NULL
"""

AGREGADOS = [
    ("envios: conteo y peso",
     "SELECT count(*), SUM(peso_kg) FROM envios.envios",
     "SELECT count(*), SUM(peso_kg) FROM hecho_envios"),
    ("entregados y a tiempo",
     ENTREGADOS_OLTP,
     ENTREGADOS_DW),
    ("despachos: conteo, km y costo",
     "SELECT count(*), COALESCE(SUM(km_recorridos), 0),"
     " COALESCE(SUM(costo_estimado), 0) FROM rutas.despachos",
     "SELECT count(*), COALESCE(SUM(km_recorridos), 0),"
     " COALESCE(SUM(costo_estimado), 0) FROM hecho_despachos"),
    ("incidencias: conteo y minutos",
     "SELECT count(*), COALESCE(SUM(minutos_retraso), 0) FROM rutas.incidencias",
     "SELECT count(*), COALESCE(SUM(minutos_retraso), 0) FROM hecho_incidencias"),
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
    """Ejecuta el cuadre completo; `correcto` resume todas las fronteras."""
    with conexion_oltp() as cn_oltp, cn_oltp.cursor() as cur_oltp, \
         conexion_dw() as cn_dw, cn_dw.cursor() as cur_dw:

        oltp = _contar_oltp(cur_oltp)
        staging, hechos, escenarios = _contar_dw(cur_dw)

        agregados: dict[str, dict[str, tuple]] = {}
        for nombre, sql_oltp, sql_dw in AGREGADOS:
            cur_oltp.execute(sql_oltp)
            agregados[nombre] = {"oltp": cur_oltp.fetchone()}
            cur_dw.execute(sql_dw)
            agregados[nombre]["dw"] = cur_dw.fetchone()

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
        "agregados": agregados,
        "escenarios": {"esperados": list(ESCENARIOS), "registrados": escenarios},
        "correcto": all(
            fila["oltp"] == fila["staging"] for fila in tablas.values()
        )
        and all(fila["staging"] == fila["hecho"] for fila in frontera_hechos.values())
        and all(fila["oltp"] == fila["dw"] for fila in agregados.values())
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
    for nombre, fila in reporte["agregados"].items():
        marca = "ok" if fila["oltp"] == fila["dw"] else "DIFIERE"
        print(f"{nombre:32} oltp {fila['oltp']}  dw {fila['dw']}  {marca}")
    print(
        "escenarios:",
        ", ".join(reporte["escenarios"]["registrados"]) or "(ninguno)",
        "— ok" if reporte["correcto"] else "— DIFIERE",
    )
    raise SystemExit(0 if reporte["correcto"] else 1)
