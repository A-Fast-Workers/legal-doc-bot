"""Превращает ответ модели (markdown-подобный) в безопасный HTML для Telegram."""
from __future__ import annotations

import html
import re

TG_LIMIT = 4096


def to_html(text: str) -> str:
    out: list[str] = []
    for raw in text.strip().split("\n"):
        line = html.escape(raw.rstrip(), quote=False)
        m = re.match(r"^#{1,6}\s*(.+)$", line)
        if m:
            out.append(f"\n<b>{m.group(1).strip()}</b>")
            continue
        line = re.sub(r"^\s*[-*•]\s+", "• ", line)
        line = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", line)
        line = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", line)
        out.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


def _close_tags(chunk: str) -> tuple[str, list[str]]:
    """Закрывает открытые <b>/<i> в конце куска и возвращает список для переоткрытия."""
    stack: list[str] = []
    for m in re.finditer(r"<(/?)(b|i)>", chunk):
        if m.group(1):
            if stack and stack[-1] == m.group(2):
                stack.pop()
        else:
            stack.append(m.group(2))
    closing = "".join(f"</{t}>" for t in reversed(stack))
    return chunk + closing, stack


def split_message(html_text: str, limit: int = TG_LIMIT) -> list[str]:
    """Делит текст на сообщения до limit знаков по границам строк, не ломая теги."""
    if len(html_text) <= limit:
        return [html_text]
    budget = limit - 16   # запас под закрывающие/открывающие теги
    parts: list[str] = []
    current = ""
    for line in html_text.split("\n"):
        while len(line) > budget:        # очень длинная строка: режем по пробелу
            cut = line.rfind(" ", 0, budget)
            cut = cut if cut > budget // 2 else budget
            if current:
                parts.append(current)
                current = ""
            parts.append(line[:cut])
            line = line[cut:].lstrip()
        if len(current) + len(line) + 1 > budget and current:
            parts.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    if current:
        parts.append(current)

    fixed: list[str] = []
    reopen: list[str] = []
    for p in parts:
        p = "".join(f"<{t}>" for t in reopen) + p
        p, reopen = _close_tags(p)
        fixed.append(p)
    return fixed
