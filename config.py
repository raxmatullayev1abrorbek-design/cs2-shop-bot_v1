import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

DEFAULT_CONFIG = {
    "bot_token": "",
    "admins": [],
    "admin_command": "adminpanel",
    "card_info": "Karta raqamini bu yerga kiriting",
    "channel_id": "",
    "gemini_api_keys": [],
    "services": {
        "premium": {
            "enabled": True,
            "title": "Telegram Premium",
            "plans": [
                {"id": "1", "name": "1 oy", "price": 89000, "enabled": True},
                {"id": "2", "name": "3 oy", "price": 240000, "enabled": True},
                {"id": "3", "name": "6 oy", "price": 450000, "enabled": True},
                {"id": "4", "name": "12 oy", "price": 850000, "enabled": True}
            ]
        },
        "stars": {
            "enabled": True,
            "title": "Telegram Stars",
            "plans": [
                {"id": "1", "name": "50 ta", "price": 8000, "enabled": True},
                {"id": "2", "name": "100 ta", "price": 15000, "enabled": True},
                {"id": "3", "name": "250 ta", "price": 35000, "enabled": True},
                {"id": "4", "name": "500 ta", "price": 65000, "enabled": True}
            ]
        },
        "steam_topup": {
            "enabled": True,
            "title": "Steam balans",
            "plans": [
                {"id": "1", "name": "50 000 so'm", "price": 50000, "enabled": True},
                {"id": "2", "name": "100 000 so'm", "price": 100000, "enabled": True},
                {"id": "3", "name": "200 000 so'm", "price": 200000, "enabled": True},
                {"id": "4", "name": "Boshqa summa", "price": 0, "enabled": True}
            ]
        }
    }
}


class Config:
    def __init__(self):
        if not os.path.exists(CONFIG_PATH):
            self._save(DEFAULT_CONFIG)
        self._data = self._load()
        self._apply_env_overrides()
        self._db = None

    def _get_db(self):
        if self._db is None:
            from database import Database
            self._db = Database()
        return self._db

    def _use_db_settings(self):
        return bool(os.environ.get("DATABASE_URL", ""))

    def _load(self):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save(self, data=None):
        if data is None:
            data = self._data
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _reload(self):
        self._data = self._load()
        self._apply_env_overrides()

    def _apply_env_overrides(self):
        token = os.environ.get("BOT_TOKEN")
        if token:
            self._data["bot_token"] = token
        admins = os.environ.get("ADMIN_IDS")
        if admins:
            self._data["admins"] = [int(x.strip()) for x in admins.split(",") if x.strip()]
        cmd = os.environ.get("ADMIN_COMMAND")
        if cmd:
            self._data["admin_command"] = cmd
        card = os.environ.get("CARD_INFO")
        if card:
            self._data["card_info"] = card
        channel = os.environ.get("CHANNEL_ID")
        if channel:
            self._data["channel_id"] = channel
        gemini = os.environ.get("GEMINI_API_KEYS")
        if gemini:
            keys = []
            for part in gemini.replace(",", "\n").split("\n"):
                k = part.strip()
                if k and len(k) > 10:
                    keys.append(k)
            self._data["gemini_api_keys"] = keys

    def get_bot_token(self):
        self._reload()
        return self._data.get("bot_token", "")

    def get_admins(self):
        self._reload()
        return self._data.get("admins", [])

    def add_admin(self, user_id: int):
        self._reload()
        if user_id not in self._data["admins"]:
            self._data["admins"].append(user_id)
            self._save()

    def remove_admin(self, user_id: int):
        self._reload()
        if user_id in self._data["admins"]:
            self._data["admins"].remove(user_id)
            self._save()

    def get_admin_command(self):
        self._reload()
        return self._data.get("admin_command", "adminpanel")

    def set_admin_command(self, command: str):
        self._reload()
        self._data["admin_command"] = command
        self._save()

    def get_card_info(self):
        self._reload()
        return self._data.get("card_info", "")

    def set_card_info(self, card_info: str):
        self._reload()
        self._data["card_info"] = card_info
        self._save()

    def get_channel_id(self):
        self._reload()
        env_val = os.environ.get("CHANNEL_ID")
        if env_val:
            return env_val
        if self._use_db_settings():
            val = self._get_db().get_setting("channel_id")
            if val:
                return val
        return self._data.get("channel_id", "")

    def set_channel_id(self, channel_id: str):
        self._reload()
        if self._use_db_settings():
            self._get_db().set_setting("channel_id", channel_id)
        self._data["channel_id"] = channel_id
        self._save()

    def get_gemini_api_keys(self) -> list:
        self._reload()
        env_val = os.environ.get("GEMINI_API_KEYS")
        if env_val:
            return [k.strip() for k in env_val.split(",") if k.strip()]
        if self._use_db_settings():
            raw = self._get_db().get_setting("gemini_api_keys")
            if raw:
                return self._expand_gemini_keys(json.loads(raw))
        keys = self._data.get("gemini_api_keys", [])
        return self._expand_gemini_keys(keys)

    def _normalize_key(self, key: str) -> str:
        return "".join(str(key).split()).strip()

    def _expand_gemini_keys(self, keys) -> list:
        """Kalitlarni tozalash — bo'shliq va vergul bilan ajratish."""
        result = []
        if isinstance(keys, str):
            keys = [keys]
        for item in keys:
            for part in str(item).split(","):
                k = self._normalize_key(part)
                if k and len(k) > 10:
                    result.append(k)
        return list(dict.fromkeys(result))

    def set_gemini_api_keys(self, keys: list):
        self._reload()
        clean = list(dict.fromkeys(
            self._normalize_key(k) for k in keys if k and len(self._normalize_key(k)) > 10
        ))[:50]
        self._data["gemini_api_keys"] = clean
        self._data.pop("groq_api_key", None)
        self._save()
        if self._use_db_settings():
            self._get_db().set_setting("gemini_api_keys", json.dumps(clean, ensure_ascii=False))

    def add_gemini_api_keys(self, new_keys: list) -> int:
        existing = self.get_gemini_api_keys()
        added = 0
        for k in new_keys:
            k = k.strip()
            if k and k not in existing and len(existing) < 50:
                existing.append(k)
                added += 1
        self.set_gemini_api_keys(existing)
        return added

    def clear_gemini_api_keys(self):
        self.set_gemini_api_keys([])

    def get_services(self):
        self._reload()
        if self._use_db_settings():
            raw = self._get_db().get_setting("services")
            if raw:
                services = json.loads(raw)
                return self._normalize_all_services(services)
        services = self._data.get("services", DEFAULT_CONFIG["services"])
        return self._normalize_all_services(services)

    def _normalize_service(self, svc: dict) -> dict:
        """Eski format (bitta narx) → yangi format (plans ro'yxati)."""
        if not svc:
            return {"enabled": True, "title": "", "plans": []}
        if "plans" not in svc:
            svc = dict(svc)
            svc["plans"] = [{
                "id": "1",
                "name": svc.pop("description", "Asosiy"),
                "price": svc.pop("price", 0),
                "enabled": True,
            }]
            svc.pop("price", None)
            svc.pop("description", None)
        if "title" not in svc:
            svc["title"] = ""
        return svc

    def _normalize_all_services(self, services: dict) -> dict:
        return {k: self._normalize_service(v) for k, v in services.items()}

    def _persist_services(self):
        if self._use_db_settings():
            self._get_db().set_setting(
                "services", json.dumps(self._data["services"], ensure_ascii=False)
            )
        self._save()

    def get_service(self, name: str):
        services = self.get_services()
        return services.get(name, {})

    def get_service_plan(self, service_key: str, plan_id: str):
        svc = self.get_service(service_key)
        for plan in svc.get("plans", []):
            if str(plan.get("id")) == str(plan_id):
                return plan
        return None

    def get_active_plans(self, service_key: str):
        svc = self.get_service(service_key)
        if not svc.get("enabled", True):
            return []
        return [p for p in svc.get("plans", []) if p.get("enabled", True)]

    def set_service(self, name: str, data: dict):
        self._reload()
        if "services" not in self._data:
            self._data["services"] = {}
        self._data["services"][name] = self._normalize_service(data)
        self._persist_services()

    def update_service_field(self, name: str, field: str, value):
        self._reload()
        if "services" not in self._data:
            self._data["services"] = {}
        if name not in self._data["services"]:
            self._data["services"][name] = {}
        self._data["services"][name] = self._normalize_service(self._data["services"][name])
        self._data["services"][name][field] = value
        self._persist_services()

    def add_service_plan(self, service_key: str, name: str, price: float):
        self._reload()
        svc = self._normalize_service(self._data.get("services", {}).get(service_key, {}))
        plans = svc.get("plans", [])
        new_id = str(max([int(p["id"]) for p in plans if str(p.get("id", "")).isdigit()] + [0]) + 1)
        plans.append({"id": new_id, "name": name, "price": price, "enabled": True})
        svc["plans"] = plans
        if "services" not in self._data:
            self._data["services"] = {}
        self._data["services"][service_key] = svc
        self._persist_services()
        return new_id

    def update_service_plan(self, service_key: str, plan_id: str, **fields):
        self._reload()
        svc = self._normalize_service(self._data.get("services", {}).get(service_key, {}))
        for plan in svc.get("plans", []):
            if str(plan.get("id")) == str(plan_id):
                plan.update(fields)
                break
        if "services" not in self._data:
            self._data["services"] = {}
        self._data["services"][service_key] = svc
        self._persist_services()

    def remove_service_plan(self, service_key: str, plan_id: str):
        self._reload()
        svc = self._normalize_service(self._data.get("services", {}).get(service_key, {}))
        svc["plans"] = [p for p in svc.get("plans", []) if str(p.get("id")) != str(plan_id)]
        if "services" not in self._data:
            self._data["services"] = {}
        self._data["services"][service_key] = svc
        self._persist_services()
