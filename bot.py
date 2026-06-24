import os
import asyncio
import logging
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

from database import Database
from config import Config
from keyboards import (
    main_menu_keyboard, back_button, skin_buttons,
    admin_panel_keyboard, services_menu_keyboard,
    service_plans_keyboard, admin_service_plans_keyboard, SERVICE_LABELS
)
import ai_service

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

db = Database()
config = Config()

# States
(
    ADMIN_WAITING_SKIN_CATEGORY, ADMIN_WAITING_SKIN_SUBCATEGORY,
    ADMIN_WAITING_SKIN_NAME, ADMIN_WAITING_SKIN_PHOTO,
    ADMIN_WAITING_SKIN_PRICE, ADMIN_WAITING_SKIN_FLOAT,
    ADMIN_WAITING_SKIN_STATTRAK,
    USER_WAITING_PAYMENT_SCREENSHOT,
    ADMIN_WAITING_TRADE_CONFIRM,
    ADMIN_WAITING_NEW_ADMIN_ID, ADMIN_WAITING_NEW_BOT_TOKEN,
    ADMIN_WAITING_BROADCAST,
    USER_WAITING_AI_QUESTION, USER_WAITING_MESSAGE_TO_ADMIN,
    USER_WAITING_SERVICE_PAYMENT,
    ADMIN_WAITING_CONTEST_TITLE, ADMIN_WAITING_CONTEST_DESC,
    ADMIN_WAITING_CONTEST_END,
    ADMIN_WAITING_GEMINI_KEYS, ADMIN_WAITING_CHANNEL_ID,
    ADMIN_ADD_PLAN_NAME, ADMIN_ADD_PLAN_PRICE,
    ADMIN_EDIT_PLAN_NAME, ADMIN_EDIT_PLAN_PRICE,
) = range(24)

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def is_admin(user_id: int) -> bool:
    return user_id in config.get_admins()


async def track_user(update: Update):
    user = update.effective_user
    if user:
        db.save_user(user.id, user.username, user.first_name)
        db.touch_user(user.id)


def knife_types():
    return [
        "Bayonet", "M9 Bayonet", "Karambit", "Flip Knife", "Gut Knife",
        "Huntsman Knife", "Butterfly Knife", "Falchion Knife", "Bowie Knife",
        "Shadow Daggers", "Navaja Knife", "Stiletto Knife", "Talon Knife",
        "Ursus Knife", "Paracord Knife", "Survival Knife", "Nomad Knife",
        "Skeleton Knife"
    ]


def gun_subcategories():
    return {
        "pistolet": ("🔫 Pistoletlar (Pistols)", [
            "Glock-18", "USP-S", "P2000", "Dual Berettas", "P250",
            "Five-SeveN", "Tec-9", "CZ75-Auto", "Desert Eagle", "R8 Revolver"
        ]),
        "smg": ("🔫 SMG (Submachine Guns)", [
            "MAC-10", "MP9", "MP7", "MP5-SD", "UMP-45", "P90", "PP-Bizon"
        ]),
        "shotgun": ("🔫 Shotgunlar", ["Nova", "XM1014", "MAG-7", "Sawed-Off"]),
        "rifle": ("🔫 Rifles (Avtomatlar)", [
            "AK-47", "M4A4", "M4A1-S", "FAMAS", "Galil AR", "SG 553", "AUG"
        ]),
        "sniper": ("🎯 Sniperlar", ["AWP", "SSG 08 (Scout)", "G3SG1", "SCAR-20"]),
        "heavy": ("💣 Og'ir qurollar (Heavy / Machine Guns)", ["M249", "Negev"]),
    }


def has_active_contest():
    return db.get_active_contest() is not None


# ─────────────────────────────────────────────────────────────────────────────
# START
# ─────────────────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await track_user(update)
    user = update.effective_user
    admin = is_admin(user.id)
    text = (
        f"👋 Xush kelibsiz, <b>{user.first_name}</b>!\n\n"
        "🎮 <b>CS2 Skin Do'koni</b>ga xush kelibsiz.\n"
        "Quyidagi bo'limlardan birini tanlang:"
    )
    await update.message.reply_text(
        text, parse_mode="HTML",
        reply_markup=main_menu_keyboard(admin, has_active_contest())
    )


# ─────────────────────────────────────────────────────────────────────────────
# CATEGORY BROWSING
# ─────────────────────────────────────────────────────────────────────────────

async def category_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await track_user(update)
    data = query.data

    if data == "cat_knife":
        buttons, row = [], []
        for knife in knife_types():
            row.append(InlineKeyboardButton(knife, callback_data=f"sub_knife|{knife}"))
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        buttons.append([InlineKeyboardButton("🔙 Orqaga", callback_data="back_main")])
        await query.edit_message_text(
            "🔪 <b>Pichoq turini tanlang:</b>", parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif data == "cat_gun":
        buttons = [[InlineKeyboardButton(label, callback_data=f"gun_subcat|{key}")]
                   for key, (label, _) in gun_subcategories().items()]
        buttons.append([InlineKeyboardButton("🔙 Orqaga", callback_data="back_main")])
        await query.edit_message_text(
            "🔫 <b>Miltiq turini tanlang:</b>", parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif data in ("cat_case", "cat_sticker", "cat_charm"):
        cat_map = {
            "cat_case": ("📦", "Keyslar"), "cat_sticker": ("🎨", "Stikerlar"),
            "cat_charm": ("🔑", "Breloklar"),
        }
        cat_key = {"cat_case": "case", "cat_sticker": "sticker", "cat_charm": "charm"}[data]
        icon, label = cat_map[data]
        all_skins = db.get_skins_by_category(cat_key)
        item_names = list(dict.fromkeys(s['item_name'] for s in all_skins if not s.get('sold')))
        if not item_names:
            await query.edit_message_text(
                f"{icon} <b>{label}</b>\n\nHozircha mahsulot yo'q.", parse_mode="HTML",
                reply_markup=back_button("back_main")
            )
            return
        buttons = [[InlineKeyboardButton(n, callback_data=f"sub_{cat_key}|{n}")] for n in item_names]
        buttons.append([InlineKeyboardButton("🔙 Orqaga", callback_data="back_main")])
        await query.edit_message_text(
            f"{icon} <b>{label}</b>\nTanlang:", parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif data == "back_main":
        user = query.from_user
        await query.edit_message_text(
            "🎮 <b>CS2 Skin Do'koni</b>\nBo'limni tanlang:", parse_mode="HTML",
            reply_markup=main_menu_keyboard(is_admin(user.id), has_active_contest())
        )


async def subcat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await track_user(update)
    data = query.data

    if data.startswith("gun_subcat|"):
        key = data.split("|", 1)[1]
        subcat = gun_subcategories()
        if key in subcat:
            label, guns = subcat[key]
            buttons, row = [], []
            for gun in guns:
                row.append(InlineKeyboardButton(gun, callback_data=f"sub_gun|{gun}"))
                if len(row) == 2:
                    buttons.append(row)
                    row = []
            if row:
                buttons.append(row)
            buttons.append([InlineKeyboardButton("🔙 Orqaga", callback_data="cat_gun")])
            await query.edit_message_text(
                f"<b>{label}</b>\nQurol turini tanlang:", parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(buttons)
            )


async def show_skins_for_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await track_user(update)
    data = query.data

    prefix_map = {
        "sub_knife": ("knife", "cat_knife"), "sub_gun": ("gun", "cat_gun"),
        "sub_case": ("case", "cat_case"), "sub_sticker": ("sticker", "cat_sticker"),
        "sub_charm": ("charm", "cat_charm"),
    }

    for prefix, (cat, back) in prefix_map.items():
        if data.startswith(prefix + "|"):
            item_name = data.split("|", 1)[1]
            skins = db.get_skins_by_item(cat, item_name)
            if not skins:
                await query.edit_message_text(
                    f"❌ <b>{item_name}</b> uchun hozircha skinlar yo'q.", parse_mode="HTML",
                    reply_markup=back_button(back)
                )
                return

            for skin in skins:
                caption = (
                    f"🎨 <b>{skin['name']}</b>\n"
                    f"🔫 Qurol: {skin['item_name']}\n"
                    f"💵 Narx: <b>{skin['price']:,.0f} so'm</b>\n"
                )
                if skin.get('float_value'):
                    caption += f"📊 Float: <code>{skin['float_value']}</code>\n"
                if skin.get('is_stattrak'):
                    caption += "⚡ StatTrak™: Ha\n"
                caption += f"\n🆔 ID: <code>{skin['id']}</code>"
                btns = skin_buttons(skin['id'], back)
                if skin.get('photo_id'):
                    await query.message.reply_photo(
                        photo=skin['photo_id'], caption=caption,
                        parse_mode="HTML", reply_markup=btns
                    )
                else:
                    await query.message.reply_text(
                        caption, parse_mode="HTML", reply_markup=btns
                    )

            await query.edit_message_text(
                f"📋 <b>{item_name}</b> — {len(skins)} ta skin.\n"
                "Har bir skin ostida 🔙 Orqaga tugmasi bor.",
                parse_mode="HTML", reply_markup=back_button(back)
            )
            return



    return USER_WAITING_AI_QUESTION


async def ai_receive_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await track_user(update)
    if update.message.text == "/cancel":
        await update.message.reply_text("Bekor qilindi.", reply_markup=main_menu_keyboard(
            is_admin(update.effective_user.id), has_active_contest()
        ))
        return ConversationHandler.END

    question = update.message.text.strip()
    wait_msg = await update.message.reply_text("🤖 AI o'ylayapti...")

    api_keys = config.get_gemini_api_keys()
    weapon = None
    for w in ["desert eagle", "ak-47", "awp", "m4a4", "karambit", "bayonet"]:
        if w in question.lower():
            weapon = w.title()
            break

    found_skins = db.search_skins(question, weapon=weapon)
    if found_skins and any(k in question.lower() for k in ["top", "ber", "qidir", "kerak", "red", "qizil"]):
        answer = ai_service.find_skins_for_request(api_keys, question, found_skins)
        if found_skins and not answer.startswith("❌"):
            skin_lines = "\n".join(
                f"• {s['item_name']} | {s['name']} — {s['price']:,.0f} so'm (ID: {s['id']})"
                for s in found_skins[:8]
            )
            answer += f"\n\n🛒 <b>Do'kondan topilganlar:</b>\n{skin_lines}"
    else:
        answer = ai_service.get_skin_advice(api_keys, question, found_skins)

    await wait_msg.edit_text(answer, parse_mode="HTML")
    await update.message.reply_text(
        "Yana savol bering yoki menyuga qayting:",
        reply_markup=InlineKeyboardMarkup([
           
            [InlineKeyboardButton("🔙 Bosh menu", callback_data="back_main")],
        ])
    )
    return USER_WAITING_AI_QUESTION


# ─────────────────────────────────────────────────────────────────────────────
# SERVICES
# ─────────────────────────────────────────────────────────────────────────────

async def services_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await track_user(update)
    services = config.get_services()
    text = "🛎 <b>Qo'shimcha xizmatlar</b>\n\nKerakli xizmatni tanlang:"
    await query.edit_message_text(
        text, parse_mode="HTML",
        reply_markup=services_menu_keyboard(services)
    )


async def service_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xizmat tanlandi — variantlar ro'yxatini ko'rsatish."""
    query = update.callback_query
    await query.answer()
    await track_user(update)
    service_key = query.data.split("|")[1]
    svc = config.get_service(service_key)
    label = SERVICE_LABELS.get(service_key, svc.get("title", service_key))
    plans = config.get_active_plans(service_key)

    if not plans:
        await query.edit_message_text(
            f"😔 <b>{label}</b> uchun hozircha variant yo'q.",
            parse_mode="HTML", reply_markup=back_button("services_menu")
        )
        return

    await query.edit_message_text(
        f"🛎 <b>{label}</b>\n\nKerakli variantni tanlang:",
        parse_mode="HTML",
        reply_markup=service_plans_keyboard(service_key, plans)
    )


async def service_plan_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Variant tanlandi — to'lov."""
    query = update.callback_query
    await query.answer()
    await track_user(update)
    parts = query.data.split("|")
    service_key, plan_id = parts[1], parts[2]
    plan = config.get_service_plan(service_key, plan_id)
    if not plan:
        await query.answer("Variant topilmadi!", show_alert=True)
        return

    label = SERVICE_LABELS.get(service_key, service_key)
    price = plan.get("price", 0)
    price_text = f"{price:,.0f} so'm" if price else "Summani admin bilan kelishing"

    context.user_data['service_type'] = service_key
    context.user_data['service_plan_id'] = plan_id
    context.user_data['service_plan_name'] = plan.get("name", "")

    await query.edit_message_text(
        f"🛎 <b>{label}</b>\n"
        f"📦 Variant: <b>{plan.get('name', '')}</b>\n"
        f"💵 Narx: <b>{price_text}</b>\n\n"
        f"💳 <b>To'lov:</b>\n<code>{config.get_card_info()}</code>\n\n"
        "📸 To'lov chekini (screenshot) yuboring:",
        parse_mode="HTML",
        reply_markup=back_button(f"service|{service_key}")
    )
    return USER_WAITING_SERVICE_PAYMENT


async def receive_service_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await track_user(update)
    if not update.message.photo:
        await update.message.reply_text("❌ Chekni rasm ko'rinishida yuboring.")
        return USER_WAITING_SERVICE_PAYMENT

    service_key = context.user_data.get('service_type', 'unknown')
    plan_name = context.user_data.get('service_plan_name', '')
    label = SERVICE_LABELS.get(service_key, service_key)
    user = update.effective_user
    photo_id = update.message.photo[-1].file_id
    username_display = f"@{user.username}" if user.username else user.first_name
    plan_line = f" — {plan_name}" if plan_name else ""

    for admin_id in config.get_admins():
        try:
            await context.bot.send_photo(
                chat_id=admin_id, photo=photo_id,
                caption=(
                    f"🛎 YANGI XIZMAT BUYURTMASI\n\n"
                    f"📌 Xizmat: {label}{plan_line}\n"
                    f"👤 Mijoz: {username_display} ({user.id})"
                )
            )
        except Exception as e:
            logger.error(f"Service notify error: {e}")

    await update.message.reply_text(
        "✅ Buyurtmangiz qabul qilindi! Admin tez orada bog'lanadi.",
        reply_markup=main_menu_keyboard(is_admin(user.id), has_active_contest())
    )
    context.user_data.pop('service_type', None)
    context.user_data.pop('service_plan_id', None)
    context.user_data.pop('service_plan_name', None)
    return ConversationHandler.END


# ─────────────────────────────────────────────────────────────────────────────
# USER CONTACT ADMIN
# ─────────────────────────────────────────────────────────────────────────────

async def user_contact_admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await track_user(update)
    await query.edit_message_text(
        "✉️ <b>Admin bilan bog'lanish</b>\n\n"
        "Taklif, shikoyat yoki qaysi skin kerakligini yozing.\n"
        "Xabaringiz admin panelga yetkaziladi.\n\n"
        "<i>Bekor qilish: /cancel</i>",
        parse_mode="HTML", reply_markup=back_button("back_main")
    )
    return USER_WAITING_MESSAGE_TO_ADMIN


async def receive_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await track_user(update)
    if update.message.text == "/cancel":
        await update.message.reply_text("Bekor qilindi.")
        return ConversationHandler.END

    user = update.effective_user
    text = update.message.text.strip()
    msg_id = db.add_user_message(user.id, user.username or user.first_name, text)

    for admin_id in config.get_admins():
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=(
                    f"📩 <b>Yangi xabar #{msg_id}</b>\n\n"
                    f"👤 {user.first_name} (@{user.username or '—'}) — <code>{user.id}</code>\n\n"
                    f"{text}"
                ),
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ O'qildi", callback_data=f"admin_msg_read|{msg_id}")]
                ])
            )
        except Exception as e:
            logger.error(f"Message notify error: {e}")

    await update.message.reply_text(
        "✅ Xabaringiz yuborildi! Admin tez orada javob beradi.",
        reply_markup=main_menu_keyboard(is_admin(user.id), has_active_contest())
    )
    return ConversationHandler.END


# ─────────────────────────────────────────────────────────────────────────────
# CONTEST (USER)
# ─────────────────────────────────────────────────────────────────────────────

async def user_contest_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await track_user(update)
    contest = db.get_active_contest()
    if not contest:
        await query.edit_message_text(
            "Hozircha faol konkurs yo'q.", reply_markup=back_button("back_main")
        )
        return

    user = query.from_user
    tickets = db.get_user_contest_tickets(contest['id'], user.id)
    end_at = contest['end_at']
    if isinstance(end_at, str):
        end_str = end_at[:16].replace("T", " ")
    else:
        end_str = str(end_at)[:16]

    await query.edit_message_text(
        f"🎁 <b>{contest['title']}</b>\n\n"
        f"{contest.get('description', '')}\n\n"
        f"⏰ Tugash: <b>{end_str}</b>\n"
        f"🎟 Sizning biletlaringiz: <b>{tickets} ta</b>\n\n"
        "💡 Har bir skin xaridi = 1 bilet!\n"
        "Ko'p skin olsangiz — g'olib bo'lish imkoniyati oshadi!",
        parse_mode="HTML", reply_markup=back_button("back_main")
    )


# ─────────────────────────────────────────────────────────────────────────────
# PURCHASE FLOW
# ─────────────────────────────────────────────────────────────────────────────

async def buy_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await track_user(update)
    skin_id = int(query.data.split("|")[1])
    skin = db.get_skin(skin_id)
    if not skin:
        await query.answer("❌ Skin topilmadi!", show_alert=True)
        return ConversationHandler.END

    context.user_data['buying_skin_id'] = skin_id
    text = (
        f"🛒 <b>Buyurtma: {skin['name']}</b>\n"
        f"💵 To'lash kerak: <b>{skin['price']:,.0f} so'm</b>\n\n"
        f"💳 <b>To'lov rekvizitlari:</b>\n<code>{config.get_card_info()}</code>\n\n"
        "📸 To'lovni amalga oshirib, <b>chek (screenshot)</b> rasmini yuboring:"
    )
    await query.message.reply_text(text, parse_mode="HTML")
    return USER_WAITING_PAYMENT_SCREENSHOT


async def receive_payment_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await track_user(update)
    if not update.message.photo:
        await update.message.reply_text("❌ Iltimos, to'lov chekini <b>rasm</b> ko'rinishida yuboring.", parse_mode="HTML")
        return USER_WAITING_PAYMENT_SCREENSHOT

    skin_id = context.user_data.get('buying_skin_id')
    if not skin_id:
        await update.message.reply_text("❌ Xatolik: buyurtma topilmadi. /start bosing.", parse_mode="HTML")
        return ConversationHandler.END

    skin = db.get_skin(skin_id)
    if not skin:
        await update.message.reply_text("❌ Skin topilmadi.")
        return ConversationHandler.END

    photo_id = update.message.photo[-1].file_id
    user = update.effective_user
    order_id = db.create_order(user.id, user.username or user.first_name, skin_id, photo_id)
    context.user_data['current_order_id'] = order_id
    username_display = f"@{user.username}" if user.username else user.first_name

    for admin_id in config.get_admins():
        try:
            await context.bot.send_photo(
                chat_id=admin_id, photo=photo_id,
                caption=(
                    f"💰 YANGI TOLOV CHEKI\n\n"
                    f"👤 Mijoz: {username_display} ({user.id})\n"
                    f"🎨 Skin: {skin['name']}\n"
                    f"💵 Summa: {skin['price']:,.0f} so'm\n"
                    f"🆔 Buyurtma ID: {order_id}"
                ),
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"admin_confirm|{order_id}"),
                        InlineKeyboardButton("❌ Rad etish", callback_data=f"admin_reject|{order_id}")
                    ]
                ])
            )
        except Exception as e:
            logger.error(f"Admin notify error: {e}")

    await update.message.reply_text(
        "✅ Chek qabul qilindi! Adminlar tasdiqlashini kuting...\n⏳ Odatda 5-15 daqiqa.",
        parse_mode="HTML"
    )
    return ConversationHandler.END


async def admin_confirm_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    order_id = int(query.data.split("|")[1])
    order = db.get_order(order_id)
    skin = db.get_skin(order['skin_id'])
    skin_name = skin['name'] if skin else "Noma'lum"
    price_line = f"Summa: {skin['price']:,.0f} so'm\n" if skin else ""
    new_caption = (
        f"💰 Yangi tolov cheki\n\n"
        f"Mijoz: {order['username']} ({order['user_id']})\n"
        f"Skin: {skin_name}\n"
        f"{price_line}"
        f"Buyurtma ID: {order_id}\n\nSTATUS: Tasdiqlandi ✅"
    )
    try:
        await query.edit_message_caption(caption=new_caption)
    except Exception as e:
        logger.error(f"Caption edit error: {e}")

    db.update_order_status(order_id, 'payment_confirmed')
    try:
        await context.bot.send_message(
            chat_id=order['user_id'],
            text=(
                "✅ <b>To'lovingiz tasdiqlandi!</b>\n\n"
                "🔗 Endi Steam Trade linkingizni yuboring.\n"
                "Steam > Inventar > Trade Offers > My Trade URL"
            ),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"User notify error: {e}")


async def admin_reject_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    order_id = int(query.data.split("|")[1])
    order = db.get_order(order_id)
    db.update_order_status(order_id, 'rejected')
    skin = db.get_skin(order['skin_id'])
    skin_name = skin['name'] if skin else "Noma'lum"
    try:
        await query.edit_message_caption(
            caption=f"Rad etildi\nMijoz: {order['username']}\nSkin: {skin_name}\nID: {order_id}\nSTATUS: ❌"
        )
    except Exception:
        pass
    try:
        await context.bot.send_message(
            chat_id=order['user_id'],
            text="❌ Afsuski, tolovingiz tasdiqlanmadi. Admin bilan bog'laning."
        )
    except Exception as e:
        logger.error(f"User reject notify: {e}")


async def receive_steam_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await track_user(update)
    text = update.message.text
    user = update.effective_user
    order = db.get_active_order_for_user(user.id)
    if not order:
        return
    if "steamcommunity.com/tradeoffer" not in text:
        await update.message.reply_text("❌ Noto'g'ri Steam Trade link.", parse_mode="HTML")
        return

    db.update_order_steam_link(order['id'], text)
    db.update_order_status(order['id'], 'steam_link_received')
    skin = db.get_skin(order['skin_id'])

    for admin_id in config.get_admins():
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=(
                    f"🔗 <b>Steam Trade Link!</b>\n\n"
                    f"👤 @{order['username']} (<code>{order['user_id']}</code>)\n"
                    f"🎨 {skin['name']}\n"
                    f"🔗 <a href=\"{text}\">Link</a>\n🆔 #{order['id']}"
                ),
                parse_mode="HTML", disable_web_page_preview=True,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Skin yuborildi", callback_data=f"admin_skin_sent|{order['id']}")]
                ])
            )
        except Exception as e:
            logger.error(f"Admin steam notify: {e}")

    await update.message.reply_text("✅ Trade link qabul qilindi! Kutib turing...", parse_mode="HTML")


async def admin_skin_sent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    order_id = int(query.data.split("|")[1])
    order = db.get_order(order_id)
    skin = db.get_skin(order['skin_id'])
    skin_name = skin['name'] if skin else "Skin"
    await query.edit_message_text(
        f"📸 <b>{skin_name}</b> — screenshot yuboring:\n(Buyurtma #{order_id})",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Bekor", callback_data=f"admin_cancel_trade|{order_id}")]
        ])
    )
    context.user_data['skin_sent_order_id'] = order_id
    return ADMIN_WAITING_TRADE_CONFIRM


async def receive_trade_confirm_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    if not update.message.photo:
        await update.message.reply_text("❌ Screenshot rasm bo'lishi kerak.")
        return ADMIN_WAITING_TRADE_CONFIRM

    order_id = context.user_data.get('skin_sent_order_id')
    if not order_id:
        return ConversationHandler.END

    order = db.get_order(order_id)
    if not order:
        return ConversationHandler.END

    confirm_photo = update.message.photo[-1].file_id
    skin = db.get_skin(order['skin_id'])
    skin_name = skin['name'] if skin else "Skin"

    db.update_order_status(order_id, 'completed')
    db.mark_skin_sold(order['skin_id'])

    contest = db.get_active_contest()
    if contest:
        db.add_contest_entry(contest['id'], order['user_id'], order_id)
        try:
            tickets = db.get_user_contest_tickets(contest['id'], order['user_id'])
            await context.bot.send_message(
                chat_id=order['user_id'],
                text=(
                    f"🎁 <b>Konkursga qo'shildingiz!</b>\n"
                    f"🎟 Jami biletlaringiz: <b>{tickets} ta</b>\n"
                    f"⏰ Tugash: {contest['end_at']}"
                ),
                parse_mode="HTML"
            )
        except Exception:
            pass

    try:
        await context.bot.send_photo(
            chat_id=order['user_id'], photo=confirm_photo,
            caption=f"🎮 <b>{skin_name} yuborildi!</b>\n\nXarid uchun rahmat! 🎉",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Skin yetib keldi!", callback_data=f"user_skin_received|{order_id}")]
            ])
        )
    except Exception as e:
        logger.error(f"User confirm notify: {e}")

    await update.message.reply_text("✅ Buyurtma yakunlandi!", parse_mode="HTML")
    context.user_data.pop('skin_sent_order_id', None)
    return ConversationHandler.END


async def user_skin_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    order_id = int(query.data.split("|")[1])
    order = db.get_order(order_id)
    skin = db.get_skin(order['skin_id']) if order else None
    skin_name = skin['name'] if skin else "Skin"
    await query.edit_message_text(
        f"🎉 <b>Tabriklaymiz!</b>\n✅ {skin_name} qabul qilindi!\nXarid uchun rahmat! 🎮",
        parse_mode="HTML"
    )


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN PANEL
# ─────────────────────────────────────────────────────────────────────────────

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        user = query.from_user
    else:
        user = update.effective_user

    if not is_admin(user.id):
        if query:
            await query.answer("❌ Siz admin emassiz!", show_alert=True)
        return

    unread = db.get_unread_messages_count()
    text = "⚙️ <b>Admin Panel</b>\nNimani qilmoqchisiz?"
    kb = admin_panel_keyboard(unread)
    if query:
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)


async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return

    revenue = db.get_revenue_stats()
    users = db.get_users_stats()
    sold_count = db.count_completed_sales()

    text = (
        "📊 <b>Savdo statistikasi</b>\n\n"
        f"💰 Bugun: <b>{revenue['today']:,.0f} so'm</b>\n"
        f"💰 Haftalik: <b>{revenue['week']:,.0f} so'm</b>\n"
        f"💰 Oylik: <b>{revenue['month']:,.0f} so'm</b>\n\n"
        "👥 <b>Foydalanuvchilar</b>\n"
        f"• Jami: <b>{users['total']}</b>\n"
        f"• Bugun qo'shilgan: <b>{users['today']}</b>\n"
        f"• Faol (7 kun): <b>{users['active']}</b>\n\n"
        f"🛍 Sotilgan buyurtmalar: <b>{sold_count}</b>"
    )
    await query.edit_message_text(
        text, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")]
        ])
    )


async def admin_subscribers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return

    channel_id = config.get_channel_id()
    count_text = "Kanal ID sozlanmagan"
    if channel_id:
        try:
            count = await context.bot.get_chat_member_count(channel_id)
            count_text = f"<b>{count:,}</b> ta obunachi"
        except Exception as e:
            count_text = f"Xatolik: bot kanalda admin bo'lishi kerak ({e})"

    bot_users = db.get_users_count()
    await query.edit_message_text(
        f"👥 <b>Obunachilar</b>\n\n"
        f"📢 Kanal: {count_text}\n"
        f"🤖 Bot foydalanuvchilari: <b>{bot_users}</b>\n\n"
        f"Kanal ID: <code>{channel_id or 'sozlanmagan'}</code>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📌 Kanal ID o'rnatish", callback_data="admin_set_channel")],
            [InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")],
        ])
    )


async def admin_set_channel_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "Kanal ID yoki @username yuboring (masalan: @cs2shop):"
    )
    return ADMIN_WAITING_CHANNEL_ID


async def admin_save_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    config.set_channel_id(update.message.text.strip())
    await update.message.reply_text("✅ Kanal ID saqlandi!")
    return ConversationHandler.END


async def admin_sold_items(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return

    page = 0
    if "|" in query.data:
        page = int(query.data.split("|")[1])

    limit = 15
    sales = db.get_completed_sales(limit=limit, offset=page * limit)
    total = db.count_completed_sales()

    if not sales:
        await query.edit_message_text(
            "🛍 Hozircha sotilgan buyum yo'q.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")]
            ])
        )
        return

    lines = []
    for s in sales:
        lines.append(
            f"#{s.get('order_id', s.get('id', '?'))} — "
            f"@{s.get('username', '?')} — {s.get('skin_name', '?')} "
            f"({s.get('price', 0):,.0f} so'm)"
        )
    text = f"🛍 <b>Sotilgan buyumlar</b> ({total} ta)\n\n" + "\n".join(lines)

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"admin_sold_items|{page-1}"))
    if (page + 1) * limit < total:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"admin_sold_items|{page+1}"))
    buttons = [nav] if nav else []
    buttons.append([InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")])

    await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(buttons))


async def admin_user_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return

    messages = db.get_user_messages(limit=20)
    if not messages:
        await query.edit_message_text(
            "📩 Xabarlar yo'q.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")]
            ])
        )
        return

    lines = []
    buttons = []
    for m in messages:
        status = "🆕" if not m.get('is_read') else "✅"
        preview = m['message_text'][:40] + "..." if len(m['message_text']) > 40 else m['message_text']
        lines.append(f"{status} #{m['id']} @{m.get('username', '?')}: {preview}")
        buttons.append([InlineKeyboardButton(
            f"{status} #{m['id']} — {preview[:25]}",
            callback_data=f"admin_msg_detail|{m['id']}"
        )])
    buttons.append([InlineKeyboardButton("✅ Hammasini o'qildi", callback_data="admin_msg_read_all")])
    buttons.append([InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")])

    await query.edit_message_text(
        "📩 <b>Foydalanuvchi xabarlari</b>\n\n" + "\n".join(lines[:10]),
        parse_mode="HTML", reply_markup=InlineKeyboardMarkup(buttons)
    )


async def admin_msg_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    msg_id = int(query.data.split("|")[1])
    messages = db.get_user_messages(limit=100)
    msg = next((m for m in messages if m['id'] == msg_id), None)
    if not msg:
        return
    db.mark_message_read(msg_id)
    await query.edit_message_text(
        f"📩 <b>Xabar #{msg_id}</b>\n\n"
        f"👤 @{msg.get('username', '?')} — <code>{msg['user_id']}</code>\n"
        f"📅 {msg.get('created_at', '')}\n\n"
        f"{msg['message_text']}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Xabarlarga", callback_data="admin_user_messages")]
        ])
    )


async def admin_msg_read(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("✅ O'qildi")
    if not is_admin(query.from_user.id):
        return
    msg_id = int(query.data.split("|")[1])
    db.mark_message_read(msg_id)
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass


async def admin_msg_read_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("✅ Hammasi o'qildi")
    if not is_admin(query.from_user.id):
        return
    db.mark_all_messages_read()
    await admin_user_messages(update, context)


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN: CONTEST
# ─────────────────────────────────────────────────────────────────────────────

async def admin_contest_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return

    contest = db.get_active_contest()
    if contest:
        leaderboard = db.get_contest_leaderboard(contest['id'], limit=5)
        lb_text = "\n".join(
            f"{i+1}. @{e.get('username') or e.get('first_name')} — {e['tickets']} bilet"
            for i, e in enumerate(leaderboard)
        ) or "Hali ishtirokchilar yo'q"
        text = (
            f"🎁 <b>Faol konkurs:</b> {contest['title']}\n"
            f"⏰ Tugash: {contest['end_at']}\n\n"
            f"🏆 Top 5:\n{lb_text}"
        )
        buttons = [
            [InlineKeyboardButton("⏹ Konkursni to'xtatish", callback_data=f"admin_contest_stop|{contest['id']}")],
            [InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")],
        ]
    else:
        text = "🎁 Faol konkurs yo'q.\nYangi konkurs yaratishni xohlaysizmi?"
        buttons = [
            [InlineKeyboardButton("➕ Konkurs yaratish", callback_data="admin_contest_create")],
            [InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")],
        ]
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(buttons))


async def admin_contest_create_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🎁 Konkurs nomini yozing (masalan: Bahor yutuqli o'yini):")
    return ADMIN_WAITING_CONTEST_TITLE


async def admin_contest_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['contest_title'] = update.message.text.strip()
    await update.message.reply_text("Konkurs tavsifini yozing (qoidalarni tushuntiring):")
    return ADMIN_WAITING_CONTEST_DESC


async def admin_contest_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['contest_desc'] = update.message.text.strip()
    await update.message.reply_text(
        "Tugash vaqtini yozing:\n"
        "Format: <code>2026-06-30 23:59</code>",
        parse_mode="HTML"
    )
    return ADMIN_WAITING_CONTEST_END


async def admin_contest_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    try:
        end_at = datetime.strptime(update.message.text.strip(), "%Y-%m-%d %H:%M")
    except ValueError:
        await update.message.reply_text("❌ Noto'g'ri format. Masalan: 2026-06-30 23:59")
        return ADMIN_WAITING_CONTEST_END

    title = context.user_data.get('contest_title', 'Konkurs')
    desc = context.user_data.get('contest_desc', '')
    contest_id = db.create_contest(title, desc, end_at.strftime("%Y-%m-%d %H:%M:%S"))

    broadcast_text = (
        f"🎁🎉 <b>YANGI KONKURS!</b> 🎉🎁\n\n"
        f"<b>{title}</b>\n\n"
        f"{desc}\n\n"
        f"📌 <b>Qoida:</b> Har bir skin xaridi = 1 bilet!\n"
        f"Ko'p skin olsangiz — g'olib bo'lish imkoniyati ko'payadi!\n\n"
        f"⏰ <b>Tugash muddati:</b> {end_at.strftime('%d.%m.%Y %H:%M')}\n\n"
        f"Bosh menu → 🎁 Konkurs tugmasidan biletlaringizni kuzating!"
    )

    users = db.get_all_users()
    sent = 0
    for uid in users:
        try:
            await context.bot.send_message(chat_id=uid, text=broadcast_text, parse_mode="HTML")
            sent += 1
        except Exception:
            pass

    await update.message.reply_text(
        f"✅ Konkurs #{contest_id} yaratildi!\n📨 {sent} foydalanuvchiga yuborildi.",
        parse_mode="HTML"
    )
    context.user_data.pop('contest_title', None)
    context.user_data.pop('contest_desc', None)
    return ConversationHandler.END


async def admin_contest_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    contest_id = int(query.data.split("|")[1])
    contest = db.get_active_contest()
    db.stop_contest(contest_id)

    stop_text = (
        f"⏹ <b>Konkurs yakunlandi!</b>\n\n"
        f"🎁 {contest['title'] if contest else 'Konkurs'}\n"
        f"G'oliblar tez orada e'lon qilinadi. Botdan kuzatib boring!"
    )
    for uid in db.get_all_users():
        try:
            await context.bot.send_message(chat_id=uid, text=stop_text, parse_mode="HTML")
        except Exception:
            pass
    await query.edit_message_text("✅ Konkurs to'xtatildi va foydalanuvchilarga xabar yuborildi.")
    await admin_contest_menu(update, context)


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN: SERVICES SETTINGS
# ─────────────────────────────────────────────────────────────────────────────

async def admin_services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return

    services = config.get_services()
    lines = []
    for key, label in SERVICE_LABELS.items():
        s = services.get(key, {})
        status = "✅" if s.get("enabled") else "❌"
        plans = s.get("plans", [])
        active = len([p for p in plans if p.get("enabled", True)])
        lines.append(f"{status} {label}: {active} ta variant")

    await query.edit_message_text(
        "🛎 <b>Xizmatlar sozlamalari</b>\n\n" + "\n".join(lines) +
        "\n\nHar bir xizmat ichida variantlar (1 oy, 3 oy, 100 stars...) boshqariladi.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⭐ Premium", callback_data="admin_svc|premium")],
            [InlineKeyboardButton("✨ Stars", callback_data="admin_svc|stars")],
            [InlineKeyboardButton("🎮 Steam", callback_data="admin_svc|steam_topup")],
            [InlineKeyboardButton("🤖 Gemini API kalitlari", callback_data="admin_gemini_keys")],
            [InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")],
        ])
    )


async def admin_service_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xizmat ichidagi barcha variantlar ro'yxati."""
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    key = query.data.split("|")[1]
    svc = config.get_service(key)
    context.user_data['edit_service'] = key
    label = SERVICE_LABELS.get(key, key)
    enabled = svc.get("enabled", True)
    status_text = "Yoqilgan" if enabled else "O'chirilgan"
    plans = svc.get("plans", [])

    await query.edit_message_text(
        f"🛎 <b>{label}</b>\nHolat: {status_text}\n\n"
        f"Variantlar ({len(plans)} ta). Tahrirlash uchun tanlang:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            *[[InlineKeyboardButton(
                f"{'✅' if p.get('enabled', True) else '❌'} {p['name']} — {p.get('price', 0):,.0f} so'm",
                callback_data=f"admin_svcplan|{key}|{p['id']}"
            )] for p in plans],
            [InlineKeyboardButton("➕ Yangi variant qo'shish", callback_data=f"admin_svc_addplan|{key}")],
            [InlineKeyboardButton(
                "🔴 Butun xizmatni o'chirish" if enabled else "🟢 Butun xizmatni yoqish",
                callback_data=f"admin_svc_toggle|{key}"
            )],
            [InlineKeyboardButton("🔙 Xizmatlar", callback_data="admin_services")],
        ])
    )


async def admin_service_plan_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bitta variantni tahrirlash."""
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    parts = query.data.split("|")
    key, plan_id = parts[1], parts[2]
    plan = config.get_service_plan(key, plan_id)
    if not plan:
        await query.answer("Topilmadi!", show_alert=True)
        return

    context.user_data['edit_service'] = key
    context.user_data['edit_plan_id'] = plan_id
    enabled = plan.get("enabled", True)
    price = plan.get("price", 0)
    price_txt = f"{price:,.0f} so'm" if price else "Kelishiladi (0)"

    plan_status = "Yoqilgan" if enabled else "O'chirilgan"
    await query.edit_message_text(
        f"📦 <b>{plan.get('name', '')}</b>\n"
        f"💵 Narx: {price_txt}\n"
        f"Holat: {plan_status}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ Nomni o'zgartirish", callback_data=f"admin_svc_editname|{key}|{plan_id}")],
            [InlineKeyboardButton("💵 Narxni o'zgartirish", callback_data=f"admin_svc_editprice|{key}|{plan_id}")],
            [InlineKeyboardButton(
                "🔴 O'chirish" if enabled else "🟢 Yoqish",
                callback_data=f"admin_svc_plantoggle|{key}|{plan_id}"
            )],
            [InlineKeyboardButton("🗑 Variantni o'chirish", callback_data=f"admin_svc_delplan|{key}|{plan_id}")],
            [InlineKeyboardButton("🔙 Orqaga", callback_data=f"admin_svc|{key}")],
        ])
    )


async def admin_svc_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    key = query.data.split("|")[1]
    svc = config.get_service(key)
    config.update_service_field(key, "enabled", not svc.get("enabled", True))
    await admin_service_detail(update, context)


async def admin_svc_plan_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    parts = query.data.split("|")
    key, plan_id = parts[1], parts[2]
    plan = config.get_service_plan(key, plan_id)
    config.update_service_plan(key, plan_id, enabled=not plan.get("enabled", True))
    await admin_service_plan_detail(update, context)


async def admin_svc_delete_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("O'chirildi")
    if not is_admin(query.from_user.id):
        return
    parts = query.data.split("|")
    key, plan_id = parts[1], parts[2]
    config.remove_service_plan(key, plan_id)
    await admin_service_detail(update, context)


async def admin_svc_addplan_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    key = query.data.split("|")[1]
    context.user_data['edit_service'] = key
    hints = {
        "premium": "Masalan: 1 oy, 3 oy, 6 oy, 12 oy",
        "stars": "Masalan: 50 ta, 100 ta, 250 ta",
        "steam_topup": "Masalan: 50 000 so'm, 100 000 so'm",
    }
    await query.edit_message_text(
        f"➕ <b>Yangi variant</b>\n\n"
        f"Variant nomini yozing:\n<i>{hints.get(key, 'Masalan: 1 oy')}</i>",
        parse_mode="HTML"
    )
    return ADMIN_ADD_PLAN_NAME


async def admin_svc_addplan_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['new_plan_name'] = update.message.text.strip()
    await update.message.reply_text(
        "💵 Narxni yozing (faqat raqam).\n"
        "Erkin summa uchun 0 yozing:"
    )
    return ADMIN_ADD_PLAN_PRICE


async def admin_svc_addplan_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key = context.user_data.get('edit_service')
    name = context.user_data.get('new_plan_name', 'Variant')
    try:
        price = float(update.message.text.replace(",", "").replace(" ", "").strip())
    except ValueError:
        await update.message.reply_text("❌ Faqat raqam kiriting.")
        return ADMIN_ADD_PLAN_PRICE

    plan_id = config.add_service_plan(key, name, price)
    await update.message.reply_text(
        f"✅ Variant qo'shildi!\n📦 {name} — {price:,.0f} so'm (ID: {plan_id})",
        parse_mode="HTML"
    )
    context.user_data.pop('new_plan_name', None)
    return ConversationHandler.END


async def admin_svc_editname_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("|")
    context.user_data['edit_service'] = parts[1]
    context.user_data['edit_plan_id'] = parts[2]
    await query.edit_message_text("Yangi nomni yozing:")
    return ADMIN_EDIT_PLAN_NAME


async def admin_svc_editname_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key = context.user_data.get('edit_service')
    plan_id = context.user_data.get('edit_plan_id')
    config.update_service_plan(key, plan_id, name=update.message.text.strip())
    await update.message.reply_text("✅ Nom yangilandi!")
    return ConversationHandler.END


async def admin_svc_editprice_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("|")
    context.user_data['edit_service'] = parts[1]
    context.user_data['edit_plan_id'] = parts[2]
    await query.edit_message_text("Yangi narxni yozing (faqat raqam, erkin summa uchun 0):")
    return ADMIN_EDIT_PLAN_PRICE


async def admin_svc_editprice_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key = context.user_data.get('edit_service')
    plan_id = context.user_data.get('edit_plan_id')
    try:
        price = float(update.message.text.replace(",", "").replace(" ", "").strip())
    except ValueError:
        await update.message.reply_text("❌ Faqat raqam kiriting.")
        return ADMIN_EDIT_PLAN_PRICE
    config.update_service_plan(key, plan_id, price=price)
    await update.message.reply_text(f"✅ Narx yangilandi: {price:,.0f} so'm")
    return ConversationHandler.END


async def admin_gemini_keys_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return

    keys = config.get_gemini_api_keys()
    lines = []
    for i, k in enumerate(keys[:10], 1):
        masked = f"...{k[-6:]}" if len(k) > 6 else "***"
        lines.append(f"{i}. {masked}")
    extra = f"\n... va yana {len(keys) - 10} ta" if len(keys) > 10 else ""

    await query.edit_message_text(
        f"🤖 <b>Gemini API kalitlari</b>\n\n"
        f"Jami: <b>{len(keys)}</b> ta kalit\n"
        f"Limit tugasa avtomatik keyingisiga o'tadi.\n\n"
        + ("\n".join(lines) + extra if lines else "Hali kalit yo'q."),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Kalit qo'shish", callback_data="admin_gemini_add")],
            [InlineKeyboardButton("🗑 Barchasini o'chirish", callback_data="admin_gemini_clear")],
            [InlineKeyboardButton("🔙 Xizmatlar", callback_data="admin_services")],
        ])
    )


async def admin_gemini_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    await query.edit_message_text(
        "🤖 <b>Gemini API kalitlarini yuboring</b>\n\n"
        "Har bir kalit yangi qatorda yoki vergul bilan:\n"
        "<code>AIza...key1\nAIza...key2</code>\n\n"
        "30 tagacha kalit qo'shishingiz mumkin.\n"
        "Olish: https://aistudio.google.com/apikey",
        parse_mode="HTML"
    )
    return ADMIN_WAITING_GEMINI_KEYS


async def admin_gemini_save_keys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END

    text = update.message.text.strip()
    new_keys = []
    for part in text.replace(",", "\n").split("\n"):
        k = part.strip()
        if k and len(k) > 10:
            new_keys.append(k)

    if not new_keys:
        await update.message.reply_text("❌ Hech qanday kalit topilmadi. Qayta yuboring.")
        return ADMIN_WAITING_GEMINI_KEYS

    added = config.add_gemini_api_keys(new_keys)
    total = len(config.get_gemini_api_keys())
    await update.message.reply_text(
        f"✅ {added} ta yangi kalit qo'shildi!\n"
        f"Jami: <b>{total}</b> ta kalit faol.",
        parse_mode="HTML"
    )
    return ConversationHandler.END


async def admin_gemini_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("O'chirildi")
    if not is_admin(query.from_user.id):
        return
    config.clear_gemini_api_keys()
    await admin_gemini_keys_menu(update, context)


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN: BROADCAST
# ─────────────────────────────────────────────────────────────────────────────

async def admin_broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    user_count = db.get_users_count()
    await query.edit_message_text(
        f"📢 <b>E'lon yuborish</b>\n👥 Jami: <b>{user_count}</b>\n\nMatn yoki rasm yuboring.\n/cancel — bekor",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Bekor", callback_data="admin_panel")]])
    )
    return ADMIN_WAITING_BROADCAST


async def admin_broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    if update.message.text == "/cancel":
        await update.message.reply_text("Bekor qilindi.")
        return ConversationHandler.END

    users = db.get_all_users()
    sent, failed = 0, 0
    status_msg = await update.message.reply_text(f"📤 0/{len(users)}")

    for user_id in users:
        try:
            if update.message.photo:
                await context.bot.send_photo(
                    chat_id=user_id, photo=update.message.photo[-1].file_id,
                    caption=update.message.caption or "", parse_mode="HTML"
                )
            else:
                await context.bot.send_message(chat_id=user_id, text=update.message.text, parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1
        if (sent + failed) % 25 == 0:
            try:
                await status_msg.edit_text(f"📤 {sent + failed}/{len(users)}")
            except Exception:
                pass

    await status_msg.edit_text(f"✅ Yuborildi: {sent} | ❌ Xato: {failed}", parse_mode="HTML")
    return ConversationHandler.END


async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await admin_panel(update, context)


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN: ADD SKIN FLOW
# ─────────────────────────────────────────────────────────────────────────────

async def admin_add_skin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    context.user_data['new_skin'] = {}
    buttons = [
        [InlineKeyboardButton("🔪 Pichoq", callback_data="newskin_cat|knife")],
        [InlineKeyboardButton("🔫 Miltiq", callback_data="newskin_cat|gun")],
        [InlineKeyboardButton("📦 Keys", callback_data="newskin_cat|case")],
        [InlineKeyboardButton("🎨 Stiker", callback_data="newskin_cat|sticker")],
        [InlineKeyboardButton("🔑 Brelok", callback_data="newskin_cat|charm")],
        [InlineKeyboardButton("❌ Bekor", callback_data="admin_panel")],
    ]
    await query.edit_message_text("➕ Kategoriyani tanlang:", reply_markup=InlineKeyboardMarkup(buttons))
    return ADMIN_WAITING_SKIN_CATEGORY


async def admin_skin_category_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat = query.data.split("|")[1]
    context.user_data['new_skin']['category'] = cat

    if cat == "knife":
        buttons, row = [], []
        for knife in knife_types():
            row.append(InlineKeyboardButton(knife, callback_data=f"newskin_sub|{knife}"))
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
    elif cat == "gun":
        buttons = [[InlineKeyboardButton(label, callback_data=f"newskin_guntype|{key}")]
                   for key, (label, _) in gun_subcategories().items()]
    elif cat in ("case", "sticker", "charm"):
        cat_labels = {"case": "Keys", "sticker": "Stiker", "charm": "Brelok"}
        context.user_data['new_skin']['item_name'] = cat_labels[cat]
        await query.edit_message_text(f"✏️ {cat_labels[cat]} nomini yozing:")
        return ADMIN_WAITING_SKIN_NAME
    else:
        return ADMIN_WAITING_SKIN_CATEGORY

    await query.edit_message_text("Tur tanlang:", reply_markup=InlineKeyboardMarkup(buttons))
    return ADMIN_WAITING_SKIN_SUBCATEGORY


async def admin_skin_guntype_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data.split("|")[1]
    context.user_data['new_skin']['subcategory'] = key
    _, guns = gun_subcategories()[key]
    buttons, row = [], []
    for gun in guns:
        row.append(InlineKeyboardButton(gun, callback_data=f"newskin_sub|{gun}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    await query.edit_message_text("Qurolni tanlang:", reply_markup=InlineKeyboardMarkup(buttons))
    return ADMIN_WAITING_SKIN_SUBCATEGORY


async def admin_skin_item_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    item_name = query.data.split("|", 1)[1]
    context.user_data['new_skin']['item_name'] = item_name
    await query.edit_message_text(f"✅ {item_name}\n\nSkin nomini yozing:")
    return ADMIN_WAITING_SKIN_NAME


async def admin_skin_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['new_skin']['name'] = update.message.text
    await update.message.reply_text("📸 Skin rasmini yuboring:")
    return ADMIN_WAITING_SKIN_PHOTO


async def admin_skin_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("❌ Rasm yuboring.")
        return ADMIN_WAITING_SKIN_PHOTO
    context.user_data['new_skin']['photo_id'] = update.message.photo[-1].file_id
    await update.message.reply_text("💵 Narx (faqat raqam):")
    return ADMIN_WAITING_SKIN_PRICE


async def admin_skin_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = float(update.message.text.replace(",", "").replace(" ", "").strip())
        context.user_data['new_skin']['price'] = price
    except ValueError:
        await update.message.reply_text("❌ Faqat raqam:")
        return ADMIN_WAITING_SKIN_PRICE
    await update.message.reply_text("📊 Float (yoki - o'tkazib yuborish):")
    return ADMIN_WAITING_SKIN_FLOAT


async def admin_skin_float(update: Update, context: ContextTypes.DEFAULT_TYPE):
    val = update.message.text.strip()
    context.user_data['new_skin']['float_value'] = None if val == "-" else val
    await update.message.reply_text(
        "⚡ StatTrak™?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Ha", callback_data="stattrak|yes"),
             InlineKeyboardButton("❌ Yo'q", callback_data="stattrak|no")]
        ])
    )
    return ADMIN_WAITING_SKIN_STATTRAK


async def admin_skin_stattrak(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['new_skin']['is_stattrak'] = query.data.split("|")[1] == "yes"
    skin = context.user_data['new_skin']
    skin_id = db.add_skin(
        category=skin.get('category'), subcategory=skin.get('subcategory'),
        item_name=skin.get('item_name'), name=skin.get('name'),
        photo_id=skin.get('photo_id'), price=skin.get('price'),
        float_value=skin.get('float_value'), is_stattrak=skin.get('is_stattrak', False)
    )
    await query.edit_message_text(f"✅ Skin qo'shildi! ID: <code>{skin_id}</code>", parse_mode="HTML")
    context.user_data.pop('new_skin', None)
    return ConversationHandler.END


async def admin_list_skins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return

    page = int(query.data.split("|")[1]) if "|" in query.data else 0
    limit = 20
    skins = db.get_all_skins(limit=limit, offset=page * limit)
    total = db.count_skins()

    if not skins:
        await query.edit_message_text("📋 Skinlar yo'q.", reply_markup=back_button("admin_panel"))
        return

    buttons = []
    for skin in skins:
        status = "✅" if not skin.get('sold') else "❌"
        buttons.append([InlineKeyboardButton(
            f"{status} {skin['item_name']} | {skin['name']} — {skin['price']:,.0f}",
            callback_data=f"admin_skin_detail|{skin['id']}"
        )])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"admin_list_skins|{page-1}"))
    if (page + 1) * limit < total:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"admin_list_skins|{page+1}"))
    if nav:
        buttons.append(nav)
    buttons.append([InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")])

    await query.edit_message_text(
        f"📋 Skinlar ({total} ta):", parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def admin_skin_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    skin_id = int(query.data.split("|")[1])
    skin = db.get_skin(skin_id)
    if not skin:
        return
    sold_val = "❌ SOTILGAN" if skin.get('sold') else "✅ Mavjud"
    text = (
        f"🎨 <b>{skin['name']}</b>\n🔫 {skin['item_name']}\n"
        f"💵 {skin['price']:,.0f} so'm\n{sold_val}\n🆔 {skin_id}"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🗑 O'chirish", callback_data=f"admin_delete_skin|{skin_id}")],
        [InlineKeyboardButton("🔙 Ro'yxat", callback_data="admin_list_skins|0")],
    ])
    if skin.get('photo_id'):
        await query.message.reply_photo(photo=skin['photo_id'], caption=text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)


async def admin_delete_skin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    skin_id = int(query.data.split("|")[1])
    db.delete_skin(skin_id)
    try:
        await query.edit_message_caption(caption="🗑 O'chirildi!", reply_markup=back_button("admin_list_skins|0"))
    except Exception:
        await query.edit_message_text("🗑 O'chirildi!", reply_markup=back_button("admin_list_skins|0"))


async def admin_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return

    page = int(query.data.split("|")[1]) if "|" in query.data else 0
    limit = 15
    orders = db.get_all_orders(limit=limit, offset=page * limit)
    total = db.count_orders()
    status_map = {'pending': '⏳', 'payment_confirmed': '✅', 'steam_link_received': '🔗',
                  'completed': '🎉', 'rejected': '❌'}

    if not orders:
        await query.edit_message_text("📦 Buyurtmalar yo'q.", reply_markup=back_button("admin_panel"))
        return

    buttons = []
    for order in orders:
        icon = status_map.get(order['status'], '❓')
        skin = db.get_skin(order['skin_id'])
        skin_name = skin['name'] if skin else '?'
        buttons.append([InlineKeyboardButton(
            f"{icon} #{order['id']} — {order['username']} — {skin_name}",
            callback_data=f"admin_order_detail|{order['id']}"
        )])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"admin_orders|{page-1}"))
    if (page + 1) * limit < total:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"admin_orders|{page+1}"))
    if nav:
        buttons.append(nav)
    buttons.append([InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")])

    await query.edit_message_text(
        f"📦 Buyurtmalar ({total}):", parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def admin_order_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    order_id = int(query.data.split("|")[1])
    order = db.get_order(order_id)
    if not order:
        return
    skin = db.get_skin(order['skin_id'])
    text = (
        f"📦 <b>#{order_id}</b>\n👤 @{order['username']} ({order['user_id']})\n"
        f"🎨 {skin['name'] if skin else 'N/A'}\n"
        f"💵 {(skin['price'] if skin else 0):,.0f} so'm\n📊 {order['status']}"
    )
    await query.edit_message_text(
        text, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="admin_orders|0")]])
    )


async def admin_manage_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    admins = config.get_admins()
    text = "👥 <b>Adminlar:</b>\n" + "\n".join(f"• <code>{a}</code>" for a in admins)
    await query.edit_message_text(
        text, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Qo'shish", callback_data="admin_add_admin")],
            [InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")],
        ])
    )


async def admin_add_admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Yangi admin Telegram ID:")
    return ADMIN_WAITING_NEW_ADMIN_ID


async def admin_add_admin_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    try:
        new_id = int(update.message.text.strip())
        config.add_admin(new_id)
        await update.message.reply_text(f"✅ Admin qo'shildi: <code>{new_id}</code>", parse_mode="HTML")
    except ValueError:
        await update.message.reply_text("❌ Noto'g'ri ID.")
    return ConversationHandler.END


async def admin_card_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    await query.edit_message_text(
        f"💳 Hozirgi:\n<code>{config.get_card_info()}</code>\n\nYangi karta ma'lumoti:",
        parse_mode="HTML"
    )
    return ADMIN_WAITING_NEW_BOT_TOKEN


async def admin_save_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    config.set_card_info(update.message.text.strip())
    await update.message.reply_text("✅ Karta yangilandi!")
    return ConversationHandler.END


# ─────────────────────────────────────────────────────────────────────────────
# APP SETUP
# ─────────────────────────────────────────────────────────────────────────────

def build_app() -> Application:
    bot_token = config.get_bot_token()
    if not bot_token:
        raise RuntimeError("BOT_TOKEN topilmadi! config.json yoki env o'rnating.")

    app = Application.builder().token(bot_token).build()

    admin_secret = config.get_admin_command()
    app.add_handler(CommandHandler(admin_secret, admin_cmd))
    app.add_handler(CommandHandler("start", start))

    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(buy_handler, pattern=r"^buy\|")],
        states={USER_WAITING_PAYMENT_SCREENSHOT: [MessageHandler(filters.PHOTO, receive_payment_screenshot)]},
        fallbacks=[CommandHandler("start", start)], per_message=False,
    ))

    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_skin_sent, pattern=r"^admin_skin_sent\|")],
        states={ADMIN_WAITING_TRADE_CONFIRM: [
            MessageHandler(filters.PHOTO, receive_trade_confirm_screenshot),
            MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: u.message.reply_text("❌ Rasm yuboring.")),
        ]},
        fallbacks=[CallbackQueryHandler(lambda u, c: ConversationHandler.END, pattern=r"^admin_cancel_trade\|")],
        per_message=False,
    ))

    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_add_skin_start, pattern=r"^admin_add_skin$")],
        states={
            ADMIN_WAITING_SKIN_CATEGORY: [CallbackQueryHandler(admin_skin_category_chosen, pattern=r"^newskin_cat\|")],
            ADMIN_WAITING_SKIN_SUBCATEGORY: [
                CallbackQueryHandler(admin_skin_item_chosen, pattern=r"^newskin_sub\|"),
                CallbackQueryHandler(admin_skin_guntype_chosen, pattern=r"^newskin_guntype\|"),
            ],
            ADMIN_WAITING_SKIN_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_skin_name)],
            ADMIN_WAITING_SKIN_PHOTO: [MessageHandler(filters.PHOTO, admin_skin_photo)],
            ADMIN_WAITING_SKIN_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_skin_price)],
            ADMIN_WAITING_SKIN_FLOAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_skin_float)],
            ADMIN_WAITING_SKIN_STATTRAK: [CallbackQueryHandler(admin_skin_stattrak, pattern=r"^stattrak\|")],
        },
        fallbacks=[CallbackQueryHandler(admin_panel, pattern=r"^admin_panel$")],
        per_message=False,
    ))

    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_add_admin_start, pattern=r"^admin_add_admin$")],
        states={ADMIN_WAITING_NEW_ADMIN_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_admin_id)]},
        fallbacks=[], per_message=False,
    ))

    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_card_settings, pattern=r"^admin_card_settings$")],
        states={ADMIN_WAITING_NEW_BOT_TOKEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_save_card)]},
        fallbacks=[], per_message=False,
    ))

    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_broadcast_start, pattern=r"^admin_broadcast$")],
        states={ADMIN_WAITING_BROADCAST: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, admin_broadcast_send),
            MessageHandler(filters.PHOTO, admin_broadcast_send),
        ]},
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
        per_message=False,
    ))



    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(user_contact_admin_start, pattern=r"^user_contact_admin$")],
        states={USER_WAITING_MESSAGE_TO_ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_user_message)]},
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
        per_message=False,
    ))

    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(service_plan_selected, pattern=r"^svcplan\|")],
        states={USER_WAITING_SERVICE_PAYMENT: [MessageHandler(filters.PHOTO, receive_service_payment)]},
        fallbacks=[
            CommandHandler("cancel", lambda u, c: ConversationHandler.END),
            CallbackQueryHandler(service_selected, pattern=r"^service\|"),
        ],
        per_message=False,
    ))

    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_svc_addplan_start, pattern=r"^admin_svc_addplan\|")],
        states={
            ADMIN_ADD_PLAN_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_svc_addplan_name)],
            ADMIN_ADD_PLAN_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_svc_addplan_price)],
        },
        fallbacks=[], per_message=False,
    ))

    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_svc_editname_start, pattern=r"^admin_svc_editname\|")],
        states={ADMIN_EDIT_PLAN_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_svc_editname_save)]},
        fallbacks=[], per_message=False,
    ))

    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_contest_create_start, pattern=r"^admin_contest_create$")],
        states={
            ADMIN_WAITING_CONTEST_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_contest_title)],
            ADMIN_WAITING_CONTEST_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_contest_desc)],
            ADMIN_WAITING_CONTEST_END: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_contest_end)],
        },
        fallbacks=[], per_message=False,
    ))

    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_set_channel_start, pattern=r"^admin_set_channel$")],
        states={ADMIN_WAITING_CHANNEL_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_save_channel)]},
        fallbacks=[], per_message=False,
    ))

    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_gemini_add_start, pattern=r"^admin_gemini_add$")],
        states={ADMIN_WAITING_GEMINI_KEYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_gemini_save_keys)]},
        fallbacks=[], per_message=False,
    ))

    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_svc_editprice_start, pattern=r"^admin_svc_editprice\|")],
        states={ADMIN_EDIT_PLAN_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_svc_editprice_save)]},
        fallbacks=[], per_message=False,
    ))

    app.add_handler(CallbackQueryHandler(category_handler, pattern=r"^(cat_knife|cat_gun|cat_case|cat_sticker|cat_charm|back_main)$"))
    app.add_handler(CallbackQueryHandler(subcat_handler, pattern=r"^gun_subcat\|"))
    app.add_handler(CallbackQueryHandler(show_skins_for_item, pattern=r"^(sub_knife|sub_gun|sub_case|sub_sticker|sub_charm)\|"))
    app.add_handler(CallbackQueryHandler(services_menu, pattern=r"^services_menu$"))
    app.add_handler(CallbackQueryHandler(service_selected, pattern=r"^service\|"))
    app.add_handler(CallbackQueryHandler(user_contest_info, pattern=r"^user_contest_info$"))

    app.add_handler(CallbackQueryHandler(admin_panel, pattern=r"^admin_panel$"))
    app.add_handler(CallbackQueryHandler(admin_stats, pattern=r"^admin_stats$"))
    app.add_handler(CallbackQueryHandler(admin_subscribers, pattern=r"^admin_subscribers$"))
    app.add_handler(CallbackQueryHandler(admin_sold_items, pattern=r"^admin_sold_items"))
    app.add_handler(CallbackQueryHandler(admin_user_messages, pattern=r"^admin_user_messages$"))
    app.add_handler(CallbackQueryHandler(admin_msg_detail, pattern=r"^admin_msg_detail\|"))
    app.add_handler(CallbackQueryHandler(admin_msg_read, pattern=r"^admin_msg_read\|"))
    app.add_handler(CallbackQueryHandler(admin_msg_read_all, pattern=r"^admin_msg_read_all$"))
    app.add_handler(CallbackQueryHandler(admin_contest_menu, pattern=r"^admin_contest$"))
    app.add_handler(CallbackQueryHandler(admin_contest_stop, pattern=r"^admin_contest_stop\|"))
    app.add_handler(CallbackQueryHandler(admin_services, pattern=r"^admin_services$"))
    app.add_handler(CallbackQueryHandler(admin_service_detail, pattern=r"^admin_svc\|"))
    app.add_handler(CallbackQueryHandler(admin_service_plan_detail, pattern=r"^admin_svcplan\|"))
    app.add_handler(CallbackQueryHandler(admin_svc_toggle, pattern=r"^admin_svc_toggle\|"))
    app.add_handler(CallbackQueryHandler(admin_svc_plan_toggle, pattern=r"^admin_svc_plantoggle\|"))
    app.add_handler(CallbackQueryHandler(admin_svc_delete_plan, pattern=r"^admin_svc_delplan\|"))
    app.add_handler(CallbackQueryHandler(admin_gemini_keys_menu, pattern=r"^admin_gemini_keys$"))
    app.add_handler(CallbackQueryHandler(admin_gemini_clear, pattern=r"^admin_gemini_clear$"))
    app.add_handler(CallbackQueryHandler(admin_list_skins, pattern=r"^admin_list_skins"))
    app.add_handler(CallbackQueryHandler(admin_skin_detail, pattern=r"^admin_skin_detail\|"))
    app.add_handler(CallbackQueryHandler(admin_delete_skin, pattern=r"^admin_delete_skin\|"))
    app.add_handler(CallbackQueryHandler(admin_orders, pattern=r"^admin_orders"))
    app.add_handler(CallbackQueryHandler(admin_order_detail, pattern=r"^admin_order_detail\|"))
    app.add_handler(CallbackQueryHandler(admin_manage_admins, pattern=r"^admin_manage_admins$"))
    app.add_handler(CallbackQueryHandler(admin_confirm_payment, pattern=r"^admin_confirm\|"))
    app.add_handler(CallbackQueryHandler(admin_reject_payment, pattern=r"^admin_reject\|"))
    app.add_handler(CallbackQueryHandler(user_skin_received, pattern=r"^user_skin_received\|"))

    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.Regex(r"steamcommunity\.com"),
        receive_steam_link
    ))

    return app


def main():
    import asyncio
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

    app = build_app()
    print("CS2 Shop Bot ishga tushdi...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK - CS2 Shop Bot is running")

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"Health server: http://0.0.0.0:{port}")
    main()
