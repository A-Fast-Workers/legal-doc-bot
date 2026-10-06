"""Настройки из переменных окружения (.env)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Mapping, Optional

from .errors import ConfigError


def _bool(value: Optional[str], default: bool) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "да"}


def _int(env: Mapping[str, str], name: str, default: int) -> int:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} должно быть целым числом, сейчас: {raw!r}") from exc


def _ids(raw: Optional[str]) -> frozenset[int]:
    if not raw:
        return frozenset()
    result = set()
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            result.add(int(part))
        except ValueError as exc:
            raise ConfigError(f"ALLOWED_USER_IDS: {part!r} не число") from exc
    return frozenset(result)


@dataclass(frozen=True)
class Settings:
    telegram_token: str = ""
    gigachat_credentials: str = ""
    gigachat_scope: str = "GIGACHAT_API_PERS"
    gigachat_model: str = "GigaChat-2"
    gigachat_verify_ssl: bool = False
    gigachat_ca_bundle: str = ""
    gigachat_timeout: int = 120
    llm_concurrency: int = 1  # бесплатный тариф GigaChat работает в один поток

    max_file_mb: int = 10
    max_chars: int = 150_000          # больше этого документ не принимаем
    single_pass_chars: int = 20_000   # до этого размера разбор одним запросом
    chunk_chars: int = 12_000         # размер части при разборе длинных документов
    qa_chunk_chars: int = 3_000       # размер фрагмента для ответов на вопросы

    session_ttl_minutes: int = 60
    requests_per_hour: int = 15
    allowed_user_ids: frozenset[int] = field(default_factory=frozenset)


def load_settings(
    env: Optional[Mapping[str, str]] = None,
    *,
    require_telegram: bool = True,
    require_llm: bool = True,
) -> Settings:
    env = os.environ if env is None else env

    token = env.get("TELEGRAM_BOT_TOKEN", "").strip()
    creds = env.get("GIGACHAT_CREDENTIALS", "").strip()
    if require_telegram and not token:
        raise ConfigError("Не задан TELEGRAM_BOT_TOKEN (токен от @BotFather).")
    if require_llm and not creds:
        raise ConfigError("Не задан GIGACHAT_CREDENTIALS (ключ авторизации GigaChat API).")

    return Settings(
        telegram_token=token,
        gigachat_credentials=creds,
        gigachat_scope=env.get("GIGACHAT_SCOPE", "GIGACHAT_API_PERS").strip() or "GIGACHAT_API_PERS",
        gigachat_model=env.get("GIGACHAT_MODEL", "GigaChat-2").strip() or "GigaChat-2",
        gigachat_verify_ssl=_bool(env.get("GIGACHAT_VERIFY_SSL"), False),
        gigachat_ca_bundle=env.get("GIGACHAT_CA_BUNDLE", "").strip(),
        gigachat_timeout=_int(env, "GIGACHAT_TIMEOUT", 120),
        llm_concurrency=max(1, _int(env, "LLM_CONCURRENCY", 1)),
        max_file_mb=_int(env, "MAX_FILE_MB", 10),
        max_chars=_int(env, "MAX_CHARS", 150_000),
        single_pass_chars=_int(env, "SINGLE_PASS_CHARS", 20_000),
        chunk_chars=_int(env, "CHUNK_CHARS", 12_000),
        qa_chunk_chars=_int(env, "QA_CHUNK_CHARS", 3_000),
        session_ttl_minutes=_int(env, "SESSION_TTL_MINUTES", 60),
        requests_per_hour=_int(env, "REQUESTS_PER_HOUR", 15),
        allowed_user_ids=_ids(env.get("ALLOWED_USER_IDS")),
    )
