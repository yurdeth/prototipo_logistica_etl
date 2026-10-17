"""Escenarios de optimización de rutas sobre el grafo.

Tres corridas entre San Salvador y Santa Ana, la ruta óptima por Dijkstra
sobre el peso de cada arista:

  base       la red tal cual está
  bloqueo    la conexión directa se excluye (como cuando activa=false)
  congestión la conexión directa conserva su distancia pero su tiempo crece
             por la penalización versionada en rutas.parametros

Cada corrida deja su resultado en resultado_escenario (DW) con la ruta
elegida y sus totales; comparar las tres es la demostración de que el grafo
elige caminos alternativos.
"""

import heapq

from neo4j import GraphDatabase

from etl.config import ajustes
from etl.conexiones import conexion_dw, conexion_oltp

ORIGEN = "SUC-SSS"   # San Salvador
DESTINO = "SUC-SAN"  # Santa Ana

CLAVE_CONGESTION = "conexion_congestion"
CLAVE_PENALIZACION = "penalizacion_congestion"


def leer_conexiones() -> list[dict]:
    a = ajustes()
    with GraphDatabase.driver(a.neo4j_uri, auth=(a.neo4j_user, a.neo4j_password)) as driver:
        with driver.session() as sesion:
            return [
                dict(registro)
                for registro in sesion.run(
                    "MATCH (o:Sucursal)-[c:CONECTA]->(d:Sucursal)"
                    " RETURN c.id_conexion AS id, o.codigo AS origen, d.codigo AS destino,"
                    " c.distancia_km AS km, c.tiempo_min AS minutos, c.activa AS activa"
                )
            ]


def parametros_de_congestion() -> tuple[int, int]:
    """(id_conexion congestionada, minutos de penalización) desde la OLTP."""
    with conexion_oltp() as cn, cn.cursor() as cur:
        # última versión vigente por clave
        cur.execute(
            "SELECT DISTINCT ON (clave) clave, valor::int"
            " FROM rutas.parametros"
            " WHERE clave IN (%s, %s)"
            " ORDER BY clave, vigente_desde DESC",
            (CLAVE_CONGESTION, CLAVE_PENALIZACION),
        )
        valores = {clave: int(valor) for clave, valor in cur.fetchall()}

    return valores[CLAVE_CONGESTION], valores[CLAVE_PENALIZACION]


def ruta_optima(
    conexiones: list[dict],
    origen: str,
    destino: str,
    excluir_ids: set[int] | None = None,
    penalizar: dict[int, int] | None = None,
) -> dict:
    """Dijkstra por tiempo (con distancia de respaldo en el resultado).
    Las conexiones excluidas no se recorren; las penalizadas suman minutos."""
    excluir_ids = excluir_ids or set()
    penalizar = penalizar or {}

    adyacencia: dict[str, list[tuple[str, dict]]] = {}
    for c in conexiones:
        if c["id"] in excluir_ids or not c["activa"]:
            continue
        minutos = c["minutos"] + penalizar.get(c["id"], 0)
        km = c["km"]
        adyacencia.setdefault(c["origen"], []).append(
            (c["destino"], {"minutos": minutos, "km": km, "id": c["id"]})
        )

    cola = [(0, 0, origen, [origen])]
    mejor_km: dict[str, float] = {origen: 0}
    visitados: set[str] = set()

    while cola:
        minutos_acum, km_acum, actual, camino = heapq.heappop(cola)
        if actual in visitados:
            continue
        visitados.add(actual)

        if actual == destino:
            return {"ruta": " -> ".join(camino), "minutos": minutos_acum, "km": round(km_acum, 2)}

        for vecino, arista in adyacencia.get(actual, []):
            if vecino in visitados:
                continue
            heapq.heappush(
                cola,
                (
                    minutos_acum + arista["minutos"],
                    km_acum + arista["km"],
                    vecino,
                    camino + [vecino],
                ),
            )

    return {"ruta": "(sin ruta disponible)", "minutos": 0, "km": 0.0}


def ejecutar_escenarios() -> list[dict]:
    """Corre base/bloqueo/congestión y registra cada resultado en el DW."""
    conexiones = leer_conexiones()
    id_congestion, penalizacion = parametros_de_congestion()

    escenarios = [
        {"escenario": "base", "excluir": set(), "penalizar": {}, "tramo": None},
        {"escenario": "bloqueo", "excluir": {id_congestion}, "penalizar": {}, "tramo": f"conexion {id_congestion}"},
        {
            "escenario": "congestion",
            "excluir": set(),
            "penalizar": {id_congestion: penalizacion},
            "tramo": f"conexion {id_congestion} (+{penalizacion} min)",
        },
    ]

    resultados = []
    for caso in escenarios:
        calculo = ruta_optima(conexiones, ORIGEN, DESTINO, caso["excluir"], caso["penalizar"])
        resultado = {
            "escenario": caso["escenario"],
            "origen": ORIGEN,
            "destino": DESTINO,
            "ruta": calculo["ruta"],
            "km_totales": calculo["km"],
            "minutos_totales": calculo["minutos"],
            "tramo_afectado": caso["tramo"],
            "penalizacion_min": sum(caso["penalizar"].values()),
        }
        resultados.append(resultado)

    with conexion_dw() as cn, cn.cursor() as cur:
        cur.executemany(
            "INSERT INTO resultado_escenario"
            " (escenario, origen, destino, ruta, km_totales,"
            "  minutos_totales, tramo_afectado, penalizacion_min)"
            " VALUES (%(escenario)s, %(origen)s, %(destino)s, %(ruta)s,"
            "         %(km_totales)s, %(minutos_totales)s, %(tramo_afectado)s,"
            "         %(penalizacion_min)s)",
            resultados,
        )

    return resultados


if __name__ == "__main__":
    for r in ejecutar_escenarios():
        print(f"[{r['escenario']:10}] {r['ruta']}  = {r['km_totales']} km / {r['minutos_totales']} min")
