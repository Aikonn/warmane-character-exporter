"""Machine-aware configuration loading for local client paths."""

from __future__ import annotations

import socket
import tomllib
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    """Raised when configuration cannot be loaded or resolved."""


def find_config_path(explicit: str | Path | None = None) -> Path:
    """Return the config path from an explicit value or repository default."""
    if explicit is not None:
        return Path(explicit)
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "warmane-character-exporter.config"


def load_config(path: str | Path, hostname: str | None = None) -> dict[str, Any]:
    """
    Load and merge config from [default] and [machines.<hostname>].

    Machine-specific values override default values.
    """
    config_path = Path(path)
    detected_hostname = hostname or socket.gethostname()

    try:
        raw_bytes = config_path.read_bytes()
    except FileNotFoundError as exc:
        raise ConfigError(
            "Config file not found at "
            f"{config_path}. Copy warmane-character-exporter.config.template "
            "to warmane-character-exporter.config and update wow_client_dirs."
        ) from exc
    except OSError as exc:
        raise ConfigError(f"Failed to read config file at {config_path}: {exc}") from exc

    try:
        parsed = tomllib.loads(raw_bytes.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise ConfigError(f"Config file is not valid UTF-8 at {config_path}: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Invalid TOML in config file at {config_path}: {exc}") from exc

    if not isinstance(parsed, dict):
        raise ConfigError(f"Invalid config structure at {config_path}: expected a TOML table.")

    default_section = parsed.get("default")
    machines_section = parsed.get("machines")

    if default_section is not None and not isinstance(default_section, dict):
        raise ConfigError(f"Invalid [default] section in {config_path}: expected a table.")
    if machines_section is not None and not isinstance(machines_section, dict):
        raise ConfigError(f"Invalid [machines] section in {config_path}: expected a table.")

    machine_match: dict[str, Any] | None = None
    if isinstance(machines_section, dict):
        wanted = detected_hostname.casefold()
        for machine_name, machine_config in machines_section.items():
            if not isinstance(machine_name, str):
                continue
            if machine_name.casefold() == wanted:
                if not isinstance(machine_config, dict):
                    raise ConfigError(
                        f"Invalid [machines.{machine_name}] section in {config_path}: "
                        "expected a table."
                    )
                machine_match = machine_config
                break

    if default_section is None and machine_match is None:
        raise ConfigError(
            "No matching machine section and no [default] section found for hostname "
            f"{detected_hostname} in {config_path}."
        )

    merged: dict[str, Any] = {}
    if isinstance(default_section, dict):
        merged.update(default_section)
    if machine_match is not None:
        merged.update(machine_match)

    return merged


def resolve_wow_client_dir(config: dict[str, Any]) -> Path:
    """Return the first existing directory in wow_client_dirs."""
    raw_dirs = config.get("wow_client_dirs")
    if not isinstance(raw_dirs, list) or not raw_dirs:
        raise ConfigError(
            "No usable wow_client_dirs in merged config. Provide a non-empty list of paths."
        )

    tried: list[str] = []
    for raw_path in raw_dirs:
        if not isinstance(raw_path, str):
            continue
        candidate = Path(raw_path).expanduser()
        tried.append(str(candidate))
        if candidate.is_dir():
            return candidate

    raise ConfigError(
        "No existing WoW client directory found. Paths tried: " + ", ".join(tried)
    )
