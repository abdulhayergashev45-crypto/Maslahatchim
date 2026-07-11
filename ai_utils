"""Claude API yordamida kitob matnidan taqdimot rejasini yaratish."""

import json
import os
import re

from anthropic import Anthropic

MODEL = "claude-sonnet-5"

SYSTEM_PROMPT = """Sen tajribali o'qituvchi va metodistsan. Senga darslik matni beriladi.
Vazifang — shu matn asosida abituriyentlar uchun taqdimot (slaydlar) rejasini tuzish.

Qat'iy qoidalar:
- Faqat berilgan matndagi faktlarga tayan, o'zingdan hech narsa qo'shma yoki o'ylab topma.
- Har bir slayd aniq bir kichik mavzuga bag'ishlangan bo'lsin.
- Har bir slaydda 3-5 ta qisqa va aniq punkt (bullet) bo'lsin, har biri 1-2 gap.
- 6 dan 12 gacha slayd yarat (matn hajmiga qarab).
- Birinchi slayd — sarlavha slaydi (title, subtitle).
- Oxirgi slayd — xulosa slaydi (asosiy fikrlar ro'yxati).
- Faqat O'zbek tilida yoz.

Javobni FAQAT quyidagi JSON formatida qaytar, hech qanday qo'shimcha matn, izoh yoki markdown belgisisiz:

{
  "deck_title": "Taqdimot sarlavhasi",
  "deck_subtitle": "Qisqa tavsif",
  "slides": [
    {
      "type": "title",
      "title": "...",
      "subtitle": "..."
    },
    {
      "type": "content",
      "title": "...",
      "bullets": ["...", "..."]
    },
    {
      "type": "conclusion",
      "title": "Xulosa",
      "bullets": ["...", "..."]
    }
  ]
}
"""


def _extract_json(raw: str) -> dict:
    """Modeldan kelgan javobdan JSON qismini xavfsiz ajratib oladi."""
    raw = raw.strip()
    raw = re.sub(r"^```(json)?", "", raw).strip()
    raw = re.sub(r"```$", "", raw).strip()
    return json.loads(raw)


def generate_slide_plan(text: str, topic_hint: str = "") -> dict:
    """
    Berilgan matn asosida taqdimot rejasini (JSON) qaytaradi.
    topic_hint — foydalanuvchi bergan qo'shimcha ko'rsatma (masalan, mavzu nomi).
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY topilmadi. .env faylini tekshiring.")

    client = Anthropic(api_key=api_key)

    user_content = text
    if topic_hint:
        user_content = f"Mavzu/bo'lim nomi: {topic_hint}\n\nMatn:\n{text}"

    response = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )

    raw_text = "".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    )
    return _extract_json(raw_text)
