# CS2 Shop Bot

Telegram orqali CS2 skinlar sotish boti — admin panel, AI maslahatchi, konkurs, xizmatlar va statistika.

## Xususiyatlar

- Skin do'koni (pichoqlar, miltiqlar, keyslar, stikerlar, breloklar)
- Admin panel (statistika, obunachilar, sotilganlar, xabarlar)
- AI maslahatchi (Google Gemini — ko'p kalit, avtomatik almashish)
- Konkurs tizimi (har xarid = 1 bilet)
- Xizmatlar: Telegram Premium, Stars, Steam balans
- PostgreSQL (Render) yoki SQLite (lokal)

## Lokal ishga tushirish

```bash
pip install -r requirements.txt
cp config.example.json config.json
# config.json ni to'ldiring
python bot.py
```

## Render.com ga joylash

1. GitHub repoga yuklang
2. [render.com](https://render.com) → New → Blueprint → `render.yaml`
3. Environment Variables:
   - `BOT_TOKEN` — Telegram bot token
   - `ADMIN_IDS` — admin ID lar (vergul bilan: `123,456`)
   - `CARD_INFO` — karta ma'lumoti
   - `GEMINI_API_KEYS` — AI uchun (vergul bilan: `key1,key2,key3`)
   - `CHANNEL_ID` — kanal @username yoki ID (obunachilar soni uchun)
4. PostgreSQL avtomatik yaratiladi (bepul 1GB)

## UptimeRobot (bot uxlamasligi uchun)

1. [uptimerobot.com](https://uptimerobot.com) da ro'yxatdan o'ting
2. **Add Monitor** → HTTP(s)
3. URL: `https://SIZNING-APP.render.com/` (Render web service URL)
4. Interval: **5 daqiqa**
5. Bot health server `/` da `OK` qaytaradi

## Admin panel

Botda `/adminpanel` (yoki siz sozlagan buyruq) yoki **Admin Panel** tugmasi.

Yangi bo'limlar:
- **Statistika** — bugun/hafta/oy daromad, foydalanuvchilar
- **Obunachilar** — kanal va bot foydalanuvchilari
- **Sotilganlar** — kim nima sotib olgan
- **Foydalanuvchi xabarlari** — taklif va so'rovlar
- **Konkurs** — yaratish va to'xtatish
- **Xizmatlar** — Premium, Stars, Steam sozlamalari

## AI sozlash

Admin Panel → Xizmatlar sozlamalari → Gemini API kalitlari

Bepul kalit: https://aistudio.google.com/apikey (30 tagacha qo'shish mumkin)

## Kanal obunachilari

Bot kanalda **admin** bo'lishi kerak. Admin Panel → Obunachilar → Kanal ID o'rnatish.

## Eslatma

`config.json` gitga kirmaydi (`.gitignore`). Renderda env orqali sozlang.
