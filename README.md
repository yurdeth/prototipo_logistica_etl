# Prototipo Logística ETL
 
Pipeline ETL en Python que copia datos de una base operacional PostgreSQL (OLTP) de logística hacia un **Data Warehouse** con modelo estrella Kimball y, a partir de él, construye un **grafo en Neo4j** de la red de rutas para análisis de inteligencia de negocios.

| Componente | Descripción |
|---|---|
| **OLTP** | Base `prototipo_logistica` (esquemas `envios`, `rutas`, `flota`, `personal`, `territorio`). El ETL **solo la lee**, nunca escribe. |
| **DW** | Base `prototipo_logistica_dw`, creada por este proyecto: esquema `staging` (copias planas por corrida) y modelo estrella con 8 dimensiones. |
| **Neo4j** | Proyección pequeña del DW con forma de red: sucursales, territorios y rutas. Responde preguntas de caminos que el modelo estrella resuelve mal. |

**División de responsabilidades:** el DW guarda agregados, tendencias y atributos (clientes, conductores, vehículos, calendario). Neo4j guarda únicamente la estructura de red y se usa para recorridos de profundidad variable (camino más rápido, puntos críticos, alternativas si falla una ruta).

## Requisitos previos
 
- Python 3.12 o superior y [uv](https://docs.astral.sh/uv/).
- PostgreSQL 17 o superior (con `psql`).
- Docker y Docker Compose (para Neo4j).
- Una OLTP ya existente y poblada. Este proyecto no la crea ni la modifica.

## 1. Roles y bases de PostgreSQL (manual, una sola vez)
 
El programa no crea los roles ni las bases: deben existir antes de ejecutar cualquier comando. El orden correcto es **roles → base del DW → migraciones**.

### 1.1 Como superusuario (`postgres`), conectado a la base `postgres`
 
```sql
-- Roles (cambie las contraseñas)
CREATE ROLE etl_reader LOGIN PASSWORD 'cambiar';
CREATE ROLE etl_writer LOGIN PASSWORD 'cambiar';
 
-- Base del DW, con etl_writer como dueño
CREATE DATABASE prototipo_logistica_dw OWNER etl_writer;
 
-- Conexión a las dos bases
GRANT CONNECT ON DATABASE prototipo_logistica    TO etl_reader;
GRANT CONNECT ON DATABASE prototipo_logistica_dw TO etl_reader;
```

> Hacer a `etl_writer` **dueño** del DW es intencional: así puede ejecutar `CREATE SCHEMA` y crear tablas en las migraciones. Dar solo `CREATE` sobre `public` no alcanza y produce el error `permiso denegado a la base de datos`.

### 1.2 Permisos de lectura en la OLTP
 
Conéctese a la OLTP (`\c prototipo_logistica`) y ejecute:
 
```sql
DO $$
DECLARE s RECORD;
BEGIN
    FOR s IN
        SELECT schema_name FROM information_schema.schemata
        WHERE schema_name <> 'information_schema' AND schema_name NOT LIKE 'pg\_%'
    LOOP
        EXECUTE format('GRANT USAGE ON SCHEMA %I TO etl_reader', s.schema_name);
        EXECUTE format('GRANT SELECT ON ALL TABLES IN SCHEMA %I TO etl_reader', s.schema_name);
    END LOOP;
END $$;
```
### 1.3 Permisos de lectura en el DW
 
Conéctese al DW (`\c prototipo_logistica_dw`) y ejecute el **mismo bloque** de arriba. Esto permitirá otorgar permisos de lectura sobre los esquemas y las tablas que ya existan en la base de datos, como los del esquema public.
 
Para los esquemas y las tablas que se creen en el futuro (staging, modelo estrella), la primera migración configura los permisos predeterminados mediante  `ALTER DEFAULT PRIVILEGES FOR ROLE etl_writer` y debe otorgar también `USAGE` sobre cada esquema nuevo a `etl_reader`. Por eso `etl_writer` debe existir antes de migrar.
 
> **Notas sobre sintaxis.** `GRANT ... ON ALL SCHEMAS IN DATABASE` y `GRANT ... ON ALL TABLES IN DATABASE` **no existen** en PostgreSQL. Los bloques `DO $$` solo afectan a la base a la que se está conectado, por eso se ejecutan una vez en cada base.

## 2. Variables de entorno

Copie `.env.example` a `.env` y complete las contraseñas:

```bash
cp .env.example .env
```

| Variable   | Descripción                                                                         |
|------------|-------------------------------------------------------------------------------------|
| `ETL_DB_*` | Conexión a la OLTP (`prototipo_logistica`) con el rol de solo lectura `etl_reader`. |
| `DW_DB_*`  | Conexión al DW (`prototipo_logistica_dw`) con el rol de escritura `etl_writer`.     |
| `NEO4J_*`  | Conexión a Neo4j.  

## 3. Neo4j con Docker
El archivo docker-compose.yml, ubicado en la raíz del repositorio, permite levantar Neo4j mediante Docker Compose. La configuración utiliza las variables definidas en el archivo .env, evitando duplicar las credenciales y facilitando la configuración del entorno.

Para iniciar el servicio en segundo plano, ejecute los siguientes comandos:

```bash
docker compose up -d
docker compose ps          # esperar a que diga "healthy"
```         

## 4. Puesta en marcha

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

# 6. Grafo: carga sucursales, territorios y rutas en Neo4j desde el DW
uv run python -m etl.grafo
```

Los pasos 4, 5 y 6 imprimen conteos para poder cuadrar cada etapa contra la anterior.

## 5. Cómo funciona

El pipeline se ejecuta por etapas; cada una es un subpaquete invocable con `python -m`:

| Etapa | Módulo | Qué hace |
|---|---|---|
| Migrar | `etl/migrar.py` | Crea la tabla de control `public.sql_versiones` si no existe y aplica en orden los `sql/NNNN_*.sql` pendientes, cada uno en su propia transacción. |
| Extract | `etl/extract/` | Trunca y rellena las tablas `st_*` de `staging` con `COPY` desde la OLTP. Los `JOIN` con catálogos se hacen aquí para aplanar filas. |
| Transform | `etl/transform/` | Carga las dimensiones en orden (territorio, estado y tiempo primero). Es idempotente: solo agrega filas cuyo id de la OLTP aún no existe. |
| Grafo | `etl/grafo/` | Lee del DW y escribe en Neo4j con `MERGE`, por lo que re-ejecutar no duplica. |
| Load / Verify | `etl/load/`, `etl/verify/` | Cargas de hechos y verificaciones: aún placeholders. |

## 6. Modelo del grafo
 
Solo se carga lo que tiene forma de red. Lo demás se consulta en SQL.
 
```
(:Sucursal)-[:RUTA {id_oltp, distancia_km, tiempo_min}]->(:Sucursal)
(:Sucursal)-[:UBICADA_EN]->(:Territorio)
```

## 7. Verificación
 
### 7.1 Conexión a Neo4j
 
```bash
uv run python -c "from etl.conexiones import conexion_neo4j; d = conexion_neo4j(); print('conexión OK'); d.close()"
```

## 8. Convenciones del modelo
 
- `*_sk` = clave subrogada del DW; `*_oltp` = identificador de la operación (`id_conexion_oltp` en rutas, `id_empleado_oltp` en conductores).
- `dim_tiempo.id_tiempo` tiene formato `AAAAMMDD`; el valor `0` es el miembro «sin fecha», usado por hechos cuyo evento aún no ocurre, para evitar nulos en las claves foráneas.
- Estrategia de carga: foto completa por corrida. Los hechos se reconstruyen desde staging en cada ejecución; las dimensiones crecen por clave natural.
  
## 9. Migraciones
 
Toda la estructura del DW se crea con archivos `sql/NNNN_descripcion.sql`, aplicados en orden por `etl/migrar.py`. Cada migración se registra en `public.sql_versiones` (tabla creada automáticamente) y solo se aplican las pendientes. Para cambiar la estructura, cree un archivo nuevo; **no edite migraciones ya aplicadas**.
 
## 10. Frontera rectora
 
El ETL lee la OLTP y nunca escribe en ella. Se protege con doble candado: el rol `etl_reader` no tiene permisos de escritura y la sesión se abre en modo *read only*. Los tests de la suite verifican ambos candados; si alguno se afloja, los tests fallan antes de que se cargue un dato.
