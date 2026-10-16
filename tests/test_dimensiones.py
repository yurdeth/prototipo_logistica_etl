"""Las dimensiones cargan idempotentes y sin huérfanos: re-corrida no
duplica, y toda FK de dimensión a dimensión resuelve."""

from etl.conexiones import conexion_dw
from etl.transform.dimensiones import cargar_dimensiones

TOTALES_ESPERADOS = {
    "dim_territorio": 9,
    "dim_estado": 8,
    "dim_cliente": 32,
    "dim_sucursal": 8,
    "dim_vehiculo": 18,
    "dim_conductor": 8,
    "dim_ruta": 11,
}


def test_la_primera_carga_llena_las_dimensiones():
    cargar_dimensiones()

    with conexion_dw() as cn, cn.cursor() as cur:
        for tabla, esperado in TOTALES_ESPERADOS.items():
            cur.execute(f"SELECT count(*) FROM {tabla}")  # noqa: S608
            (total,) = cur.fetchone()
            assert total == esperado, f"{tabla}: {total} != {esperado}"


def test_recorrida_no_duplica_ni_renumera():
    cargar_dimensiones()
    insertadas = cargar_dimensiones()

    for tabla in TOTALES_ESPERADOS:
        assert insertadas[tabla] == 0, f"{tabla} insertó {insertadas[tabla]} en re-corrida"

    with conexion_dw() as cn, cn.cursor() as cur:
        cur.execute("SELECT count(*) FROM dim_cliente WHERE id_cliente_sk > 32")
        assert cur.fetchone()[0] == 0


def test_las_dimensiones_no_tienen_huerfanos_entre_si():
    cargar_dimensiones()

    with conexion_dw() as cn, cn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM dim_cliente c"
            " LEFT JOIN dim_territorio t ON t.id_territorio_sk = c.territorio_sk"
            " WHERE t.id_territorio_sk IS NULL"
        )
        assert cur.fetchone()[0] == 0

        cur.execute(
            "SELECT count(*) FROM dim_sucursal s"
            " LEFT JOIN dim_territorio t ON t.id_territorio_sk = s.territorio_sk"
            " WHERE t.id_territorio_sk IS NULL"
        )
        assert cur.fetchone()[0] == 0


def test_dim_tiempo_cubre_la_operacion_y_el_miembro_sin_fecha():
    cargar_dimensiones()

    with conexion_dw() as cn, cn.cursor() as cur:
        cur.execute("SELECT count(*) FROM dim_tiempo WHERE id_tiempo = 0")
        assert cur.fetchone()[0] == 1

        # cada fecha de la operación debe tener su fila en dim_tiempo
        cur.execute(
            "SELECT count(*) FROM ("
            "  SELECT DISTINCT (fecha_registro AT TIME ZONE 'America/El_Salvador')::date AS f"
            "  FROM st_envios) fechas"
            " LEFT JOIN dim_tiempo d ON d.fecha = fechas.f"
            " WHERE d.id_tiempo IS NULL"
        )
        assert cur.fetchone()[0] == 0
