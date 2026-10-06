# Юр-бот: разбор документов в Telegram на GigaChat

![tests](../../actions/workflows/tests.yml/badge.svg)


Принимает PDF, DOCX, TXT или вставленный текст и выдаёт: суть, ключевые условия, риски (🔴🟡🟢 с номерами пунктов), чего не хватает, что проверить. Дальше отвечает на вопросы по документу. Все ответы на русском.

## Требования
Python 3.11–3.13 (на 3.14 у части зависимостей может не быть готовых сборок), аккаунт разработчика GigaChat, бот в @BotFather.

## Запуск
0. `git clone <адрес репозитория> && cd legal_bot`
1. Токен бота: @BotFather → /newbot.
2. Ключ GigaChat API: developers.sber.ru → Studio → API-ключ (scope `GIGACHAT_API_PERS` для физлиц).
3. `cp .env.example .env` и впишите `TELEGRAM_BOT_TOKEN`, `GIGACHAT_CREDENTIALS`.
4. Сертификаты: скачайте корневой сертификат Минцифры и укажите путь в `GIGACHAT_CA_BUNDLE`. Если не указать, проверка SSL отключена (`GIGACHAT_VERIFY_SSL=false`), для продакшена так не делайте.
5. Запуск:
   - локально: `pip install -r requirements.txt && python -m legalbot.main`
   - Docker: `docker compose up -d --build`

## Проверка без Telegram
- Тесты (без внешних пакетов, кроме pypdf/python-docx/reportlab): `python -m unittest discover -s tests -t .`
- Демо без ключа: `python -m legalbot.cli examples/dogovor.txt --demo`
- Реальный GigaChat без Telegram: `python -m legalbot.cli examples/dogovor.txt -q "Какая неустойка?"` (нужен `GIGACHAT_CREDENTIALS` в окружении)

## Команды бота
`/start`, `/help`, `/new` (забыть документ), `/simplify` (объяснить фрагмент простым языком). Кнопки после разбора: риски, деньги и штрафы, сроки, чек-лист.

## Как устроено
- `extract.py` текст из PDF/DOCX (включая таблицы)/TXT; сканы без текстового слоя отклоняются с пояснением.
- `analyzer.py` короткие документы идут одним запросом; длинные: разбиение на части, выжимки, итоговый разбор. Вопросы: подбор релевантных фрагментов (упрощённый TF-IDF), в модель уходит только нужное.
- `llm.py` GigaChat с семафором (бесплатный тариф — один поток), повторами и понятными ошибками.
- `storage.py`, `ratelimit.py` сессии в памяти с TTL (диск не используется), лимит запросов на пользователя.
- `handlers.py` только aiogram-обвязка поверх `service.py`.

## Разработка
`pip install -r requirements-dev.txt`, затем `python -m unittest discover -s tests -t .`. Тесты не обращаются к сети и GigaChat: модель подменяется `FakeLLM`. CI запускает их на Python 3.11–3.13.

Лицензия: MIT. Сообщения об уязвимостях: см. `SECURITY.md`.

## Ограничения
- Это не юридическая консультация (дисклеймер добавлен в ответы). Модель может ошибаться.
- Нет OCR: сканы и фото не читаются.
- Тексты документов передаются в GigaChat (облако Сбера). Для конфиденциальных документов проверьте условия обработки данных и при необходимости обезличивайте их.
- Условия бесплатных лимитов и адрес доступа GigaChat для новых клиентов могут меняться, проверяйте на developers.sber.ru.
