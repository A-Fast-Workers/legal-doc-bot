"""Обёртка над GigaChat и тестовая заглушка. Ядро бота зависит только от протокола LLM."""
from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable, Optional, Protocol

from .config import Settings
from .errors import LLMError

log = logging.getLogger(__name__)


class LLM(Protocol):
    async def complete(self, system: str, user: str, *, temperature: float = 0.2,
                       max_tokens: int = 1800) -> str: ...


class GigaChatLLM:
    """Клиент GigaChat. Бесплатный тариф даёт один поток, поэтому есть семафор и повторы."""

    def __init__(self, settings: Settings, retries: int = 2):
        self._settings = settings
        self._retries = retries
        self._sem = asyncio.Semaphore(settings.llm_concurrency)
        self._client = None

    def _get_client(self):
        if self._client is None:
            from gigachat import GigaChat  # импорт здесь, чтобы ядро работало без SDK

            kwargs = dict(
                credentials=self._settings.gigachat_credentials,
                scope=self._settings.gigachat_scope,
                model=self._settings.gigachat_model,
                timeout=self._settings.gigachat_timeout,
            )
            if self._settings.gigachat_ca_bundle:
                kwargs["ca_bundle_file"] = self._settings.gigachat_ca_bundle
                kwargs["verify_ssl_certs"] = True
            else:
                kwargs["verify_ssl_certs"] = self._settings.gigachat_verify_ssl
            self._client = GigaChat(**kwargs)
        return self._client

    async def complete(self, system, user, *, temperature=0.2, max_tokens=1800):
        payload = {
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        last_exc: Optional[Exception] = None
        for attempt in range(self._retries + 1):
            try:
                async with self._sem:
                    resp = await self._get_client().achat(payload)
                text = (resp.choices[0].message.content or "").strip()
                if not text:
                    raise LLMError("Нейросеть вернула пустой ответ. Попробуйте ещё раз.")
                return text
            except LLMError:
                raise
            except Exception as exc:  # сеть, 429, авторизация: SDK кидает разные типы
                last_exc = exc
                log.warning("GigaChat: попытка %s не удалась: %r", attempt + 1, exc)
                if attempt < self._retries:
                    await asyncio.sleep(2 * (attempt + 1))
        raise LLMError(
            "Сейчас не получается связаться с GigaChat. Подождите минуту и повторите запрос."
        ) from last_exc

    async def aclose(self) -> None:
        if self._client is not None:
            close = getattr(self._client, "aclose", None)
            if close:
                await close()


class FakeLLM:
    """Для тестов и демо без ключа: возвращает заданный ответ и запоминает вызовы."""

    def __init__(self, responder: Optional[Callable[[str, str], str]] = None):
        self.calls: list[tuple[str, str]] = []
        self._responder = responder

    async def complete(self, system, user, *, temperature=0.2, max_tokens=1800):
        self.calls.append((system, user))
        if self._responder:
            return self._responder(system, user)
        return f"[заглушка] ответ на запрос #{len(self.calls)}"
