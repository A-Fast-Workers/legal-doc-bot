"""Ограничение числа запросов на пользователя (скользящее окно)."""
from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Callable

from .errors import RateLimited


class RateLimiter:
    def __init__(self, limit: int, window_seconds: int = 3600, clock: Callable[[], float] = time.monotonic):
        self.limit = limit
        self.window = window_seconds
        self._clock = clock
        self._hits: dict[int, deque[float]] = defaultdict(deque)

    def check(self, user_id: int) -> None:
        """Регистрирует запрос или бросает RateLimited. limit<=0 отключает ограничение."""
        if self.limit <= 0:
            return
        now = self._clock()
        hits = self._hits[user_id]
        while hits and now - hits[0] > self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            wait = int(self.window - (now - hits[0])) // 60 + 1
            raise RateLimited(
                f"Лимит запросов исчерпан ({self.limit} в час). Попробуйте через {wait} мин."
            )
        hits.append(now)
