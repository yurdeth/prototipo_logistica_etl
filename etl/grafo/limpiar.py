"""Uso: uv run python -m etl.grafo.limpiar"""

from etl.conexiones import conexion_neo4j

if __name__ == "__main__":
    with conexion_neo4j() as driver:
        # Elimina todos los nodos y sus relaciones en lotes de 10 000 registros.
        driver.execute_query(
            "MATCH (n) CALL { WITH n DETACH DELETE n } IN TRANSACTIONS OF 10000 ROWS"
        )

        # Elimina las restricciones existentes para permitir una limpieza completa.
        for nombre in ["cliente_id", "conductor_id", "vehiculo_id", "estado_id", "ruta_id"]:
            driver.execute_query(f"DROP CONSTRAINT {nombre} IF EXISTS")

        print("grafo limpio")