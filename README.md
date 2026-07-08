# Darslikdan videoga/slaydga — Telegram bot

Foydalanuvchi darslik matnini yoki sahifa suratini yuboradi → bot Claude API
orqali uni sodda tildagi sahnalarga bo'ladi → tanlangan formatga qarab
`.pptx` taqdimot yoki ovozli animatsion `.mp4` video tayyorlab qaytaradi.

## Fayllar

| Fayl | Vazifasi |
|---|---|
| `bot.py` | Asosiy bot — suhbat oqimi (daraja → matn/rasm → format → yuborish) |
| `content_generator.py` | Claude API chaqiruvi — matn yoki rasmni sahnalar JSON'iga aylantiradi |
| `slide_builder.py` | `python-pptx` bilan `.pptx` taqdimot yasaydi |
| `video_builder.py` | `edge-tts` + `Pillow` + `ffmpeg` bilan ovozli animatsion `.mp4` yasaydi |
| `requirements.txt` | Kerakli Python kutubxonalari |
| `.env.example` | Muhit o'zgaruvchilari namunasi |
| `Dockerfile` | Render uchun konteyner tavsifi (ffmpeg + shriftlarni o'z ichiga oladi) |
| `render.yaml` | Render'da bir bosishda (Blueprint) joylashtirish konfiguratsiyasi |

## O'rnatish

### 1. Talablar
- Python 3.10+
- **ffmpeg** tizimda o'rnatilgan bo'lishi shart:
  ```bash
  sudo apt install ffmpeg fonts-dejavu
  ```
  (video kadrlaridagi matn uchun DejaVu shriftlaridan foydalaniladi — odatda
  Ubuntu/Debian'da tayyor bo'ladi; bo'lmasa yuqoridagi buyruq bilan o'rnatiladi)

### 2. Telegram bot yaratish
1. Telegram'da [@BotFather](https://t.me/BotFather) bilan suhbatlashing
2. `/newbot` buyrug'ini yuboring, nom va username bering
3. Sizga beriladigan tokenni saqlab qo'ying

### 3. Anthropic API kalit
[console.anthropic.com](https://console.anthropic.com) dan API kalit oling.

### 4. Loyihani sozlash
```bash
pip install -r requirements.txt
cp .env.example .env
```
`.env` faylini oching va quyidagilarni to'ldiring:
```
TELEGRAM_BOT_TOKEN=BotFather'dan olingan token
ANTHROPIC_API_KEY=sk-ant-...
```

### 5. Ishga tushirish
```bash
python bot.py
```
Bot ishga tushgach, Telegram'da botingizga `/start` yuboring.

## Doimiy ishlab turishi uchun — GitHub + Render orqali joylashtirish

Bu loyihada `Dockerfile` va `render.yaml` allaqachon tayyor — Render buni avtomatik
tanib, ffmpeg va shriftlarni o'zi o'rnatadi. Sizga faqat quyidagi qadamlar kerak:

### 1. GitHub'ga yuklash
```bash
cd telegram-bot
git init
git add .
git commit -m "Darslikdan videoga bot"
```
GitHub'da yangi (bo'sh) repository yarating, so'ng:
```bash
git remote add origin https://github.com/FOYDALANUVCHI_NOMI/REPO_NOMI.git
git branch -M main
git push -u origin main
```
**Muhim:** `.env` faylini hech qachon push qilmang — u `.dockerignore`'da bor,
lekin git'ga ham qo'shilmasligi kerak (token/kalitlar oshkor bo'lmasligi uchun).

### 2. Render'da servis yaratish
1. [dashboard.render.com](https://dashboard.render.com) ga kiring
2. **New +** → **Blueprint** ni tanlang (bu `render.yaml`'ni avtomatik o'qiydi)
3. GitHub repo'ingizni ulang va tanlang
4. Render `render.yaml`'ni topib, **"darslik-bot"** nomli **Worker** servisini taklif qiladi — tasdiqlang

   *(Agar Blueprint ko'rinmasa: **New +** → **Background Worker** → repo tanlang →
   Environment: **Docker** ni tanlang — Render `Dockerfile`'ni avtomatik topadi)*

### 3. Maxfiy kalitlarni kiritish
Render sizdan `TELEGRAM_BOT_TOKEN` va `ANTHROPIC_API_KEY` qiymatlarini so'raydi
(chunki `render.yaml`'da `sync: false` qilib belgilangan — bu ularni GitHub'ga
push qilinmasligini ta'minlaydi). Ikkalasini ham shu yerda kiriting.

### 4. Deploy
**Apply**/**Create** tugmasini bosing. Render avtomatik ravishda:
- Docker image'ni quradi (shu jarayonda ffmpeg va shriftlar o'rnatiladi)
- Konteynerni ishga tushiradi (`python bot.py`)
- Loglar bo'limida `"Bot ishga tushdi."` yozuvini ko'rasiz — shu bot tayyor degani

Shundan keyin bot 24/7 ishlab turadi. Kodga o'zgartirish kiritib GitHub'ga
push qilsangiz (`autoDeploy: true` tufayli), Render avtomatik qayta joylaydi.

**Eslatma — narx:** `render.yaml`'da `plan: starter` ko'rsatilgan (Render'ning
bepul emas, arzon tarifi) — Background Worker'lar uchun bepul tarif odatda
mavjud emas. Render dashboard'ida narxlarni tekshiring va kerak bo'lsa
`render.yaml`'dagi `plan` qiymatini o'zingizga mosini tanlang.

## Boshqa hosting variantlari

## Cheklovlar va eslatmalar

- **Video generatsiyasi vaqt oladi** — har bir sahna uchun ovoz yaratiladi va
  kadrlar chiziladi, shuning uchun 5 sahnali video ~1-2 daqiqa vaqt olishi mumkin.
- **Ovoz**: `edge-tts` orqali `uz-UZ-MadinaNeural` ovozi ishlatiladi (bepul,
  Microsoft Edge TTS xizmati). Agar o'chirilgan/mavjud bo'lmasa,
  `video_builder.py` ichidagi `VOICE` o'zgaruvchisini `uz-UZ-SardorNeural`
  ga almashtiring.
- **Emoji o'rniga raqamli doira**: video kadrlarida asl emoji shakli o'rniga
  rangli doira ichida sahna raqami chiziladi — chunki server shriftlarida rangli
  emoji glif ko'rinishi ishonchli ishlamaydi. Slaydlarda (`.pptx`) esa haqiqiy
  emoji chiqadi, chunki uni PowerPoint o'zi chizadi.
- **Bitta API kalit — barcha foydalanuvchilar uchun**: hozirgi tuzilishda bot
  egasining Anthropic kaliti barcha foydalanuvchilar uchun ishlatiladi. Ko'p
  odam faol foydalansa, API xarajatlarini kuzatib turing.
- Kod xatoliklarni ushlab, foydalanuvchiga tushunarli xabar bilan qaytaradi,
  lekin nazoratsiz production muhitda qo'shimcha rate-limit va xatolarni
  monitoring qilish tavsiya etiladi.
