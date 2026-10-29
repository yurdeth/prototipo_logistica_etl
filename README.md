# Prototipo Logística ETL

Pipeline ETL en Python que integra una base de datos operacional PostgreSQL (OLTP) de logística con un Data Warehouse (DW) de modelo estrella Kimball y un grafo de la red vial en Neo4j.

- **OLTP**: base `prototipo_logistica` con esquemas `envios`, `rutas`, `flota`, `personal` y `territorio`. El ETL **solo la lee**, nunca escribe en ella.
- **DW**: base `prototipo_logistica_dw`, creada y poblada por este proyecto. Se organiza en dos esquemas: `staging` (copias planas de la operación, una tabla `st_*` por fuente, truncadas en cada corrida) y `dw` (modelo estrella con 8 dimensiones, 4 tablas de hechos y el registro de escenarios de rutas `resultado_escenario`).
- **Neo4j**: almacena el grafo de la red logística — 8 sucursales como nodos y 11 conexiones como relaciones ponderadas — sobre el que se calculan los escenarios base, bloqueo y congestión con Dijkstra.

## Requisitos previos

- Python 3.12 o superior y [uv](https://docs.astral.sh/uv/) como gestor de dependencias.
- PostgreSQL 17 o superior y Neo4j 5.
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
| `NEO4J_*`  | Conexión a Neo4j: carga del grafo y cálculo de escenarios de rutas.                  |

## Puesta en marcha

```bash
# 1. Instalar dependencias
uv sync

# 2. Validar la configuración completa (conexiones y permisos de ambos roles)
uv run pytest

# 3. Corrida completa: migraciones → extract → dimensiones → hechos → grafo
#    → escenarios → verificación de cuadre (sale con error si algo no cuadra)
uv run python -m etl
```

Cada etapa también puede ejecutarse sola (la corrida completa ya las encadena en orden): `python -m etl.migrar`, `python -m etl.extract`, `python -m etl.transform`, `python -m etl.load`.

## Cómo funciona

La corrida completa (`python -m etl`) ejecuta siete etapas en orden, cada una en su propia transacción, y termina con la verificación de cuadre:

1. **Migraciones** (`etl/migrar.py`): aplica los `sql/NNNN_*.sql` pendientes y los registra en `sql_versiones`.
2. **Extract** (`etl/extract/`): trunca y rellena las tablas `st_*` del esquema `staging` usando `COPY` desde la OLTP. El corte es siempre completo y los JOIN con catálogos se hacen aquí para aplanar las filas.
3. **Dimensiones** (`etl/transform/dimensiones.py`): carga las 8 dimensiones en orden de dependencia. La carga es **idempotente**: solo agrega filas cuyo identificador de la OLTP aún no exista, así que re-ejecutar no duplica ni renumera.
4. **Hechos** (`etl/transform/hechos.py`): foto completa por corrida — los 4 hechos (envíos, despachos, eventos, incidencias) se truncan y reconstruyen enteros desde staging. Las medidas condicionales quedan sin valor mientras el proceso no cierra.
5. **Grafo** (`etl/load/grafo.py`): carga la red en Neo4j con `MERGE` (idempotente: re-corrida no duplica nodos ni relaciones).
6. **Escenarios** (`etl/load/escenarios.py`): calcula con Dijkstra la ruta óptima San Salvador → Santa Ana en tres escenarios (base, bloqueo del tramo directo, congestión con penalización) y registra cada resultado en `dw.resultado_escenario`. Si la red quedara desconectada, el resultado se registra **sin totales**, nunca como costo cero.
7. **Verificación** (`etl/verify/cuadre.py`): cuadre final con tres fronteras de conteos (OLTP↔staging, staging↔hechos), agregados espejo OLTP↔DW (peso de envíos, entregados y a tiempo, kilómetros y costo de despachos, incidencias) y la presencia de los tres escenarios. El proceso sale con error si algo difiere.

### Convenciones del modelo

- `*_sk` = clave subrogada del DW; `*_oltp` = identificador de la operación.
- `dim_tiempo.id_tiempo` tiene formato AAAAMMDD; el valor `0` es el miembro "sin fecha", usado por hechos cuyo evento aún no ocurre, evitando nulos en las claves foráneas.
- Estrategia de carga: foto completa por corrida. Los hechos se reconstruyen desde staging en cada ejecución; las dimensiones crecen por clave natural.
- El DDL de las migraciones siempre cualifica el esquema destino (`staging.*`, `dw.*`, `public.sql_versiones`); el DML del pipeline confía en el `search_path` de la conexión del DW (`staging, dw, public`).
- Herramientas de análisis (p. ej. Power BI) acceden únicamente al esquema `dw`.

### Migraciones

Toda la estructura del DW se crea mediante archivos `sql/NNNN_descripcion.sql`, aplicados en orden por `etl/migrar.py`. Cada migración se registra en la tabla `sql_versiones` y solo se aplican las pendientes. Para agregar cambios de estructura, cree un archivo `sql/NNNN_*.sql` nuevo; no edite migraciones ya aplicadas.

### Frontera rectora

El ETL **lee la OLTP y nunca escribe en ella**. Se protege con doble candado: el rol `etl_reader` no tiene permisos de escritura y la sesión se abre en modo `read only`. Los tests de la suite verifican ambos candados; si alguno se afloja, los tests fallan antes de que se cargue un dato.
