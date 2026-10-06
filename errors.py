"""Ошибки с понятными для пользователя текстами."""


class BotError(Exception):
    """Базовая ошибка: user_message можно показывать пользователю как есть."""

    def __init__(self, user_message: str):
        super().__init__(user_message)
        self.user_message = user_message


class ConfigError(RuntimeError):
    """Неверные или отсутствующие настройки запуска."""


class DocumentError(BotError):
    """Документ нельзя прочитать или он не подходит."""


class LLMError(BotError):
    """Сбой при обращении к нейросети."""


class RateLimited(BotError):
    """Превышен лимит запросов."""


class AccessDenied(BotError):
    """Пользователю доступ закрыт."""
