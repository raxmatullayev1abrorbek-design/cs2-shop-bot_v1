import logging
import json
import time
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
MODELS_TO_TRY = [
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
]
COOLDOWN_SECONDS = 60
MAX_KEYS_ON_QUOTA = 3


def normalize_api_key(key: str) -> str:
    return "".join(str(key).split()).strip()


class GeminiKeyRotator:
    def __init__(self):
        self._index = 0
        self._cooldown_until = {}

    def reset(self):
        self._index = 0
        self._cooldown_until = {}

    def _is_available(self, idx: int) -> bool:
        return time.time() >= self._cooldown_until.get(idx, 0)

    def mark_limited(self, idx: int):
        self._cooldown_until[idx] = time.time() + COOLDOWN_SECONDS

    def _next_index(self, total: int) -> int | None:
        if total == 0:
            return None
        for _ in range(total):
            idx = self._index % total
            self._index += 1
            if self._is_available(idx):
                return idx
        return None


_rotator = GeminiKeyRotator()


def _request_gemini(api_key: str, model: str, payload: dict) -> str:
    url = f"{GEMINI_BASE}/{model}:generateContent"
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return data["candidates"][0]["content"]["parts"][0]["text"]


def _call_gemini(api_key: str, system_text: str, user_text: str) -> str:
    api_key = normalize_api_key(api_key)
    payloads = [
        {
            "system_instruction": {"parts": [{"text": system_text}]},
            "contents": [{"role": "user", "parts": [{"text": user_text}]}],
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1024},
        },
        {
            "contents": [{"parts": [{"text": f"{system_text}\n\n{user_text}"}]}],
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1024},
        },
    ]
    last_code = 0
    for model in MODELS_TO_TRY:
        for payload in payloads:
            try:
                return _request_gemini(api_key, model, payload)
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", errors="ignore")
                last_code = e.code
                logger.warning(f"Gemini {model} HTTP {e.code}: {body[:120]}")
                if e.code == 404:
                    break
                if e.code == 429:
                    raise
                if e.code in (400, 401, 403):
                    raise
                continue
    raise urllib.error.HTTPError("", last_code or 500, "fail", None, None)


def _quota_exhausted_message(total_keys: int) -> str:
    return (
        "⏳ <b>Gemini limiti tugagan</b>\n\n"
        "Kalitlaringiz ishlayapti, lekin bugungi bepul limit tugagan.\n\n"
        "📌 <b>Muhim:</b> Bir Gmail akkauntdan 20 ta kalit olsangiz ham — "
        "limit <b>1 ta</b> bo'ladi! Har xil akkaunt kerak.\n\n"
        "✅ Nima qilish mumkin:\n"
        "• 1-24 soat kuting (limit yangilanadi)\n"
        "• Boshqa Gmail akkauntlardan yangi kalit oling\n"
        "• <a href=\"https://aistudio.google.com\">AI Studio</a> da billing yoqing\n\n"
        f"📊 Sozlangan kalitlar: {total_keys} ta"
    )


def _call_with_keys(api_keys: list, system_text: str, user_text: str) -> str:
    clean_keys = list(dict.fromkeys(
        normalize_api_key(k) for k in api_keys if k and len(normalize_api_key(k)) > 10
    ))

    if not clean_keys:
        return (
            "❌ Gemini API kalitlari sozlanmagan.\n\n"
            "Admin Panel → Xizmatlar → Gemini API kalitlari"
        )

    quota_hits = 0
    tried = 0
    total = len(clean_keys)

    while tried < total and tried < MAX_KEYS_ON_QUOTA + 2:
        idx = _rotator._next_index(total)
        if idx is None:
            break
        key = clean_keys[idx]
        tried += 1
        try:
            result = _call_gemini(key, system_text, user_text)
            logger.info(f"Gemini javob berdi (kalit #{idx + 1})")
            _rotator.reset()
            return result
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="ignore")
            except Exception:
                pass
            logger.error(f"Gemini kalit #{idx + 1} HTTP {e.code}: {body[:200]}")

            if e.code == 429 or "quota" in body.lower() or "RESOURCE_EXHAUSTED" in body:
                quota_hits += 1
                _rotator.mark_limited(idx)
                if quota_hits >= MAX_KEYS_ON_QUOTA:
                    return _quota_exhausted_message(total)
                continue

            if e.code in (400, 401, 403):
                _rotator.mark_limited(idx)
                continue

            _rotator.mark_limited(idx)
            continue
        except Exception as e:
            logger.error(f"Gemini kalit #{idx + 1}: {e}")
            _rotator.mark_limited(idx)
            continue

    if quota_hits > 0:
        return _quota_exhausted_message(total)

    return (
        "❌ AI javob bera olmadi.\n\n"
        "Kalitlarni tekshiring: https://aistudio.google.com/apikey"
    )


def get_skin_advice(api_keys: list, user_question: str, available_skins: list = None) -> str:
    skin_context = ""
    if available_skins:
        lines = [
            f"- {s['item_name']} | {s['name']} — {s['price']:,.0f} so'm"
            for s in available_skins[:12]
        ]
        skin_context = "\n\nDo'kondagi mos skinlar:\n" + "\n".join(lines)

    system = (
        "Siz CS2 skin maslahatchisisiz. Foydalanuvchiga o'zbek tilida "
        "qisqa va tushunarli javob bering."
    )
    return _call_with_keys(api_keys, system, user_question + skin_context)


def find_skins_for_request(api_keys: list, user_request: str, db_skins: list) -> str:
    if not db_skins:
        return "😔 So'rovingiz bo'yicha hozircha mos skin topilmadi."

    skin_list = "\n".join(
        f"ID:{s['id']} | {s['item_name']} | {s['name']} | {s['price']:,.0f} so'm"
        for s in db_skins[:15]
    )
    system = "Siz CS2 skin qidiruv yordamchisisiz. O'zbek tilida javob bering."
    user = f"So'rov: {user_request}\n\nTopilgan skinlar:\n{skin_list}"
    return _call_with_keys(api_keys, system, user)
