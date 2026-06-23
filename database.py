import os
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL", "")
USE_POSTGRES = bool(DATABASE_URL)

SQLITE_PATH = os.path.join(os.path.dirname(__file__), "shop.db")

COLOR_KEYWORDS = {
    "qizil": ["red", "crimson", "ruby", "slaughter", "howl", "fire", "blood", "autotronic"],
    "ko'k": ["blue", "sapphire", "doppler", "case hardened", "cobalt", "ultraviolet"],
    "yashil": ["green", "emerald", "forest", "jungle", "gamma"],
    "sariq": ["yellow", "gold", "amber", "fade", "lore"],
    "oq": ["white", "asiimov", "printstream", "mecha"],
    "qora": ["black", "night", "onyx", "graphite"],
    "pushti": ["pink", "hyper beast", "neo-noir"],
    "binafsha": ["purple", "violet", "ultraviolet", "doppler"],
}


def _pg_connect():
    import pg8000.native
    import urllib.parse
    r = urllib.parse.urlparse(DATABASE_URL)
    return pg8000.native.Connection(
        host=r.hostname,
        port=r.port or 5432,
        database=r.path.lstrip("/"),
        user=r.username,
        password=r.password,
        ssl_context=True,
    )


def _sqlite_connect():
    import sqlite3
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


class Database:
    def __init__(self):
        self._init_db()

    def _init_db(self):
        if USE_POSTGRES:
            conn = _pg_connect()
            conn.run("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.run("""
                CREATE TABLE IF NOT EXISTS skins (
                    id SERIAL PRIMARY KEY,
                    category TEXT NOT NULL,
                    subcategory TEXT,
                    item_name TEXT NOT NULL,
                    name TEXT NOT NULL,
                    photo_id TEXT,
                    price REAL NOT NULL,
                    float_value TEXT,
                    is_stattrak BOOLEAN DEFAULT FALSE,
                    sold BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.run("""
                CREATE TABLE IF NOT EXISTS orders (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    username TEXT,
                    skin_id INTEGER NOT NULL,
                    status TEXT DEFAULT 'pending',
                    payment_screenshot TEXT,
                    steam_link TEXT,
                    trade_confirm_screenshot TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.run("""
                CREATE TABLE IF NOT EXISTS user_messages (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    username TEXT,
                    message_text TEXT NOT NULL,
                    message_type TEXT DEFAULT 'general',
                    is_read BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.run("""
                CREATE TABLE IF NOT EXISTS contests (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    end_at TIMESTAMP NOT NULL,
                    active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.run("""
                CREATE TABLE IF NOT EXISTS contest_entries (
                    id SERIAL PRIMARY KEY,
                    contest_id INTEGER NOT NULL,
                    user_id BIGINT NOT NULL,
                    order_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.run("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
            try:
                conn.run("ALTER TABLE users ADD COLUMN last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            except Exception:
                pass
            conn.close()
        else:
            import sqlite3
            conn = _sqlite_connect()
            c = conn.cursor()
            c.execute("""CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
            c.execute("""CREATE TABLE IF NOT EXISTS skins (
                id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT NOT NULL,
                subcategory TEXT, item_name TEXT NOT NULL, name TEXT NOT NULL,
                photo_id TEXT, price REAL NOT NULL, float_value TEXT,
                is_stattrak BOOLEAN DEFAULT 0, sold BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
            c.execute("""CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
                username TEXT, skin_id INTEGER NOT NULL, status TEXT DEFAULT 'pending',
                payment_screenshot TEXT, steam_link TEXT,
                trade_confirm_screenshot TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
            c.execute("""CREATE TABLE IF NOT EXISTS user_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
                username TEXT, message_text TEXT NOT NULL,
                message_type TEXT DEFAULT 'general', is_read BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
            c.execute("""CREATE TABLE IF NOT EXISTS contests (
                id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
                description TEXT, end_at TIMESTAMP NOT NULL,
                active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
            c.execute("""CREATE TABLE IF NOT EXISTS contest_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT, contest_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL, order_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
            c.execute("""CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY, value TEXT NOT NULL)""")
            try:
                c.execute("ALTER TABLE users ADD COLUMN last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            except sqlite3.OperationalError:
                pass
            conn.commit()
            conn.close()

    # ─── SETTINGS ─────────────────────────────────────────────────────────────

    def get_setting(self, key, default=None):
        if USE_POSTGRES:
            conn = _pg_connect()
            rows = conn.run("SELECT value FROM settings WHERE key=:k", k=key)
            conn.close()
            return rows[0][0] if rows else default
        else:
            conn = _sqlite_connect()
            row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
            conn.close()
            return row['value'] if row else default

    def set_setting(self, key, value):
        if USE_POSTGRES:
            conn = _pg_connect()
            conn.run("""
                INSERT INTO settings (key, value) VALUES (:k, :v)
                ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value
            """, k=key, v=value)
            conn.close()
        else:
            conn = _sqlite_connect()
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (key, str(value))
            )
            conn.commit()
            conn.close()

    # ─── USERS ────────────────────────────────────────────────────────────────

    def save_user(self, user_id, username, first_name):
        if USE_POSTGRES:
            conn = _pg_connect()
            conn.run("""
                INSERT INTO users (user_id, username, first_name, last_active)
                VALUES (:uid, :un, :fn, NOW())
                ON CONFLICT (user_id) DO UPDATE
                SET username=EXCLUDED.username, first_name=EXCLUDED.first_name,
                    last_active=NOW()
            """, uid=user_id, un=username or '', fn=first_name or '')
            conn.close()
        else:
            conn = _sqlite_connect()
            conn.execute(
                "INSERT OR REPLACE INTO users (user_id,username,first_name,last_active) VALUES (?,?,?,CURRENT_TIMESTAMP)",
                (user_id, username or '', first_name or '')
            )
            conn.commit()
            conn.close()

    def touch_user(self, user_id):
        if USE_POSTGRES:
            conn = _pg_connect()
            conn.run("UPDATE users SET last_active=NOW() WHERE user_id=:uid", uid=user_id)
            conn.close()
        else:
            conn = _sqlite_connect()
            conn.execute("UPDATE users SET last_active=CURRENT_TIMESTAMP WHERE user_id=?", (user_id,))
            conn.commit()
            conn.close()

    def get_all_users(self):
        if USE_POSTGRES:
            conn = _pg_connect()
            rows = conn.run("SELECT user_id FROM users")
            conn.close()
            return [r[0] for r in rows]
        else:
            conn = _sqlite_connect()
            rows = conn.execute("SELECT user_id FROM users").fetchall()
            conn.close()
            return [r['user_id'] for r in rows]

    def get_users_count(self):
        if USE_POSTGRES:
            conn = _pg_connect()
            rows = conn.run("SELECT COUNT(*) FROM users")
            conn.close()
            return rows[0][0] if rows else 0
        else:
            conn = _sqlite_connect()
            row = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()
            conn.close()
            return row['c'] if row else 0

    def get_users_stats(self):
        if USE_POSTGRES:
            conn = _pg_connect()
            total = conn.run("SELECT COUNT(*) FROM users")[0][0]
            today = conn.run(
                "SELECT COUNT(*) FROM users WHERE registered_at::date = CURRENT_DATE"
            )[0][0]
            active = conn.run(
                "SELECT COUNT(*) FROM users WHERE last_active >= NOW() - INTERVAL '7 days'"
            )[0][0]
            conn.close()
        else:
            conn = _sqlite_connect()
            total = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()['c']
            today = conn.execute(
                "SELECT COUNT(*) as c FROM users WHERE date(registered_at)=date('now')"
            ).fetchone()['c']
            active = conn.execute(
                "SELECT COUNT(*) as c FROM users WHERE last_active >= datetime('now','-7 days')"
            ).fetchone()['c']
            conn.close()
        return {"total": total, "today": today, "active": active}

    # ─── USER MESSAGES ────────────────────────────────────────────────────────

    def add_user_message(self, user_id, username, message_text, message_type="general"):
        if USE_POSTGRES:
            conn = _pg_connect()
            rows = conn.run("""
                INSERT INTO user_messages (user_id, username, message_text, message_type)
                VALUES (:uid, :un, :msg, :mt) RETURNING id
            """, uid=user_id, un=username or '', msg=message_text, mt=message_type)
            conn.close()
            return rows[0][0]
        else:
            conn = _sqlite_connect()
            c = conn.execute(
                "INSERT INTO user_messages (user_id,username,message_text,message_type) VALUES (?,?,?,?)",
                (user_id, username or '', message_text, message_type)
            )
            mid = c.lastrowid
            conn.commit()
            conn.close()
            return mid

    def get_unread_messages_count(self):
        if USE_POSTGRES:
            conn = _pg_connect()
            rows = conn.run("SELECT COUNT(*) FROM user_messages WHERE is_read=FALSE")
            conn.close()
            return rows[0][0] if rows else 0
        else:
            conn = _sqlite_connect()
            row = conn.execute("SELECT COUNT(*) as c FROM user_messages WHERE is_read=0").fetchone()
            conn.close()
            return row['c'] if row else 0

    def get_user_messages(self, limit=30, unread_only=False):
        cols = ['id', 'user_id', 'username', 'message_text', 'message_type', 'is_read', 'created_at']
        where = "WHERE is_read=FALSE" if unread_only else ""
        if USE_POSTGRES:
            conn = _pg_connect()
            rows = conn.run(
                f"SELECT * FROM user_messages {where} ORDER BY created_at DESC LIMIT :lim",
                lim=limit
            )
            conn.close()
            return [dict(zip(cols, r)) for r in rows]
        else:
            conn = _sqlite_connect()
            q = f"SELECT * FROM user_messages {'WHERE is_read=0' if unread_only else ''} ORDER BY created_at DESC LIMIT ?"
            rows = conn.execute(q, (limit,)).fetchall()
            conn.close()
            return [dict(r) for r in rows]

    def mark_message_read(self, message_id):
        if USE_POSTGRES:
            conn = _pg_connect()
            conn.run("UPDATE user_messages SET is_read=TRUE WHERE id=:id", id=message_id)
            conn.close()
        else:
            conn = _sqlite_connect()
            conn.execute("UPDATE user_messages SET is_read=1 WHERE id=?", (message_id,))
            conn.commit()
            conn.close()

    def mark_all_messages_read(self):
        if USE_POSTGRES:
            conn = _pg_connect()
            conn.run("UPDATE user_messages SET is_read=TRUE WHERE is_read=FALSE")
            conn.close()
        else:
            conn = _sqlite_connect()
            conn.execute("UPDATE user_messages SET is_read=1 WHERE is_read=0")
            conn.commit()
            conn.close()

    # ─── CONTESTS ─────────────────────────────────────────────────────────────

    def create_contest(self, title, description, end_at):
        if USE_POSTGRES:
            conn = _pg_connect()
            conn.run("UPDATE contests SET active=FALSE WHERE active=TRUE")
            rows = conn.run("""
                INSERT INTO contests (title, description, end_at, active)
                VALUES (:t, :d, :e, TRUE) RETURNING id
            """, t=title, d=description, e=end_at)
            conn.close()
            return rows[0][0]
        else:
            conn = _sqlite_connect()
            conn.execute("UPDATE contests SET active=0 WHERE active=1")
            c = conn.execute(
                "INSERT INTO contests (title,description,end_at,active) VALUES (?,?,?,1)",
                (title, description, end_at)
            )
            cid = c.lastrowid
            conn.commit()
            conn.close()
            return cid

    def get_active_contest(self):
        cols = ['id', 'title', 'description', 'end_at', 'active', 'created_at']
        if USE_POSTGRES:
            conn = _pg_connect()
            rows = conn.run(
                "SELECT * FROM contests WHERE active=TRUE AND end_at > NOW() ORDER BY created_at DESC LIMIT 1"
            )
            conn.close()
            return dict(zip(cols, rows[0])) if rows else None
        else:
            conn = _sqlite_connect()
            row = conn.execute(
                "SELECT * FROM contests WHERE active=1 AND end_at > datetime('now') ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            conn.close()
            return dict(row) if row else None

    def stop_contest(self, contest_id):
        if USE_POSTGRES:
            conn = _pg_connect()
            conn.run("UPDATE contests SET active=FALSE WHERE id=:id", id=contest_id)
            conn.close()
        else:
            conn = _sqlite_connect()
            conn.execute("UPDATE contests SET active=0 WHERE id=?", (contest_id,))
            conn.commit()
            conn.close()

    def add_contest_entry(self, contest_id, user_id, order_id):
        if USE_POSTGRES:
            conn = _pg_connect()
            conn.run("""
                INSERT INTO contest_entries (contest_id, user_id, order_id)
                VALUES (:cid, :uid, :oid)
            """, cid=contest_id, uid=user_id, oid=order_id)
            conn.close()
        else:
            conn = _sqlite_connect()
            conn.execute(
                "INSERT INTO contest_entries (contest_id,user_id,order_id) VALUES (?,?,?)",
                (contest_id, user_id, order_id)
            )
            conn.commit()
            conn.close()

    def get_contest_leaderboard(self, contest_id, limit=20):
        if USE_POSTGRES:
            conn = _pg_connect()
            rows = conn.run("""
                SELECT u.username, u.first_name, ce.user_id, COUNT(*) as tickets
                FROM contest_entries ce
                JOIN users u ON u.user_id = ce.user_id
                WHERE ce.contest_id = :cid
                GROUP BY ce.user_id, u.username, u.first_name
                ORDER BY tickets DESC
                LIMIT :lim
            """, cid=contest_id, lim=limit)
            conn.close()
            return [{"username": r[0], "first_name": r[1], "user_id": r[2], "tickets": r[3]} for r in rows]
        else:
            conn = _sqlite_connect()
            rows = conn.execute("""
                SELECT u.username, u.first_name, ce.user_id, COUNT(*) as tickets
                FROM contest_entries ce
                JOIN users u ON u.user_id = ce.user_id
                WHERE ce.contest_id = ?
                GROUP BY ce.user_id
                ORDER BY tickets DESC
                LIMIT ?
            """, (contest_id, limit)).fetchall()
            conn.close()
            return [dict(r) for r in rows]

    def get_user_contest_tickets(self, contest_id, user_id):
        if USE_POSTGRES:
            conn = _pg_connect()
            rows = conn.run(
                "SELECT COUNT(*) FROM contest_entries WHERE contest_id=:cid AND user_id=:uid",
                cid=contest_id, uid=user_id
            )
            conn.close()
            return rows[0][0] if rows else 0
        else:
            conn = _sqlite_connect()
            row = conn.execute(
                "SELECT COUNT(*) as c FROM contest_entries WHERE contest_id=? AND user_id=?",
                (contest_id, user_id)
            ).fetchone()
            conn.close()
            return row['c'] if row else 0

    # ─── SKINS ────────────────────────────────────────────────────────────────

    def add_skin(self, category, item_name, name, photo_id, price,
                 float_value=None, is_stattrak=False, subcategory=None):
        if USE_POSTGRES:
            conn = _pg_connect()
            rows = conn.run("""
                INSERT INTO skins (category,subcategory,item_name,name,photo_id,price,float_value,is_stattrak)
                VALUES (:cat,:sub,:item,:name,:photo,:price,:flt,:st) RETURNING id
            """, cat=category, sub=subcategory, item=item_name, name=name,
                photo=photo_id, price=price, flt=float_value, st=is_stattrak)
            conn.close()
            return rows[0][0]
        else:
            conn = _sqlite_connect()
            c = conn.execute("""INSERT INTO skins
                (category,subcategory,item_name,name,photo_id,price,float_value,is_stattrak)
                VALUES (?,?,?,?,?,?,?,?)""",
                (category, subcategory, item_name, name, photo_id, price, float_value, int(is_stattrak)))
            skin_id = c.lastrowid
            conn.commit()
            conn.close()
            return skin_id

    def _pg_row_to_dict(self, row, columns):
        return dict(zip(columns, row)) if row else None

    def _skin_cols(self):
        return ['id', 'category', 'subcategory', 'item_name', 'name', 'photo_id',
                'price', 'float_value', 'is_stattrak', 'sold', 'created_at']

    def get_skin(self, skin_id):
        cols = self._skin_cols()
        if USE_POSTGRES:
            conn = _pg_connect()
            rows = conn.run("SELECT * FROM skins WHERE id=:id", id=skin_id)
            conn.close()
            return self._pg_row_to_dict(rows[0] if rows else None, cols)
        else:
            conn = _sqlite_connect()
            row = conn.execute("SELECT * FROM skins WHERE id=?", (skin_id,)).fetchone()
            conn.close()
            return dict(row) if row else None

    def get_skins_by_category(self, category):
        cols = self._skin_cols()
        if USE_POSTGRES:
            conn = _pg_connect()
            rows = conn.run("SELECT * FROM skins WHERE category=:cat ORDER BY item_name", cat=category)
            conn.close()
            return [dict(zip(cols, r)) for r in rows]
        else:
            conn = _sqlite_connect()
            rows = conn.execute("SELECT * FROM skins WHERE category=? ORDER BY item_name", (category,)).fetchall()
            conn.close()
            return [dict(r) for r in rows]

    def get_skins_by_item(self, category, item_name):
        cols = self._skin_cols()
        if USE_POSTGRES:
            conn = _pg_connect()
            rows = conn.run(
                "SELECT * FROM skins WHERE category=:cat AND item_name=:item AND sold=FALSE ORDER BY price",
                cat=category, item=item_name
            )
            conn.close()
            return [dict(zip(cols, r)) for r in rows]
        else:
            conn = _sqlite_connect()
            rows = conn.execute(
                "SELECT * FROM skins WHERE category=? AND item_name=? AND sold=0 ORDER BY price",
                (category, item_name)
            ).fetchall()
            conn.close()
            return [dict(r) for r in rows]

    def get_all_skins(self, limit=50, offset=0, available_only=False):
        cols = self._skin_cols()
        sold_filter = "WHERE sold=FALSE" if available_only else ""
        sold_filter_sqlite = "WHERE sold=0" if available_only else ""
        if USE_POSTGRES:
            conn = _pg_connect()
            rows = conn.run(
                f"SELECT * FROM skins {sold_filter} ORDER BY created_at DESC LIMIT :lim OFFSET :off",
                lim=limit, off=offset
            )
            conn.close()
            return [dict(zip(cols, r)) for r in rows]
        else:
            conn = _sqlite_connect()
            rows = conn.execute(
                f"SELECT * FROM skins {sold_filter_sqlite} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset)
            ).fetchall()
            conn.close()
            return [dict(r) for r in rows]

    def count_skins(self, available_only=False):
        if USE_POSTGRES:
            conn = _pg_connect()
            if available_only:
                rows = conn.run("SELECT COUNT(*) FROM skins WHERE sold=FALSE")
            else:
                rows = conn.run("SELECT COUNT(*) FROM skins")
            conn.close()
            return rows[0][0] if rows else 0
        else:
            conn = _sqlite_connect()
            if available_only:
                row = conn.execute("SELECT COUNT(*) as c FROM skins WHERE sold=0").fetchone()
            else:
                row = conn.execute("SELECT COUNT(*) as c FROM skins").fetchone()
            conn.close()
            return row['c'] if row else 0

    def get_sold_skins(self, limit=30, offset=0):
        cols = self._skin_cols()
        if USE_POSTGRES:
            conn = _pg_connect()
            rows = conn.run(
                "SELECT * FROM skins WHERE sold=TRUE ORDER BY created_at DESC LIMIT :lim OFFSET :off",
                lim=limit, off=offset
            )
            conn.close()
            return [dict(zip(cols, r)) for r in rows]
        else:
            conn = _sqlite_connect()
            rows = conn.execute(
                "SELECT * FROM skins WHERE sold=1 ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset)
            ).fetchall()
            conn.close()
            return [dict(r) for r in rows]

    def search_skins(self, query, weapon=None, limit=15):
        """Rang yoki nom bo'yicha skin qidirish (AI uchun)."""
        query_lower = query.lower()
        keywords = [query_lower]
        for uz, en_list in COLOR_KEYWORDS.items():
            if uz in query_lower:
                keywords.extend(en_list)
        for en in query_lower.split():
            keywords.append(en)

        cols = self._skin_cols()
        results = []
        if USE_POSTGRES:
            conn = _pg_connect()
            rows = conn.run("SELECT * FROM skins WHERE sold=FALSE ORDER BY price")
            conn.close()
            all_skins = [dict(zip(cols, r)) for r in rows]
        else:
            conn = _sqlite_connect()
            rows = conn.execute("SELECT * FROM skins WHERE sold=0 ORDER BY price").fetchall()
            conn.close()
            all_skins = [dict(r) for r in rows]

        for skin in all_skins:
            if weapon and weapon.lower() not in skin['item_name'].lower():
                continue
            haystack = f"{skin['name']} {skin['item_name']}".lower()
            if any(kw in haystack for kw in keywords if len(kw) > 2):
                results.append(skin)
            if len(results) >= limit:
                break
        return results

    def delete_skin(self, skin_id):
        if USE_POSTGRES:
            conn = _pg_connect()
            conn.run("DELETE FROM skins WHERE id=:id", id=skin_id)
            conn.close()
        else:
            conn = _sqlite_connect()
            conn.execute("DELETE FROM skins WHERE id=?", (skin_id,))
            conn.commit()
            conn.close()

    def mark_skin_sold(self, skin_id):
        if USE_POSTGRES:
            conn = _pg_connect()
            conn.run("UPDATE skins SET sold=TRUE WHERE id=:id", id=skin_id)
            conn.close()
        else:
            conn = _sqlite_connect()
            conn.execute("UPDATE skins SET sold=1 WHERE id=?", (skin_id,))
            conn.commit()
            conn.close()

    # ─── ORDERS ───────────────────────────────────────────────────────────────

    def create_order(self, user_id, username, skin_id, payment_screenshot):
        if USE_POSTGRES:
            conn = _pg_connect()
            rows = conn.run("""
                INSERT INTO orders (user_id,username,skin_id,payment_screenshot)
                VALUES (:uid,:un,:sid,:ps) RETURNING id
            """, uid=user_id, un=username, sid=skin_id, ps=payment_screenshot)
            conn.close()
            return rows[0][0]
        else:
            conn = _sqlite_connect()
            c = conn.execute(
                "INSERT INTO orders (user_id,username,skin_id,payment_screenshot) VALUES (?,?,?,?)",
                (user_id, username, skin_id, payment_screenshot)
            )
            oid = c.lastrowid
            conn.commit()
            conn.close()
            return oid

    def _order_cols(self):
        return ['id', 'user_id', 'username', 'skin_id', 'status', 'payment_screenshot',
                'steam_link', 'trade_confirm_screenshot', 'created_at', 'updated_at']

    def get_order(self, order_id):
        if USE_POSTGRES:
            conn = _pg_connect()
            rows = conn.run("SELECT * FROM orders WHERE id=:id", id=order_id)
            conn.close()
            return self._pg_row_to_dict(rows[0] if rows else None, self._order_cols())
        else:
            conn = _sqlite_connect()
            row = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
            conn.close()
            return dict(row) if row else None

    def get_all_orders(self, limit=20, offset=0):
        if USE_POSTGRES:
            conn = _pg_connect()
            rows = conn.run(
                "SELECT * FROM orders ORDER BY created_at DESC LIMIT :lim OFFSET :off",
                lim=limit, off=offset
            )
            conn.close()
            return [dict(zip(self._order_cols(), r)) for r in rows]
        else:
            conn = _sqlite_connect()
            rows = conn.execute(
                "SELECT * FROM orders ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset)
            ).fetchall()
            conn.close()
            return [dict(r) for r in rows]

    def count_orders(self):
        if USE_POSTGRES:
            conn = _pg_connect()
            rows = conn.run("SELECT COUNT(*) FROM orders")
            conn.close()
            return rows[0][0] if rows else 0
        else:
            conn = _sqlite_connect()
            row = conn.execute("SELECT COUNT(*) as c FROM orders").fetchone()
            conn.close()
            return row['c'] if row else 0

    def get_completed_sales(self, limit=30, offset=0):
        """Kim nima sotib olgan — batafsil ro'yxat."""
        if USE_POSTGRES:
            conn = _pg_connect()
            rows = conn.run("""
                SELECT o.id, o.user_id, o.username, o.updated_at,
                       s.name, s.item_name, s.price
                FROM orders o
                JOIN skins s ON s.id = o.skin_id
                WHERE o.status = 'completed'
                ORDER BY o.updated_at DESC
                LIMIT :lim OFFSET :off
            """, lim=limit, off=offset)
            conn.close()
            return [{
                "order_id": r[0], "user_id": r[1], "username": r[2],
                "date": r[3], "skin_name": r[4], "item_name": r[5], "price": r[6]
            } for r in rows]
        else:
            conn = _sqlite_connect()
            rows = conn.execute("""
                SELECT o.id, o.user_id, o.username, o.updated_at,
                       s.name, s.item_name, s.price
                FROM orders o
                JOIN skins s ON s.id = o.skin_id
                WHERE o.status = 'completed'
                ORDER BY o.updated_at DESC
                LIMIT ? OFFSET ?
            """, (limit, offset)).fetchall()
            conn.close()
            return [dict(r) for r in rows]

    def count_completed_sales(self):
        if USE_POSTGRES:
            conn = _pg_connect()
            rows = conn.run("SELECT COUNT(*) FROM orders WHERE status='completed'")
            conn.close()
            return rows[0][0] if rows else 0
        else:
            conn = _sqlite_connect()
            row = conn.execute("SELECT COUNT(*) as c FROM orders WHERE status='completed'").fetchone()
            conn.close()
            return row['c'] if row else 0

    def get_revenue_stats(self):
        """Bugun, hafta, oy bo'yicha daromad (so'm)."""
        periods = {}
        if USE_POSTGRES:
            conn = _pg_connect()
            for key, sql in [
                ("today", "o.updated_at::date = CURRENT_DATE"),
                ("week", "o.updated_at >= NOW() - INTERVAL '7 days'"),
                ("month", "o.updated_at >= NOW() - INTERVAL '30 days'"),
            ]:
                rows = conn.run(f"""
                    SELECT COALESCE(SUM(s.price), 0)
                    FROM orders o JOIN skins s ON s.id = o.skin_id
                    WHERE o.status='completed' AND {sql}
                """)
                periods[key] = float(rows[0][0]) if rows else 0.0
            conn.close()
        else:
            conn = _sqlite_connect()
            for key, sql in [
                ("today", "date(o.updated_at)=date('now')"),
                ("week", "o.updated_at >= datetime('now','-7 days')"),
                ("month", "o.updated_at >= datetime('now','-30 days')"),
            ]:
                row = conn.execute(f"""
                    SELECT COALESCE(SUM(s.price), 0) as total
                    FROM orders o JOIN skins s ON s.id = o.skin_id
                    WHERE o.status='completed' AND {sql}
                """).fetchone()
                periods[key] = float(row['total']) if row else 0.0
            conn.close()
        return periods

    def get_active_order_for_user(self, user_id):
        if USE_POSTGRES:
            conn = _pg_connect()
            rows = conn.run(
                "SELECT * FROM orders WHERE user_id=:uid AND status='payment_confirmed' ORDER BY created_at DESC LIMIT 1",
                uid=user_id
            )
            conn.close()
            return self._pg_row_to_dict(rows[0] if rows else None, self._order_cols())
        else:
            conn = _sqlite_connect()
            row = conn.execute(
                "SELECT * FROM orders WHERE user_id=? AND status='payment_confirmed' ORDER BY created_at DESC LIMIT 1",
                (user_id,)
            ).fetchone()
            conn.close()
            return dict(row) if row else None

    def update_order_status(self, order_id, status):
        if USE_POSTGRES:
            conn = _pg_connect()
            conn.run("UPDATE orders SET status=:st, updated_at=NOW() WHERE id=:id", st=status, id=order_id)
            conn.close()
        else:
            conn = _sqlite_connect()
            conn.execute("UPDATE orders SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (status, order_id))
            conn.commit()
            conn.close()

    def update_order_steam_link(self, order_id, steam_link):
        if USE_POSTGRES:
            conn = _pg_connect()
            conn.run("UPDATE orders SET steam_link=:sl, updated_at=NOW() WHERE id=:id", sl=steam_link, id=order_id)
            conn.close()
        else:
            conn = _sqlite_connect()
            conn.execute("UPDATE orders SET steam_link=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (steam_link, order_id))
            conn.commit()
            conn.close()
