"""Бизнес-логика бота без привязки к Telegram: удобно тестировать."""
from __future__ import annotations

from typing import Optional

from . import prompts
from .analyzer import Analysis, Analyzer, Progress
from .config import Settings
from .errors import AccessDenied, BotError
from .extract import ExtractedDoc, extract_text, finalize
from .llm import LLM
from .ratelimit import RateLimiter
from .storage import SessionStore

NO_DOC = "Сначала отправьте документ (PDF, DOCX, TXT) или вставьте его текст сообщением."


class LegalService:
    def __init__(self, llm: LLM, settings: Settings, *, store: Optional[SessionStore] = None,
                 limiter: Optional[RateLimiter] = None):
        self.s = settings
        self.analyzer = Analyzer(llm, settings)
        self.store = store or SessionStore(settings.session_ttl_minutes * 60)
        self.limiter = limiter or RateLimiter(settings.requests_per_hour)

    def check_access(self, user_id: int) -> None:
        allowed = self.s.allowed_user_ids
        if allowed and user_id not in allowed:
            raise AccessDenied("Доступ к боту ограничен.")

    def load_file(self, user_id: int, data: bytes, filename: str) -> ExtractedDoc:
        self.check_access(user_id)
        if len(data) > self.s.max_file_mb * 1024 * 1024:
            raise BotError(f"Файл больше {self.s.max_file_mb} МБ.")
        doc = extract_text(data, filename, self.s.max_chars)
        self.store.put(user_id, doc.text, filename)
        return doc

    def load_text(self, user_id: int, text: str) -> ExtractedDoc:
        self.check_access(user_id)
        doc = finalize(text, "paste", self.s.max_chars)
        self.store.put(user_id, doc.text, "вставленный текст")
        return doc

    async def analyze(self, user_id: int, progress: Progress = None) -> Analysis:
        self.check_access(user_id)
        session = self.store.get(user_id)
        if session is None:
            raise BotError(NO_DOC)
        self.limiter.check(user_id)
        result = await self.analyzer.analyze(session.text, progress)
        session.analysis = result.text
        return result

    async def ask(self, user_id: int, question: str) -> str:
        self.check_access(user_id)
        session = self.store.get(user_id)
        if session is None:
            raise BotError(NO_DOC)
        self.limiter.check(user_id)
        return await self.analyzer.ask(session.text, question)

    async def quick(self, user_id: int, key: str) -> str:
        question = prompts.QUICK_ACTIONS.get(key)
        if question is None:
            raise BotError("Неизвестное действие.")
        return await self.ask(user_id, question)

    async def simplify(self, user_id: int, fragment: str) -> str:
        self.check_access(user_id)
        if len(fragment.strip()) < 20:
            raise BotError("Пришлите фрагмент подлиннее.")
        self.limiter.check(user_id)
        return await self.analyzer.simplify(fragment)

    def reset(self, user_id: int) -> bool:
        return self.store.drop(user_id)
