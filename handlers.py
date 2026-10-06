"""Тонкий слой aiogram 3: принимает сообщения и вызывает LegalService."""
from __future__ import annotations

import io
import logging

from aiogram import F, Router
from aiogram.enums import ChatAction
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.chat_action import ChatActionSender
from aiogram.utils.keyboard import InlineKeyboardBuilder

from . import prompts
from .errors import BotError
from .extract import SUPPORTED_EXTENSIONS
from .formatting import split_message, to_html
from .service import NO_DOC, LegalService

log = logging.getLogger(__name__)

START_TEXT = (
    "👋 Здравствуйте! Я помогу разобраться в юридических документах: "
    "договорах, офертах, соглашениях, претензиях.\n\n"
    "📎 <b>Как начать</b>\n"
    "Отправьте файл (PDF, DOCX, TXT) или вставьте текст документа сообщением.\n\n"
    "🔎 <b>Что я сделаю</b>\n"
    "• объясню суть простыми словами\n"
    "• выделю ключевые условия: деньги, сроки, обязанности\n"
    "• найду риски и невыгодные пункты (🔴 высокий, 🟡 средний, 🟢 низкий)\n"
    "• подскажу, чего не хватает и что проверить перед подписанием\n\n"
    "💬 <b>Потом можно спрашивать</b>\n"
    "«Какая неустойка за просрочку?», «Как расторгнуть договор?», «Что значит пункт 4.2?»\n\n"
    "<b>Команды</b>\n"
    "/simplify — объяснить фрагмент простым языком\n"
    "/new — удалить документ и начать заново\n\n"
    "🔒 Документ хранится только в памяти и удаляется через час.\n"
    "⚠️ Я не заменяю юриста: это автоматический разбор, и я могу ошибаться. "
    "Важные документы показывайте специалисту."
)

ACTION_TITLES = {"risks": "Риски", "money": "Деньги и штрафы", "terms": "Сроки", "checklist": "Чек-лист"}


def actions_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⚠️ Риски", callback_data="q:risks")
    kb.button(text="💰 Деньги и штрафы", callback_data="q:money")
    kb.button(text="📅 Сроки", callback_data="q:terms")
    kb.button(text="✅ Чек-лист", callback_data="q:checklist")
    kb.adjust(2)
    return kb.as_markup()


async def send_long(message: Message, text: str, markup: InlineKeyboardMarkup | None = None) -> None:
    parts = split_message(to_html(text))
    for i, part in enumerate(parts):
        last = i == len(parts) - 1
        await message.answer(part, reply_markup=markup if last else None)


def build_router(service: LegalService) -> Router:
    router = Router()
    simplify_waiting: set[int] = set()

    @router.message(CommandStart())
    @router.message(Command("help"))
    async def on_start(message: Message) -> None:
        await message.answer(START_TEXT)

    @router.message(Command("new"))
    async def on_new(message: Message) -> None:
        simplify_waiting.discard(message.from_user.id)
        had = service.reset(message.from_user.id)
        await message.answer("Документ удалён из памяти. Отправьте новый." if had else "Загруженных документов нет.")

    @router.message(Command("simplify"))
    async def on_simplify(message: Message) -> None:
        simplify_waiting.add(message.from_user.id)
        await message.answer("Пришлите фрагмент текста, который нужно объяснить простыми словами.")

    @router.message(F.document)
    async def on_document(message: Message) -> None:
        user_id = message.from_user.id
        doc = message.document
        name = doc.file_name or "document"
        try:
            service.check_access(user_id)
            if not name.lower().endswith(SUPPORTED_EXTENSIONS):
                raise BotError("Поддерживаются файлы PDF, DOCX и TXT. Также можно вставить текст сообщением.")
            if doc.file_size and doc.file_size > service.s.max_file_mb * 1024 * 1024:
                raise BotError(f"Файл больше {service.s.max_file_mb} МБ.")
            buffer = io.BytesIO()
            await message.bot.download(doc, destination=buffer)
            loaded = service.load_file(user_id, buffer.getvalue(), name)
            await message.answer(f"📄 Прочитал «{name}»: {len(loaded.text):,} знаков. Разбираю…".replace(",", " "))
            await run_analysis(message)
        except BotError as exc:
            await message.answer(exc.user_message)
        except Exception:
            log.exception("Ошибка при обработке файла")
            await message.answer("Не получилось обработать файл. Попробуйте другой формат.")

    async def run_analysis(message: Message) -> None:
        user_id = message.from_user.id
        status = await message.answer("⏳ Анализирую документ…")

        async def progress(i: int, total: int) -> None:
            try:
                await status.edit_text(f"⏳ Документ длинный, читаю часть {i} из {total}…")
            except Exception:
                pass

        try:
            async with ChatActionSender.typing(bot=message.bot, chat_id=message.chat.id):
                result = await service.analyze(user_id, progress)
        finally:
            try:
                await status.delete()
            except Exception:
                pass
        await send_long(message, result.text, None)
        await message.answer(
            "Выберите, что показать подробнее, или задайте вопрос по документу.\n\n" + prompts.DISCLAIMER,
            reply_markup=actions_keyboard(),
        )

    @router.callback_query(F.data.startswith("q:"))
    async def on_quick(call: CallbackQuery) -> None:
        key = call.data.split(":", 1)[1]
        await call.answer()
        try:
            async with ChatActionSender.typing(bot=call.bot, chat_id=call.message.chat.id):
                answer = await service.quick(call.from_user.id, key)
            await send_long(call.message, f"## {ACTION_TITLES.get(key, 'Ответ')}\n{answer}")
        except BotError as exc:
            await call.message.answer(exc.user_message)
        except Exception:
            log.exception("Ошибка быстрого действия")
            await call.message.answer("Что-то пошло не так. Попробуйте ещё раз.")

    @router.message(F.text & ~F.text.startswith("/"))
    async def on_text(message: Message) -> None:
        user_id = message.from_user.id
        text = message.text
        try:
            if user_id in simplify_waiting:
                simplify_waiting.discard(user_id)
                async with ChatActionSender.typing(bot=message.bot, chat_id=message.chat.id):
                    answer = await service.simplify(user_id, text)
                await send_long(message, answer)
                return

            has_doc = service.store.get(user_id) is not None
            looks_like_doc = len(text) >= 1500 or (not has_doc and len(text) >= 400)
            if looks_like_doc:
                service.load_text(user_id, text)
                await message.answer("📄 Принял текст как документ. Разбираю…")
                await run_analysis(message)
                return

            if not has_doc:
                await message.answer(NO_DOC)
                return
            async with ChatActionSender.typing(bot=message.bot, chat_id=message.chat.id):
                answer = await service.ask(user_id, text)
            await send_long(message, answer)
        except BotError as exc:
            await message.answer(exc.user_message)
        except Exception:
            log.exception("Ошибка при ответе на сообщение")
            await message.answer("Что-то пошло не так. Попробуйте ещё раз.")

    @router.message()
    async def on_other(message: Message) -> None:
        await message.answer("Я работаю с файлами PDF, DOCX, TXT и текстом. Фото и голосовые пока не читаю.")

    return router
