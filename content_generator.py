"""
Claude API orqali darslik matnini (yoki rasmini) sodda, animatsion
sahnalar ro'yxatiga aylantiradi. Slayd va video quruvchi modullar
shu bitta funksiyadan foydalanadi.
"""

import base64
import json
import requests

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-4-6"

LEVEL_PROMPTS = {
    "1-4": "1-4 sinf, juda sodda so'zlar, qisqa va aniq gaplar",
    "5-9": "5-9 sinf, tushunarli va qiziqarli tilda",
    "10-11": "10-11 sinf yoki talaba, biroz ilmiyroq lekin baribir sodda",
}

SYSTEM_PROMPT = """Sen bolalar va o'quvchilar uchun murakkab darslik matnlarini sodda,
qiziqarli animatsion videoga/taqdimotga aylantiruvchi ssenarist san'atkorsan.

Agar senga rasm berilgan bo'lsa, avval undagi matnni diqqat bilan o'qi (sarlavha,
asosiy matn, ajratib ko'rsatilgan qismlar), so'ng shu mazmun asosida ishla.

Berilgan matnni {level} darajasiga mos, sodda o'zbek tilida, aniq {n_scenes} ta
ketma-ket sahnaga bo'l. Har bir sahna:
- heading: qisqa sarlavha (2-4 so'z)
- text: bitta sodda, tushunarli gap (8-14 so'z)
- emoji: mavzuga mos bitta emoji

Javobni boshqa hech qanday so'z, izoh yoki markdown belgilarisiz, FAQAT quyidagi
JSON massiv sifatida qaytar (qo'shtirnoqlar to'g'ridan-to'g'ri bo'lishi shart,
apostrof ishlatma):
[{{"heading":"...", "text":"...", "emoji":"..."}}]"""


def _extract_json_array(raw: str):
    raw = raw.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("[")
        end = raw.rfind("]")
        if start == -1 or end == -1 or end < start:
            raise ValueError(f"JSON topilmadi: {raw[:300]}")
        return json.loads(raw[start:end + 1])


def _call_claude(api_key: str, system: str, user_content):
    response = requests.post(
        ANTHROPIC_API_URL,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        json={
            "model": MODEL,
            "max_tokens": 1200,
            "system": system,
            "messages": [{"role": "user", "content": user_content}],
        },
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()
    if data.get("error"):
        raise RuntimeError(f"API xatosi: {data['error'].get('message', data['error'])}")
    raw = "".join(block.get("text", "") for block in data.get("content", []))
    if not raw.strip():
        raise RuntimeError("Modeldan bo'sh javob keldi.")
    scenes = _extract_json_array(raw)
    if not isinstance(scenes, list) or not scenes:
        raise RuntimeError("Sahnalar ro'yxati bo'sh keldi.")
    return scenes


def generate_scenes_from_text(text: str, level_key: str, api_key: str, n_scenes: int = 5):
    level = LEVEL_PROMPTS.get(level_key, LEVEL_PROMPTS["5-9"])
    system = SYSTEM_PROMPT.format(level=level, n_scenes=n_scenes)
    return _call_claude(api_key, system, text)


def generate_scenes_from_image(image_bytes: bytes, media_type: str, level_key: str,
                                api_key: str, n_scenes: int = 5):
    level = LEVEL_PROMPTS.get(level_key, LEVEL_PROMPTS["5-9"])
    system = SYSTEM_PROMPT.format(level=level, n_scenes=n_scenes)
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    user_content = [
        {
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": b64},
        },
        {
            "type": "text",
            "text": "Bu darslik sahifasining rasmi. Undagi matnni o'qib, "
                    "yuqoridagi ko'rsatmaga muvofiq sahnalarga bo'l.",
        },
    ]
    return _call_claude(api_key, system, user_content)
