"""Разбор документа и ответы на вопросы поверх LLM."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Awaitable, Callable, Optional

from . import prompts
from .chunking import select_relevant, split_text
from .config import Settings
from .llm import LLM

Progress = Optional[Callable[[int, int], Awaitable[None]]]


@dataclass
class Analysis:
    text: str
    chunks_used: int = 1
    mode: str = "single"     # single / map-reduce


class Analyzer:
    def __init__(self, llm: LLM, settings: Settings):
        self.llm = llm
        self.s = settings

    async def analyze(self, doc_text: str, progress: Progress = None) -> Analysis:
        if len(doc_text) <= self.s.single_pass_chars:
            answer = await self.llm.complete(
                prompts.SYSTEM, prompts.ANALYSIS_TEMPLATE.format(text=doc_text), max_tokens=2000
            )
            return Analysis(answer, 1, "single")

        parts = split_text(doc_text, self.s.chunk_chars)
        summaries: list[str] = []
        for i, part in enumerate(parts, 1):
            if progress:
                await progress(i, len(parts))
            summary = await self.llm.complete(
                prompts.SYSTEM,
                prompts.CHUNK_SUMMARY_TEMPLATE.format(index=i, total=len(parts), text=part),
                max_tokens=900,
            )
            summaries.append(f"[Часть {i}]\n{summary}")

        merged = "\n\n".join(summaries)
        # выжимки тоже могут не поместиться: сжимаем ещё раз
        while len(merged) > self.s.single_pass_chars:
            groups = split_text(merged, self.s.chunk_chars)
            if len(groups) <= 1:
                merged = merged[: self.s.single_pass_chars]
                break
            compact = []
            for g in groups:
                compact.append(await self.llm.complete(
                    prompts.SYSTEM,
                    prompts.CHUNK_SUMMARY_TEMPLATE.format(index=1, total=1, text=g),
                    max_tokens=900,
                ))
            new = "\n\n".join(compact)
            if len(new) >= len(merged):   # не сжимается: защита от бесконечного цикла
                merged = merged[: self.s.single_pass_chars]
                break
            merged = new

        answer = await self.llm.complete(
            prompts.SYSTEM, prompts.MERGE_TEMPLATE.format(text=merged), max_tokens=2000
        )
        return Analysis(answer, len(parts), "map-reduce")

    async def ask(self, doc_text: str, question: str) -> str:
        head = doc_text[:1500]
        if len(doc_text) <= self.s.single_pass_chars:
            fragments = doc_text
        else:
            chunks = split_text(doc_text, self.s.qa_chunk_chars)
            chosen = select_relevant(chunks, question, k=4)
            fragments = "\n\n---\n\n".join(chosen)
        return await self.llm.complete(
            prompts.SYSTEM,
            prompts.QA_TEMPLATE.format(head=head, fragments=fragments, question=question.strip()),
            max_tokens=1200,
        )

    async def simplify(self, fragment: str) -> str:
        return await self.llm.complete(
            prompts.SYSTEM, prompts.SIMPLIFY_TEMPLATE.format(text=fragment[:6000]), max_tokens=1200
        )
