"""Consultas de extracción: cada entrada mapea una tabla de staging con la
consulta que llena sus columnas desde la OLTP. Los JOIN con catálogos van
aquí (aplanar en el extract), para que el transform consuma filas planas."""

# orden del dict = orden de carga (primeros los catálogos)
CONSULTAS: dict[str, str] = {
    "st_territorios": """
        SELECT id_territorio, nombre_territorio, tipo_territorio
        FROM territorio.territorios
    """,
    "st_sucursales": """
        SELECT id_sucursal, codigo, nombre_sucursal, territorio_id,
               latitud, longitud, activa
        FROM territorio.sucursales
    """,
    "st_clientes": """
        SELECT id_cliente, nombre, tipo_cliente, contacto, territorio_id
        FROM envios.clientes
    """,
    "st_estados_envios": """
        SELECT id_estado, nombre_estado
        FROM envios.estados_envios
    """,
    "st_vehiculos": """
        SELECT v.id_vehiculo, v.placa, t.nombre, t.capacidad_kg,
               v.consumo_km_gal, v.sucursal_id
        FROM flota.vehiculos v
        JOIN flota.tipos_vehiculos t ON t.id_tipo_vehiculo = v.tipo_vehiculo_id
    """,
    "st_empleados": """
        SELECT id_empleado, nombres, apellidos, numero_licencia,
               sucursal_id, activo
        FROM personal.empleados
    """,
    "st_conexiones": """
        SELECT id_conexion, origen_sucursal_id, destino_sucursal_id,
               distancia_km, tiempo_min, activa
        FROM rutas.conexiones
    """,
    "st_envios": """
        SELECT e.id_envio, e.codigo_guia, e.cliente_remitente_id,
               e.cliente_destinatario_id, e.sucursal_origen_id,
               e.territorio_destino_id, e.direccion_destino, e.peso_kg,
               e.volumen_m3, e.estado_envio_id, s.nombre_estado,
               e.prioridad, e.fecha_registro, e.fecha_comprometida
        FROM envios.envios e
        JOIN envios.estados_envios s ON s.id_estado = e.estado_envio_id
    """,
    "st_envio_eventos": """
        SELECT ev.id_evento, ev.envio_id, ev.estado_envio_id, s.nombre_estado,
               ev.ocurrido_en, ev.nota
        FROM envios.envio_eventos ev
        JOIN envios.estados_envios s ON s.id_estado = ev.estado_envio_id
    """,
    "st_despachos": """
        SELECT d.id_despacho, d.sucursal_origen_id, d.conductor_empleado_id,
               d.vehiculo_id, d.fecha, d.estado_despacho_id, ed.nombre_estado,
               d.km_planificados, d.km_recorridos, d.costo_estimado
        FROM rutas.despachos d
        JOIN rutas.estados_despachos ed ON ed.id_estado = d.estado_despacho_id
    """,
    "st_despacho_paradas": """
        SELECT id_parada, despacho_id, envio_id, orden, hora_estimada, hora_real
        FROM rutas.despacho_paradas
    """,
    "st_incidencias": """
        SELECT i.id_incidencia, i.tipo_incidencia_id, ti.nombre_tipo,
               i.despacho_id, i.envio_id, i.ocurrio_en, i.descripcion,
               i.minutos_retraso
        FROM rutas.incidencias i
        JOIN rutas.tipos_incidencias ti ON ti.id_tipo = i.tipo_incidencia_id
    """,
    "st_tipos_incidencias": """
        SELECT id_tipo, nombre_tipo
        FROM rutas.tipos_incidencias
    """,
}
