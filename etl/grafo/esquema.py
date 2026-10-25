"""Restricciones de unicidad: hacen los MERGE idempotentes y rápidos."""

ETIQUETAS = ["Territorio", "Sucursal", "Cliente", "Conductor", "Vehiculo", "Estado"]


def crear_restricciones(driver) -> None:
    # Crea una restricción de unicidad para cada tipo de nodo.
    for etiqueta in ETIQUETAS:
        driver.execute_query(
            f"CREATE CONSTRAINT {etiqueta.lower()}_id IF NOT EXISTS "
            f"FOR (n:{etiqueta}) REQUIRE n.id_oltp IS UNIQUE"
        )