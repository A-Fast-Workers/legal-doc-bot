"""Разбиение текста на части и подбор фрагментов под вопрос."""
from __future__ import annotations

import math
import re
from collections import Counter

_SENTENCE_END = re.compile(r"(?<=[.!?;])\s+")
_WORD = re.compile(r"\w+", re.UNICODE)


def _hard_split(piece: str, max_chars: int) -> list[str]:
    """Режет слишком длинный абзац по предложениям, а если и так не помещается, по длине."""
    out: list[str] = []
    current = ""
    for sentence in _SENTENCE_END.split(piece):
        while len(sentence) > max_chars:
            if current:
                out.append(current)
                current = ""
            out.append(sentence[:max_chars])
            sentence = sentence[max_chars:]
        if len(current) + len(sentence) + 1 > max_chars and current:
            out.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        out.append(current)
    return out


def split_text(text: str, max_chars: int) -> list[str]:
    """Собирает строки в части не длиннее max_chars, не разрывая пункты без нужды."""
    if max_chars <= 0:
        raise ValueError("max_chars должно быть положительным")
    chunks: list[str] = []
    current = ""
    for line in text.split("\n"):
        pieces = [line] if len(line) <= max_chars else _hard_split(line, max_chars)
        for piece in pieces:
            if len(current) + len(piece) + 1 > max_chars and current:
                chunks.append(current)
                current = piece
            else:
                current = f"{current}\n{piece}" if current else piece
    if current.strip():
        chunks.append(current)
    return [c.strip() for c in chunks if c.strip()]


def _stems(text: str) -> list[str]:
    """Грубая основа слова: первые 5 букв (достаточно для русской морфологии в поиске)."""
    return [w[:5] for w in _WORD.findall(text.lower()) if len(w) >= 3]


def select_relevant(chunks: list[str], question: str, k: int = 4, head_chars: int = 800) -> list[str]:
    """Выбирает k частей, лучше всего подходящих вопросу (упрощённый TF-IDF).

    Возвращает части в порядке следования в документе. Начало документа
    (стороны и предмет) добавляется отдельно вызывающим кодом.
    """
    if not chunks:
        return []
    if len(chunks) <= k:
        return list(chunks)

    q_stems = set(_stems(question))
    if not q_stems:
        return list(chunks[:k])

    tokenized = [Counter(_stems(c)) for c in chunks]
    n = len(chunks)
    df = Counter()
    for counts in tokenized:
        for stem in q_stems:
            if stem in counts:
                df[stem] += 1

    scores: list[float] = []
    for counts in tokenized:
        total = sum(counts.values()) or 1
        score = 0.0
        for stem in q_stems:
            tf = counts.get(stem, 0) / total
            idf = math.log(1 + n / (1 + df[stem]))
            score += tf * idf
        scores.append(score)

    best = sorted(range(n), key=lambda i: scores[i], reverse=True)[:k]
    if all(scores[i] == 0 for i in best):
        return list(chunks[:k])
    return [chunks[i] for i in sorted(best)]
