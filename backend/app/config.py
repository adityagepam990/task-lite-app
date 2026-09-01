"""Application settings, loaded from files with environment overrides.

The app is meant to run on a laptop with zero setup, so configuration is a plain
`config.toml` next to the source. Environment variables still win, which keeps
the same image usable in a container or behind a process manager.

Resolution order, highest priority first:

1. Values passed directly to ``Settings(...)`` -- used by the test suite
2. Environment variables, e.g. ``TASKLITE_SERVER__PORT=9000``
3. ``.env`` in the backend directory
4. ``config.toml`` in the backend directory
5. Defaults declared on the models below
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

# backend/app/config.py -> backend/. Everything file-related hangs off this so
# the server behaves the same regardless of the shell's working directory.
BACKEND_DIR = Path(__file__).resolve().parent.parent

CONFIG_FILE = BACKEND_DIR / "config.toml"
ENV_FILE = BACKEND_DIR / ".env"


class AppSection(BaseModel):
    """Identity and behaviour of the API itself."""

    name: str = "TaskLite API"
    version: str = "1.0.0"
    # When false, unhandled exceptions return an opaque message instead of the
    # exception text, so we never leak internals to a client.
    debug: bool = True


class ServerSection(BaseModel):
    """Where uvicorn binds when started via ``python -m app.main``."""

    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)


class DatabaseSection(BaseModel):
    """SQLite location and logging."""

    # Either a filename/relative path (resolved against backend/) or the special
    # value ":memory:" for a throwaway database.
    path: str = "tasklite.db"
    echo_sql: bool = False

    @property
    def url(self) -> str:
        """Return the SQLAlchemy URL for this database."""
        if self.path == ":memory:":
            return "sqlite://"
        resolved = Path(self.path)
        if not resolved.is_absolute():
            resolved = BACKEND_DIR / resolved
        # Ensure the parent exists so a nested path like "data/db.sqlite" works.
        resolved.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{resolved}"


class CorsSection(BaseModel):
    """Cross-origin rules for the Expo/Metro dev server."""

    allow_origins: list[str] = Field(default_factory=lambda: ["*"])


class SeedSection(BaseModel):
    """Whether to populate starter content into an empty database."""

    enabled: bool = True


class Settings(BaseSettings):
    """Root settings object; one instance per process via :func:`get_settings`."""

    model_config = SettingsConfigDict(
        env_prefix="TASKLITE_",
        # Section and field are joined by a double underscore, which keeps env
        # var names unambiguous even though field names contain underscores.
        env_nested_delimiter="__",
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        toml_file=CONFIG_FILE,
        extra="ignore",
    )

    app: AppSection = Field(default_factory=AppSection)
    server: ServerSection = Field(default_factory=ServerSection)
    database: DatabaseSection = Field(default_factory=DatabaseSection)
    cors: CorsSection = Field(default_factory=CorsSection)
    seed: SeedSection = Field(default_factory=SeedSection)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Order the config sources; earlier entries take precedence.

        The only change from pydantic-settings' default is appending the TOML
        source last, so `config.toml` acts as a committed baseline that both the
        environment and `.env` can override.
        """
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            file_secret_settings,
            TomlConfigSettingsSource(settings_cls),
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings, parsed once and cached.

    Tests that need different settings should call ``get_settings.cache_clear()``
    or construct ``Settings(...)`` directly rather than mutating the cached copy.
    """
    return Settings()
