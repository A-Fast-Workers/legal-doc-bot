"""Проверка без Telegram: python -m legalbot.cli файл [--demo] [-q "вопрос"]

--demo использует заглушку вместо GigaChat (ключ не нужен).
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from .config import load_settings
from .llm import FakeLLM
from .service import LegalService


async def amain(args: argparse.Namespace) -> int:
    settings = load_settings(require_telegram=False, require_llm=not args.demo)
    if args.demo:
        llm = FakeLLM()
    else:
        from .llm import GigaChatLLM
        llm = GigaChatLLM(settings)
    service = LegalService(llm, settings)

    with open(args.file, "rb") as fh:
        doc = service.load_file(1, fh.read(), args.file)
    print(f"Прочитано знаков: {len(doc.text)}", file=sys.stderr)

    async def progress(i, total):
        print(f"часть {i}/{total}", file=sys.stderr)

    result = await service.analyze(1, progress)
    print(f"[режим: {result.mode}, частей: {result.chunks_used}]\n")
    print(result.text)
    for q in args.question or []:
        print(f"\n--- Вопрос: {q}\n{await service.ask(1, q)}")
    if args.demo:
        print(f"\n(вызовов заглушки: {len(llm.calls)})", file=sys.stderr)
    return 0


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("file")
    p.add_argument("--demo", action="store_true")
    p.add_argument("-q", "--question", action="append")
    raise SystemExit(asyncio.run(amain(p.parse_args())))


if __name__ == "__main__":
    main()
