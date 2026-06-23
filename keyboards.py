from telegram import InlineKeyboardButton, InlineKeyboardMarkup

SERVICE_LABELS = {
    "premium": "⭐ Telegram Premium",
    "stars": "✨ Telegram Stars",
    "steam_topup": "🎮 Steam balans",
}


def main_menu_keyboard(is_admin_user=False, has_contest=False):
    keyboard = [
        [
            InlineKeyboardButton("🔪 Pichoqlar", callback_data="cat_knife"),
            InlineKeyboardButton("🔫 Miltiqlar", callback_data="cat_gun"),
        ],
        [
            InlineKeyboardButton("📦 Keyslar", callback_data="cat_case"),
            InlineKeyboardButton("🎨 Stikerlar", callback_data="cat_sticker"),
        ],
        [
            InlineKeyboardButton("🔑 Breloklar", callback_data="cat_charm"),
        ],
        [
            InlineKeyboardButton("🤖 AI Maslahatchi", callback_data="ai_assistant"),
            InlineKeyboardButton("🛎 Xizmatlar", callback_data="services_menu"),
        ],
        [
            InlineKeyboardButton("✉️ Admin bilan bog'lanish", callback_data="user_contact_admin"),
        ],
    ]
    if has_contest:
        keyboard.insert(-1, [InlineKeyboardButton("🎁 Konkurs", callback_data="user_contest_info")])
    if is_admin_user:
        keyboard.append([InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel")])
    return InlineKeyboardMarkup(keyboard)


def back_button(callback_data):
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data=callback_data)]])


def skin_buttons(skin_id, back_callback):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Sotib olish", callback_data=f"buy|{skin_id}")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data=back_callback)],
    ])


def admin_panel_keyboard(unread_count=0):
    msg_label = f"📩 Foydalanuvchi xabarlari ({unread_count})" if unread_count else "📩 Foydalanuvchi xabarlari"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Statistika", callback_data="admin_stats")],
        [
            InlineKeyboardButton("👥 Obunachilar", callback_data="admin_subscribers"),
            InlineKeyboardButton("🛍 Sotilganlar", callback_data="admin_sold_items"),
        ],
        [InlineKeyboardButton(msg_label, callback_data="admin_user_messages")],
        [InlineKeyboardButton("🎁 Konkurs boshqaruvi", callback_data="admin_contest")],
        [InlineKeyboardButton("🛎 Xizmatlar sozlamalari", callback_data="admin_services")],
        [InlineKeyboardButton("➕ Skin qo'shish", callback_data="admin_add_skin")],
        [InlineKeyboardButton("📋 Skinlar ro'yxati", callback_data="admin_list_skins|0")],
        [InlineKeyboardButton("📦 Buyurtmalar", callback_data="admin_orders|0")],
        [InlineKeyboardButton("👥 Adminlar", callback_data="admin_manage_admins")],
        [InlineKeyboardButton("💳 Karta sozlamalari", callback_data="admin_card_settings")],
        [InlineKeyboardButton("📢 E'lon yuborish", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🔙 Bosh menu", callback_data="back_main")],
    ])


def services_menu_keyboard(services):
    buttons = []
    for key, label in SERVICE_LABELS.items():
        svc = services.get(key, {})
        if svc.get("enabled", True) and svc.get("plans"):
            active = [p for p in svc["plans"] if p.get("enabled", True)]
            if active:
                buttons.append([InlineKeyboardButton(label, callback_data=f"service|{key}")])
    buttons.append([InlineKeyboardButton("🔙 Orqaga", callback_data="back_main")])
    return InlineKeyboardMarkup(buttons)


def service_plans_keyboard(service_key, plans, back_callback="services_menu"):
    buttons = []
    for plan in plans:
        price = plan.get("price", 0)
        price_txt = f"{price:,.0f} so'm" if price else "kelishiladi"
        buttons.append([InlineKeyboardButton(
            f"{plan['name']} — {price_txt}",
            callback_data=f"svcplan|{service_key}|{plan['id']}"
        )])
    buttons.append([InlineKeyboardButton("🔙 Orqaga", callback_data=back_callback)])
    return InlineKeyboardMarkup(buttons)


def admin_service_plans_keyboard(service_key, plans):
    buttons = []
    for plan in plans:
        status = "✅" if plan.get("enabled", True) else "❌"
        price = plan.get("price", 0)
        price_txt = f"{price:,.0f}" if price else "0"
        buttons.append([InlineKeyboardButton(
            f"{status} {plan['name']} — {price_txt} so'm",
            callback_data=f"admin_svcplan|{service_key}|{plan['id']}"
        )])
    buttons.append([InlineKeyboardButton("➕ Yangi variant qo'shish", callback_data=f"admin_svc_addplan|{service_key}")])
    buttons.append([InlineKeyboardButton("🔙 Xizmatlar", callback_data="admin_services")])
    return InlineKeyboardMarkup(buttons)
