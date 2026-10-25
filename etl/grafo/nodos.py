"""Un nodo por fila de dimensión, identificado por su clave *_oltp."""

from etl.conexiones import conexion_dw

# Define la etiqueta del nodo y la consulta SQL para obtener sus datos.
NODOS = [
    ("Territorio",
        "SELECT id_territorio_oltp AS id_oltp, nombre_territorio AS nombre FROM public.dim_territorio"),
    ("Sucursal",
        "SELECT id_sucursal_oltp AS id_oltp, codigo, nombre, "
        "latitud::float8 AS latitud, longitud::float8 AS longitud FROM public.dim_sucursal"),
]
LOTE = 1000 # Cantidad máxima de filas procesadas por lote


def _leer(sql: str) -> list[dict]:
    # Ejecuta la consulta y convierte cada fila en un diccionario.
    with conexion_dw() as cn, cn.cursor() as cur:
        cur.execute(sql)
        columnas = [c.name for c in cur.description]
        return [dict(zip(columnas, fila)) for fila in cur.fetchall()]


def cargar_nodos(driver) -> dict[str, int]:
    conteos = {}
    for etiqueta, sql in NODOS:
        filas = _leer(sql)
        # Procesa los registros por lotes para optimizar la carga en Neo4j.
        for i in range(0, len(filas), LOTE):
            driver.execute_query(
                f"UNWIND $filas AS f MERGE (n:{etiqueta} {{id_oltp: f.id_oltp}}) SET n += f",
                filas=filas[i : i + LOTE],
            )

        # Registra la cantidad de nodos procesados por etiqueta.
        conteos[etiqueta] = len(filas)
    return conteos