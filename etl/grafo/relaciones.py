"""Relaciones entre nodos ya cargados."""

from etl.grafo.nodos import LOTE, _leer

# Define el tipo de relación, los nodos involucrados y la consulta SQL.
# El SQL devuelve los identificadores de origen y destino, y propiedades opcionales.
RELACIONES = [
    # Relaciones basadas en claves foráneas.
    ("UBICADA_EN", "Sucursal", "Territorio",
        "SELECT s.id_sucursal_oltp AS origen_id, t.id_territorio_oltp AS destino_id "
        "FROM public.dim_sucursal s "
        "JOIN public.dim_territorio t ON t.id_territorio_sk = s.territorio_sk"),
    ("UBICADO_EN", "Cliente", "Territorio",
        "SELECT c.id_cliente_oltp AS origen_id, t.id_territorio_oltp AS destino_id "
        "FROM public.dim_cliente c "
        "JOIN public.dim_territorio t ON t.id_territorio_sk = c.territorio_sk"),

    # Relaciones por texto que deben verificarse para evitar coincidencias incorrectas.
    ("RUTA", "Sucursal", "Sucursal",
        "SELECT so.id_sucursal_oltp AS origen_id, sd.id_sucursal_oltp AS destino_id, "
        "r.id_conexion_oltp AS id_oltp, r.distancia_km::float8 AS distancia_km, r.tiempo_min "
        "FROM public.dim_ruta r "
        "JOIN public.dim_sucursal so ON so.nombre = r.origen "
        "JOIN public.dim_sucursal sd ON sd.nombre = r.destino"),
    ("BASE_EN", "Conductor", "Sucursal",
        "SELECT c.id_empleado_oltp AS origen_id, s.id_sucursal_oltp AS destino_id "
        "FROM public.dim_conductor c "
        "JOIN public.dim_sucursal s ON s.nombre = c.sucursal_base"),
]


def cargar_relaciones(driver) -> dict[str, int]:
    conteos = {}
    for tipo, origen, destino, sql in RELACIONES:
        # Separa los identificadores de las propiedades adicionales de cada relación.
        filas = [
            {
                "origen_id": f.pop("origen_id"),
                "destino_id": f.pop("destino_id"),
                "props": f,  
            }
            for f in _leer(sql)
        ]

        # Procesa las relaciones por lotes para optimizar la carga en Neo4j.
        for i in range(0, len(filas), LOTE):
            driver.execute_query(
                f"""
                UNWIND $filas AS f
                MATCH (a:{origen} {{id_oltp: f.origen_id}})
                MATCH (b:{destino} {{id_oltp: f.destino_id}})
                MERGE (a)-[r:{tipo}]->(b)
                SET r += f.props
                """,
                filas=filas[i : i + LOTE],
            )

        # Registra la cantidad de relaciones procesadas por tipo.
        conteos[tipo] = len(filas)
    return conteos