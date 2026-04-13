from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    discord_token: str
    dev_guild_id: int
    db_path: Path
    log_level: str


def load(env_file: str = ".env") -> Config:
    load_dotenv(env_file)

    token = os.environ.get("DISCORD_TOKEN", "").strip()
    if not token:
        raise RuntimeError("DISCORD_TOKEN is not set in environment / .env")

    guild_id_raw = os.environ.get("DEV_GUILD_ID", "").strip()
    if not guild_id_raw:
        raise RuntimeError("DEV_GUILD_ID is not set in environment / .env")
    try:
        guild_id = int(guild_id_raw)
    except ValueError:
        raise RuntimeError(f"DEV_GUILD_ID must be an integer, got: {guild_id_raw!r}")

    db_path = Path(os.environ.get("DB_PATH", "data/bets.db"))
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()

    return Config(
        discord_token=token,
        dev_guild_id=guild_id,
        db_path=db_path,
        log_level=log_level,
    )
