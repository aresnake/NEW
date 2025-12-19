from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BridgeConfig:
    transport: str = "tcp"
    host: str = "127.0.0.1"
    port: int = 8765
    timeout_ms: int = 8000
    retries: int = 1
    token: str | None = None


@dataclass(frozen=True)
class LoggingConfig:
    level: str = "INFO"
    file: str | None = "hephaestus_v2.log"


@dataclass(frozen=True)
class AppConfig:
    bridge: BridgeConfig = BridgeConfig()
    logging: LoggingConfig = LoggingConfig()


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_config() -> AppConfig:
    config_path = os.getenv("HEPHAESTUS_CONFIG")
    if not config_path:
        return AppConfig()

    path = Path(config_path)
    if not path.exists():
        return AppConfig()

    raw = _load_json(path)
    bridge_raw = raw.get("bridge", {})
    logging_raw = raw.get("logging", {})
    return AppConfig(
        bridge=BridgeConfig(
            transport=str(bridge_raw.get("transport", "tcp")),
            host=str(bridge_raw.get("host", "127.0.0.1")),
            port=int(bridge_raw.get("port", 8765)),
            timeout_ms=int(bridge_raw.get("timeout_ms", 8000)),
            retries=int(bridge_raw.get("retries", 1)),
            token=bridge_raw.get("token"),
        ),
        logging=LoggingConfig(
            level=str(logging_raw.get("level", "INFO")),
            file=logging_raw.get("file"),
        ),
    )
