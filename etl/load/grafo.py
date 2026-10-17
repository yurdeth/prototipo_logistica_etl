"""Carga del grafo logístico en Neo4j desde staging.

MERGE por clave natural (codigo de sucursal, id de conexión): re-corrida
no duplica, solo refresca propiedades. La propiedad `activa` de cada arista
es la que usa el escenario de bloqueo.
"""

from neo4j import GraphDatabase

from etl.config import ajustes
from etl.conexiones import conexion_dw

NODOS = """
    SELECT codigo, nombre_sucursal, latitud, longitud
    FROM st_sucursales ORDER BY id_sucursal
"""

ARISTAS = """
    SELECT c.id_conexion, so.codigo AS origen, sd.codigo AS destino,
           c.distancia_km, c.tiempo_min, c.activa
    FROM st_conexiones c
    JOIN st_sucursales so ON so.id_sucursal = c.origen_sucursal_id
    JOIN st_sucursales sd ON sd.id_sucursal = c.destino_sucursal_id
    ORDER BY c.id_conexion
"""

MERGE_SUCURSAL = """
    MERGE (s:Sucursal {codigo: $codigo})
    SET s.nombre = $nombre, s.latitud = $latitud, s.longitud = $longitud
"""

MERGE_CONEXION = """
    MATCH (o:Sucursal {codigo: $origen}), (d:Sucursal {codigo: $destino})
    MERGE (o)-[c:CONECTA {id_conexion: $id_conexion}]->(d)
    SET c.distancia_km = $distancia_km, c.tiempo_min = $tiempo_min,
        c.activa = $activa
"""


def cargar_grafo() -> dict[str, int]:
    """Carga sucursales y conexiones; devuelve conteos escritos."""
    a = ajustes()
    escritos: dict[str, int] = {}

    with GraphDatabase.driver(a.neo4j_uri, auth=(a.neo4j_user, a.neo4j_password)) as driver:
        driver.verify_connectivity()

        with driver.session() as sesion, conexion_dw() as cn, cn.cursor() as cur:
            cur.execute(NODOS)
            for codigo, nombre, latitud, longitud in cur.fetchall():
                sesion.execute_write(
                    lambda tx: tx.run(MERGE_SUCURSAL, codigo=codigo, nombre=nombre,
                                      latitud=float(latitud), longitud=float(longitud)).consume()
                )
                escritos["sucursales"] = escritos.get("sucursales", 0) + 1

            cur.execute(ARISTAS)
            for id_conexion, origen, destino, km, minutos, activa in cur.fetchall():
                sesion.execute_write(
                    lambda tx: tx.run(MERGE_CONEXION, id_conexion=id_conexion, origen=origen,
                                      destino=destino, distancia_km=float(km),
                                      tiempo_min=int(minutos), activa=bool(activa)).consume()
                )
                escritos["conexiones"] = escritos.get("conexiones", 0) + 1

    return escritos


if __name__ == "__main__":
    for tipo, filas in cargar_grafo().items():
        print(f"{tipo:12} {filas:>4} escritos")
