"""Configuración del ETL desde el entorno: OLTP (solo lectura), DW y Neo4j."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Ajustes(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # OLTP: el ETL solo LEE con el rol etl_reader (sin permisos de escritura)
    etl_db_host: str = "127.0.0.1"
    etl_db_port: int = 5432
    etl_db_database: str = "prototipo_logistica"
    etl_db_username: str = "etl_reader"
    etl_db_password: str = ""

    # DW: aquí el ETL sí escribe (rol etl_writer)
    dw_db_host: str = "127.0.0.1"
    dw_db_port: int = 5432
    dw_db_database: str = "prototipo_logistica_dw"
    dw_db_username: str = "etl_writer"
    dw_db_password: str = ""

    # Neo4j
    neo4j_uri: str = "bolt://127.0.0.1:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""


def ajustes() -> Ajustes:
    """Configuración singleton: se lee el .env una sola vez por corrida."""
    global _AJUSTES  # noqa: PLW0603
    if _AJUSTES is None:
        _AJUSTES = Ajustes()
    return _AJUSTES


_AJUSTES: Ajustes | None = None
