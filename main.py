"""Точка входа: python -m legalbot.main"""
from __future__ import annotations

import asyncio
import logging

from .config import load_settings
from .errors import ConfigError


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass


async def run() -> None:
    from aiogram import Bot, Dispatcher
    from aiogram.client.default import DefaultBotProperties
    from aiogram.enums import ParseMode

    from .handlers import build_router
    from .llm import GigaChatLLM
    from .service import LegalService

    settings = load_settings()
    llm = GigaChatLLM(settings)
    service = LegalService(llm, settings)

    bot = Bot(settings.telegram_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(build_router(service))
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await llm.aclose()
        await bot.session.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    _load_dotenv()
    try:
        asyncio.run(run())
    except ConfigError as exc:
        raise SystemExit(f"Ошибка настройки: {exc}")
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
