"""PDF fayllardan matn ajratib olish uchun yordamchi funksiyalar."""

from pypdf import PdfReader


def get_page_count(path: str) -> int:
    """PDF fayldagi sahifalar sonini qaytaradi."""
    reader = PdfReader(path)
    return len(reader.pages)


def extract_text(path: str, start_page: int | None = None, end_page: int | None = None) -> str:
    """
    PDF fayldan matnni ajratib oladi.

    start_page, end_page — 1 dan boshlanuvchi, ikkalasi ham kiritiladi (inclusive).
    Agar berilmasa, butun hujjat o'qiladi.
    """
    reader = PdfReader(path)
    total = len(reader.pages)

    start = (start_page - 1) if start_page else 0
    end = end_page if end_page else total

    start = max(0, start)
    end = min(total, end)

    chunks = []
    for i in range(start, end):
        page_text = reader.pages[i].extract_text() or ""
        if page_text.strip():
            chunks.append(page_text)

    return "\n\n".join(chunks)


def truncate_for_model(text: str, max_chars: int = 60000) -> str:
    """
    Juda katta matnlarni AI modeliga yuborishdan oldin qisqartiradi
    (token/narx chegarasidan chiqib ketmaslik uchun).
    """
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n[...matn qisqartirildi...]"
