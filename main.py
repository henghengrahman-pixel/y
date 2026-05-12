# MAIN.PY FINAL FIX 100%

```python
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ChatMemberHandler
)
from datetime import datetime
import pytz
import json
import os

TIMEZONE = pytz.timezone("Asia/Jakarta")

TOKEN = os.getenv("BOT_TOKEN", "").strip()

ADMIN_IDS = [
    int(x.strip())
    for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
]

GROUP_ID = int(os.getenv("GROUP_ID", "0"))

DATA_DIR = os.getenv("DATA_DIR", "/data")

os.makedirs(DATA_DIR, exist_ok=True)

MEMBER_FILE = os.path.join(DATA_DIR, "members.json")
ABSEN_FILE = os.path.join(DATA_DIR, "absensi.json")
GROUP_FILE = os.path.join(DATA_DIR, "groups.json")
SHIFT_FILE = os.path.join(DATA_DIR, "shift_history.json")

SHIFT_CONFIG = {
    "pagi": {
        "label": "SHIFT PAGI",
        "mulai_jam": 5,
        "mulai_menit": 0,
        "batas_jam": 6,
        "batas_menit": 15,
        "notif_jam": 6,
        "notif_menit": 45
    },
    "malam": {
        "label": "SHIFT MLM",
        "mulai_jam": 17,
        "mulai_menit": 0,
        "batas_jam": 18,
        "batas_menit": 15,
        "notif_jam": 18,
        "notif_menit": 45
    }
}

DENDA_PER_MENIT = 50000

members = {}
absensi = {}
allowed_groups = {}
shift_history = {}
last_notification = {}


def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default


def save_json(path, data):
    temp_path = f"{path}.tmp"

    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    os.replace(temp_path, path)


def load_data():
    global members
    global absensi
    global allowed_groups
    global shift_history

    members = load_json(MEMBER_FILE, {})
    absensi = load_json(ABSEN_FILE, {})
    allowed_groups = load_json(GROUP_FILE, {})
    shift_history = load_json(SHIFT_FILE, {})


def save_members():
    save_json(MEMBER_FILE, members)


def save_absensi():
    save_json(ABSEN_FILE, absensi)


def save_groups():
    save_json(GROUP_FILE, allowed_groups)


def save_shift_history():
    save_json(SHIFT_FILE, shift_history)


def get_today_key():
    return datetime.now(TIMEZONE).strftime("%Y-%m-%d")


def get_now_key():
    return datetime.now(TIMEZONE).strftime("%Y-%m-%d-%H-%M")


def ensure_today():
    today = get_today_key()

    if today not in absensi:
        absensi[today] = {
            "pagi": {},
            "malam": {}
        }

        save_absensi()

    return today


def rupiah(nominal):
    return f"Rp{int(nominal):,}".replace(",", ".")


def is_owner_admin(user_id):
    return user_id in ADMIN_IDS


def is_group_allowed(chat_id):
    if GROUP_ID != 0 and chat_id == GROUP_ID:
        return True

    return str(chat_id) in allowed_groups


async def kirim_admin(context, pesan):
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=pesan,
                parse_mode="Markdown"
            )
        except Exception:
            pass


async def is_group_admin(context, chat_id, user_id):
    try:
        member = await context.bot.get_chat_member(
            chat_id=chat_id,
            user_id=user_id
        )

        return member.status in ["administrator", "creator"]

    except Exception:
        return False


async def my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):

    event = update.my_chat_member

    if not event:
        return

    chat = event.chat
    from_user = event.from_user

    if chat.type not in ["group", "supergroup"]:
        return

    if event.new_chat_member.status in ["member", "administrator"]:

        if is_owner_admin(from_user.id):

            allowed_groups[str(chat.id)] = {
                "id": chat.id,
                "title": chat.title or "",
                "added_by": from_user.full_name
            }

            save_groups()

            await kirim_admin(
                context,
                (
                    f"✅ *BOT AKTIF DI GRUP*\n\n"
                    f"👥 Grup: {chat.title}\n"
                    f"🆔 ID: `{chat.id}`"
                )
            )

        else:

            await kirim_admin(
                context,
                (
                    f"🚨 *BOT DITAMBAHKAN OLEH NON ADMIN*\n\n"
                    f"👤 {from_user.full_name}\n"
                    f"🆔 `{from_user.id}`\n"
                    f"👥 {chat.title}\n\n"
                    f"Bot otomatis keluar dari grup."
                )
            )

            try:
                await context.bot.leave_chat(chat.id)
            except Exception:
                pass


async def track_member(update: Update):

    chat = update.effective_chat
    user = update.effective_user

    if not chat or not user:
        return

    if chat.type not in ["group", "supergroup"]:
        return

    members[str(user.id)] = {
        "id": user.id,
        "nama": user.full_name,
        "username": user.username or "",
        "group_id": chat.id,
        "group_name": chat.title or ""
    }

    save_members()


async def start_absensi(update: Update, context: ContextTypes.DEFAULT_TYPE):

    chat = update.effective_chat
    user = update.effective_user

    if not chat or not user:
        return

    if chat.type not in ["group", "supergroup"]:
        return await update.message.reply_text(
            "❌ Bot hanya bisa dipakai di grup."
        )

    if not is_group_allowed(chat.id):

        return await update.message.reply_text(
            "❌ Grup belum diizinkan."
        )

    admin_group = await is_group_admin(
        context,
        chat.id,
        user.id
    )

    if not admin_group:

        return await update.message.reply_text(
            "❌ Hanya admin grup yang bisa membuka absensi."
        )

    await track_member(update)

    keyboard = []

    user_shift = shift_history.get(str(user.id))

    if user_shift:

        if user_shift == "pagi":
            keyboard.append([
                InlineKeyboardButton(
                    "🌅 SHIFT PAGI",
                    callback_data="absen_pagi"
                )
            ])

        elif user_shift == "malam":
            keyboard.append([
                InlineKeyboardButton(
                    "🌙 SHIFT MLM",
                    callback_data="absen_malam"
                )
            ])

    else:

        keyboard = [
            [
                InlineKeyboardButton(
                    "🌅 SHIFT PAGI",
                    callback_data="absen_pagi"
                )
            ],
            [
                InlineKeyboardButton(
                    "🌙 SHIFT MLM",
                    callback_data="absen_malam"
                )
            ]
        ]

    text = (
        "📋 *SISTEM ABSENSI AKTIF*\n\n"

        "🌅 SHIFT PAGI\n"
        "• 05:00 - 06:15 WIB\n\n"

        "🌙 SHIFT MLM\n"
        "• 17:00 - 18:15 WIB\n\n"

        "⏰ Lewat batas dihitung telat\n"
        "💸 Rp50.000 / menit\n\n"

        "⚠️ Shift pertama yang dipilih akan menjadi shift tetap member."
    )

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_absen(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    if not query:
        return

    await query.answer()

    user = query.from_user
    chat = query.message.chat

    if not is_group_allowed(chat.id):

        return await query.message.reply_text(
            "❌ Grup belum diizinkan."
        )

    await track_member(update)

    shift = query.data.replace("absen_", "")

    if shift not in SHIFT_CONFIG:

        return await query.message.reply_text(
            "❌ Shift tidak valid."
        )

    saved_shift = shift_history.get(str(user.id))

    if saved_shift and saved_shift != shift:

        return await query.message.reply_text(
            (
                f"❌ Kamu terdaftar sebagai {SHIFT_CONFIG[saved_shift]['label']}.\n"
                f"Hubungi admin jika ingin pindah shift."
            )
        )

    if not saved_shift:

        shift_history[str(user.id)] = shift
        save_shift_history()

    now = datetime.now(TIMEZONE)

    config = SHIFT_CONFIG[shift]

    mulai = now.replace(
        hour=config["mulai_jam"],
        minute=config["mulai_menit"],
        second=0,
        microsecond=0
    )

    batas = now.replace(
        hour=config["batas_jam"],
        minute=config["batas_menit"],
        second=0,
        microsecond=0
    )

    if now < mulai:

        return await query.message.reply_text(
            (
                f"❌ Absensi belum dibuka.\n\n"
                f"Jam absensi:\n"
                f"{config['mulai_jam']:02d}:{config['mulai_menit']:02d}"
                f" - "
                f"{config['batas_jam']:02d}:{config['batas_menit']:02d} WIB"
            )
        )

    telat_menit = 0

    if now > batas:

        telat_menit = int(
            (now - batas).total_seconds() // 60
        )

        if telat_menit < 1:
            telat_menit = 1

    denda = telat_menit * DENDA_PER_MENIT

    today = ensure_today()

    absensi[today][shift][str(user.id)] = {
        "nama": user.full_name,
        "jam": now.strftime("%H:%M:%S"),
        "telat_menit": telat_menit,
        "denda": denda,
        "group_id": chat.id,
        "shift": shift
    }

    save_absensi()

    pesan = (
        f"✅ *ABSENSI BERHASIL*\n\n"
        f"👤 {user.full_name}\n"
        f"📌 {config['label']}\n"
        f"🕒 {now.strftime('%H:%M:%S')} WIB"
    )

    if telat_menit > 0:

        pesan += (
            f"\n\n⚠️ Telat {telat_menit} menit"
            f"\n💸 Denda {rupiah(denda)}"
        )

        admin_text = (
            f"🚨 *ABSENSI TELAT*\n\n"
            f"👥 Grup: {chat.title}\n"
            f"👤 Nama: {user.full_name}\n"
            f"📌 {config['label']}\n"
            f"🕒 {now.strftime('%H:%M:%S')} WIB\n"
            f"⏰ Telat: {telat_menit} menit\n"
            f"💸 Denda: {rupiah(denda)}"
        )

        await kirim_admin(
            context,
            admin_text
        )

    await query.message.reply_text(
        pesan,
        parse_mode="Markdown"
    )


async def cek_absensi(context: ContextTypes.DEFAULT_TYPE):

    now = datetime.now(TIMEZONE)

    today = ensure_today()

    now_key = get_now_key()

    for shift, config in SHIFT_CONFIG.items():

        notif_key = f"{today}-{shift}-{config['notif_jam']}-{config['notif_menit']}"

        if notif_key in last_notification:
            continue

        if (
            now.hour == config["notif_jam"]
            and
            now.minute == config["notif_menit"]
        ):

            data_shift = absensi[today][shift]

            belum_absen = []

            for uid, member_shift in shift_history.items():

                if member_shift != shift:
                    continue

                if uid not in data_shift:

                    nama = members.get(uid, {}).get("nama", uid)

                    belum_absen.append(
                        f"• {nama}"
                    )

            if belum_absen:

                pesan = (
                    f"🚨 *{config['label']} YANG BELUM ABSENSI*\n\n"
                    + "\n".join(belum_absen)
                )

            else:

                pesan = (
                    f"✅ *SEMUAH MEMBER {config['label']} SUDAH ABSENSI*"
                )

            await kirim_admin(
                context,
                pesan
            )

            last_notification[notif_key] = now_key


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    if not user:
        return

    if not is_owner_admin(user.id):
        return

    today = ensure_today()

    text = "📋 *STATUS ABSENSI HARI INI*\n\n"

    for shift, config in SHIFT_CONFIG.items():

        text += f"📌 {config['label']}\n"

        data = absensi[today][shift]

        if not data:

            text += "Belum ada absensi.\n\n"
            continue

        for uid, item in data.items():

            text += (
                f"👤 {item['nama']}\n"
                f"🕒 {item['jam']}\n"
            )

            if item["telat_menit"] > 0:

                text += (
                    f"⚠️ Telat {item['telat_menit']} menit\n"
                    f"💸 {rupiah(item['denda'])}\n"
                )

            text += "\n"

    await update.message.reply_text(
        text,
        parse_mode="Markdown"
    )


def main():

    if not TOKEN:
        raise RuntimeError(
            "BOT_TOKEN belum diisi di Railway Variables"
        )

    if not ADMIN_IDS:
        raise RuntimeError(
            "ADMIN_IDS belum diisi di Railway Variables"
        )

    load_data()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(
        ChatMemberHandler(
            my_chat_member,
            ChatMemberHandler.MY_CHAT_MEMBER
        )
    )

    app.add_handler(
        CommandHandler("start", start_absensi)
    )

    app.add_handler(
        CommandHandler("status", status)
    )

    app.add_handler(
        CallbackQueryHandler(
            handle_absen,
            pattern="^absen_"
        )
    )

    app.job_queue.run_repeating(
        cek_absensi,
        interval=60,
        first=15
    )

    print("BOT ABSENSI AKTIF")

    app.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
```
