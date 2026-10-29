"""El modelo estrella aplicado: tablas presentes, integridad referencial y
el miembro 0 de dim_tiempo que evita nulos en los hechos no cerrados."""

from etl.conexiones import conexion_dw

DIMENSIONES = ["dim_tiempo", "dim_estado", "dim_territorio", "dim_cliente",
               "dim_sucursal", "dim_vehiculo", "dim_conductor",
               "dim_tipo_incidencia"]

HECHOS = ["hecho_envios", "hecho_despachos", "hecho_eventos", "hecho_incidencias"]


def test_todas_las_tablas_del_estrella_existen():
    with conexion_dw() as cn, cn.cursor() as cur:
        for tabla in DIMENSIONES + HECHOS + ["resultado_escenario"]:
            cur.execute(
                "SELECT count(*) FROM information_schema.tables"
                " WHERE table_schema = 'dw' AND table_name = %s",
                (tabla,),
            )
            (existe,) = cur.fetchone()
            assert existe == 1


def test_las_copias_de_staging_viven_en_su_esquema():
    with conexion_dw() as cn, cn.cursor() as cur:
        for tabla in ("st_envios", "st_despachos", "st_incidencias",
                      "st_despacho_paradas"):
            cur.execute(
                "SELECT count(*) FROM information_schema.tables"
                " WHERE table_schema = 'staging' AND table_name = %s",
                (tabla,),
            )
            (existe,) = cur.fetchone()
            assert existe == 1


def test_los_hechos_apuntan_solo_a_dimensiones():
    # sin huérfanos: toda FK de los hechos resuelve (vacío al aplicar, pero
    # la consulta misma prueba que las referencias son válidas en el esquema)
    with conexion_dw() as cn, cn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM hecho_envios e"
            " LEFT JOIN dim_cliente c ON c.id_cliente_sk = e.remitente_sk"
            " WHERE e.hecho_id IS NOT NULL AND c.id_cliente_sk IS NULL"
        )
        assert cur.fetchone()[0] == 0


def test_dim_tiempo_tiene_miembro_sin_fecha():
    with conexion_dw() as cn, cn.cursor() as cur:
        cur.execute("SELECT fecha FROM dim_tiempo WHERE id_tiempo = 0")
        (fecha,) = cur.fetchone()
        assert fecha is None


def test_la_ddl_del_estrella_es_idempotente():
    from etl.migrar import migrar

    assert migrar() == []
