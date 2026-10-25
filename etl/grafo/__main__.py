"""Uso: uv run python -m etl.grafo"""

from etl.conexiones import conexion_neo4j
from etl.grafo.esquema import crear_restricciones
from etl.grafo.nodos import cargar_nodos
from etl.grafo.relaciones import cargar_relaciones

if __name__ == "__main__":
    # Abre la conexión y garantiza su cierre al finalizar.
    with conexion_neo4j() as driver:
        # Crea las restricciones necesarias para mantener la integridad del grafo.
        crear_restricciones(driver)
        # Carga los nodos e informa cuántos se procesaron por etiqueta.
        for etiqueta, n in cargar_nodos(driver).items():
            print(f"nodos {etiqueta}: {n}")
        # Carga las relaciones entre nodos e informa cuántas se procesaron por tipo.
        for tipo, n in cargar_relaciones(driver).items():
            print(f"relaciones {tipo}: {n}")