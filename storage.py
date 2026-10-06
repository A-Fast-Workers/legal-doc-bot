"""Сессии пользователей в памяти с TTL. Документы на диск не пишутся."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class Session:
    text: str
    name: str
    analysis: str = ""
    created: float = 0.0
    touched: float = 0.0


class SessionStore:
    def __init__(self, ttl_seconds: int, clock: Callable[[], float] = time.monotonic):
        self._ttl = ttl_seconds
        self._clock = clock
        self._data: dict[int, Session] = {}

    def put(self, user_id: int, text: str, name: str) -> Session:
        now = self._clock()
        session = Session(text=text, name=name, created=now, touched=now)
        self._data[user_id] = session
        self.purge()
        return session

    def get(self, user_id: int) -> Optional[Session]:
        session = self._data.get(user_id)
        if session is None:
            return None
        now = self._clock()
        if now - session.touched > self._ttl:
            del self._data[user_id]
            return None
        session.touched = now
        return session

    def drop(self, user_id: int) -> bool:
        return self._data.pop(user_id, None) is not None

    def purge(self) -> int:
        now = self._clock()
        stale = [uid for uid, s in self._data.items() if now - s.touched > self._ttl]
        for uid in stale:
            del self._data[uid]
        return len(stale)

    def __len__(self) -> int:
        return len(self._data)
