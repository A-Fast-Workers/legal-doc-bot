"""Извлечение текста из PDF, DOCX и TXT."""
from __future__ import annotations

import io
import os
import re
from dataclasses import dataclass
from typing import Optional

from .errors import DocumentError

SUPPORTED_EXTENSIONS = (".pdf", ".docx", ".txt")


@dataclass
class ExtractedDoc:
    text: str
    kind: str                 # pdf / docx / txt / paste
    pages: Optional[int] = None


def normalize(text: str) -> str:
    """Чистит текст: неразрывные пробелы, переносы слов, лишние пустые строки."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\xa0", " ").replace("­", "").replace("​", "")
    text = re.sub(r"(\w)-\n(?=[a-zа-яё])", r"\1", text)      # перенос слова на другую строку
    text = re.sub(r"[ \t]+", " ", text)
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _read_pdf(data: bytes) -> tuple[str, int]:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            try:
                ok = reader.decrypt("")
            except Exception:
                ok = 0
            if not ok:
                raise DocumentError("PDF защищён паролем. Снимите защиту и отправьте файл снова.")
        pages = [(page.extract_text() or "") for page in reader.pages]
    except DocumentError:
        raise
    except Exception as exc:
        raise DocumentError("Не удалось прочитать PDF. Файл повреждён или имеет необычный формат.") from exc

    text = "\n\n".join(pages)
    if len(text.strip()) < 40 * max(1, len(pages)):
        raise DocumentError(
            "В PDF почти нет текста: похоже, это скан или фото. "
            "Бот пока не умеет распознавать изображения. Пришлите файл с текстовым слоем, DOCX или TXT."
        )
    return text, len(pages)


def _read_docx(data: bytes) -> str:
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    try:
        document = Document(io.BytesIO(data))
    except Exception as exc:
        raise DocumentError("Не удалось прочитать DOCX. Файл повреждён или защищён.") from exc

    parts: list[str] = []
    for child in document.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            parts.append(Paragraph(child, document).text)
        elif tag == "tbl":
            table = Table(child, document)
            for row in table.rows:
                cells: list[str] = []
                for cell in row.cells:
                    value = cell.text.strip().replace("\n", " ")
                    if not cells or cells[-1] != value:   # склеенные ячейки дают дубли
                        cells.append(value)
                parts.append(" | ".join(cells))
    return "\n".join(parts)


def _read_txt(data: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1251"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def extract_text(data: bytes, filename: str, max_chars: int) -> ExtractedDoc:
    ext = os.path.splitext(filename.lower())[1]
    pages: Optional[int] = None

    if ext == ".pdf":
        raw, pages = _read_pdf(data)
        kind = "pdf"
    elif ext == ".docx":
        raw, kind = _read_docx(data), "docx"
    elif ext == ".txt":
        raw, kind = _read_txt(data), "txt"
    elif ext == ".doc":
        raise DocumentError("Формат .doc устарел. Сохраните документ как DOCX или PDF и отправьте снова.")
    else:
        raise DocumentError("Поддерживаются файлы PDF, DOCX и TXT. Также можно вставить текст сообщением.")

    return finalize(raw, kind, max_chars, pages)


def finalize(raw: str, kind: str, max_chars: int, pages: Optional[int] = None) -> ExtractedDoc:
    text = normalize(raw)
    if len(text) < 80:
        raise DocumentError("В документе слишком мало текста для разбора.")
    if len(text) > max_chars:
        raise DocumentError(
            f"Документ слишком большой: около {len(text) // 1000} тыс. знаков, "
            f"максимум {max_chars // 1000} тыс. Разделите его на части и отправьте по отдельности."
        )
    return ExtractedDoc(text=text, kind=kind, pages=pages)
