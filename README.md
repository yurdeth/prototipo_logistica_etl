# Prototipo Logística ETL

Pipeline ETL en Python que copia datos de una base de datos operacional PostgreSQL (OLTP) de logística hacia un Data Warehouse (DW) con modelo estrella Kimball.

- **OLTP**: base `prototipo_logistica` con esquemas `envios`, `rutas`, `flota`, `personal` y `territorio`. El ETL **solo la lee**, nunca escribe en ella.
- **DW**: base `prototipo_logistica_dw`, creada por este proyecto. Contiene un esquema de `staging` (copias planas por corrida) y el modelo estrella con 8 dimensiones.
- **Neo4j**: la configuración está incluida, pero el pipeline aún no lo utiliza.

## Requisitos previos

- Python 3.12 o superior y [uv](https://docs.astral.sh/uv/) como gestor de dependencias.
- PostgreSQL 17 o superior.
- Una OLTP **ya existente y poblada** con la estructura descrita arriba. Este proyecto no la crea ni la modifica: es únicamente fuente de lectura.

### Roles de PostgreSQL (crear manualmente)

El ETL usa dos roles con permisos mínimos. **Ninguno lo crea el programa**: deben existir antes de ejecutar cualquier comando. Conéctese como superusuario y ejecute:

```sql
-- 1. Crear los roles
CREATE ROLE etl_reader LOGIN PASSWORD 'cambiar';
CREATE ROLE etl_writer LOGIN PASSWORD 'cambiar';

-- 2. Permisos en la OLTP: SOLO lectura
GRANT CONNECT ON DATABASE prototipo_logistica TO etl_reader;
GRANT USAGE ON ALL SCHEMAS IN DATABASE prototipo_logistica TO etl_reader;
GRANT SELECT ON ALL TABLES IN DATABASE prototipo_logistica TO etl_reader;

-- 3. Crear la base del DW, vacía
CREATE DATABASE prototipo_logistica_dw;

-- 4. Permisos en el DW: etl_writer escribe, etl_reader lee (para cuadres)
GRANT CONNECT ON DATABASE prototipo_logistica_dw TO etl_writer;
GRANT CONNECT ON DATABASE prototipo_logistica_dw TO etl_reader;
GRANT USAGE, CREATE ON SCHEMA public TO etl_writer;
GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN DATABASE prototipo_logistica_dw TO etl_writer;
GRANT USAGE ON ALL SCHEMAS IN DATABASE prototipo_logistica_dw TO etl_reader;
GRANT SELECT ON ALL TABLES IN DATABASE prototipo_logistica_dw TO etl_reader;
```

> Nota: la primera migración ejecuta `ALTER DEFAULT PRIVILEGES FOR ROLE etl_writer`, por lo que **el rol debe existir antes de aplicar las migraciones**. Ese es el orden correcto: roles → base del DW → migraciones.

### Variables de entorno

Copie `.env.example` a `.env` y complete las contraseñas:

```bash
cp .env.example .env
```

| Variable   | Descripción                                                                         |
|------------|-------------------------------------------------------------------------------------|
| `ETL_DB_*` | Conexión a la OLTP (`prototipo_logistica`) con el rol de solo lectura `etl_reader`. |
| `DW_DB_*`  | Conexión al DW (`prototipo_logistica_dw`) con el rol de escritura `etl_writer`.     |
| `NEO4J_*`  | Conexión a Neo4j (opcional por ahora; el pipeline no lo usa todavía).               |

## Puesta en marcha

Ejecute los pasos en orden. Cada uno verifica el anterior: si algo de la configuración anterior falla, el primero en notarlo será `pytest`.

```bash
# 1. Instalar dependencias
uv sync

# 2. Validar la configuración completa (conexiones y permisos de ambos roles)
uv run pytest

# 3. Aplicar las migraciones: crea staging, las tablas st_* y el modelo estrella
uv run python -m etl.migrar

# 4. Extract: copia la OLTP a staging en el DW (corte completo por corrida)
uv run python -m etl.extract

# 5. Transform: carga las 8 dimensiones del modelo estrella desde staging
uv run python -m etl.transform
```

Los pasos 4 y 5 imprimen los conteos de filas por tabla, de modo que se puede cuadrar el extract contra la OLTP y el transform contra staging.

## Cómo funciona

El pipeline se ejecuta por etapas; cada una es un subpaquete invocable con `python -m`:

1. **Extract** (`etl/extract/`): trunca y rellena las tablas `st_*` del esquema `staging` usando `COPY` desde la OLTP. El corte es siempre completo. Los JOIN con catálogos se hacen aquí para aplanar las filas.
2. **Transform** (`etl/transform/`): carga las dimensiones en un orden definido (territorio/estado/tiempo primero, quienes los referencian después). La carga es **idempotente**: solo agrega filas cuyo identificador de la OLTP aún no exista en la dimensión, así que re-ejecutar no duplica ni renumera.
3. **Load** (`etl/load/`) y **Verify** (`etl/verify/`): cargas de hechos y verificaciones aún no implementadas (placeholders).

### Convenciones del modelo

- `*_sk` = clave subrogada del DW; `*_oltp` = identificador de la operación.
- `dim_tiempo.id_tiempo` tiene formato AAAAMMDD; el valor `0` es el miembro "sin fecha", usado por hechos cuyo evento aún no ocurre, evitando nulos en las claves foráneas.
- Estrategia de carga: foto completa por corrida. Los hechos se reconstruyen desde staging en cada ejecución; las dimensiones crecen por clave natural.

### Migraciones

Toda la estructura del DW se crea mediante archivos `sql/NNNN_descripcion.sql`, aplicados en orden por `etl/migrar.py`. Cada migración se registra en la tabla `sql_versiones` y solo se aplican las pendientes. Para agregar cambios de estructura, cree un archivo `sql/NNNN_*.sql` nuevo; no edite migraciones ya aplicadas.

### Frontera rectora

El ETL **lee la OLTP y nunca escribe en ella**. Se protege con doble candado: el rol `etl_reader` no tiene permisos de escritura y la sesión se abre en modo `read only`. Los tests de la suite verifican ambos candados; si alguno se afloja, los tests fallan antes de que se cargue un dato.
