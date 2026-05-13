from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ChatMemberHandler,
    MessageHandler,
    filters
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
NOTIF_FILE = os.path.join(DATA_DIR, "notification_history.json")

SHIFT_CONFIG = {
    "jam_6_pagi": {
        "label": "SHIFT JAM 6 PAGI",
        "button": "🌅 SHIFT JAM 6 PAGI",
        "mulai_jam": 5,
        "mulai_menit": 0,
        "batas_jam": 6,
        "batas_menit": 15,
        "notif_jam": 6,
        "notif_menit": 30
    },

    "jam_11_siang": {
        "label": "SHIFT JAM 11 SIANG",
        "button": "☀️ SHIFT JAM 11 SIANG",
        "mulai_jam": 10,
        "mulai_menit": 0,
        "batas_jam": 11,
        "batas_menit": 15,
        "notif_jam": 11,
        "notif_menit": 30
    },

    "jam_6_sore": {
        "label": "SHIFT JAM 6 SORE",
        "button": "🌙 SHIFT JAM 6 SORE",
        "mulai_jam": 17,
        "mulai_menit": 0,
        "batas_jam": 18,
        "batas_menit": 15,
        "notif_jam": 18,
        "notif_menit": 30
    },

    "jam_11_malam": {
        "label": "SHIFT JAM 11 MALAM",
        "button": "🌌 SHIFT JAM 11 MALAM",
        "mulai_jam": 22,
        "mulai_menit": 0,
        "batas_jam": 23,
        "batas_menit": 15,
        "notif_jam": 23,
        "notif_menit": 30
    }
}

DENDA_PER_MENIT = 50000

members = {}
absensi = {}
allowed_groups = {}
shift_history = {}
notification_history = {}


def load_json(path, default):

    if os.path.exists(path):

        try:

            with open(path, "r", encoding="utf-8") as file:
                return json.load(file)

        except Exception:
            return default

    return default


def save_json(path, data):

    temp_path = f"{path}.tmp"

    with open(temp_path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)

    os.replace(temp_path, path)


def load_data():

    global members
    global absensi
    global allowed_groups
    global shift_history
    global notification_history

    members = load_json(MEMBER_FILE, {})
    absensi = load_json(ABSEN_FILE, {})
    allowed_groups = load_json(GROUP_FILE, {})
    shift_history = load_json(SHIFT_FILE, {})
    notification_history = load_json(NOTIF_FILE, {})


def save_members():
    save_json(MEMBER_FILE, members)


def save_absensi():
    save_json(ABSEN_FILE, absensi)


def save_groups():
    save_json(GROUP_FILE, allowed_groups)


def save_shift_history():
    save_json(SHIFT_FILE, shift_history)


def save_notification_history():
    save_json(NOTIF_FILE, notification_history)


def get_today_key():
    return datetime.now(TIMEZONE).strftime("%Y-%m-%d")


def ensure_today():

    today = get_today_key()

    if today not in absensi:

        absensi[today] = {}

        for shift_key in SHIFT_CONFIG.keys():
            absensi[today][shift_key] = {}

        save_absensi()

    if today not in notification_history:

        notification_history[today] = {}

        save_notification_history()

    return today


def rupiah(nominal):
    return f"Rp{int(nominal):,}".replace(",", ".")


def is_owner_admin(user_id):
    return user_id in ADMIN_IDS


def is_group_allowed(chat_id):

    if GROUP_ID != 0 and chat_id == GROUP_ID:
        return True

    return str(chat_id) in allowed_groups


def shift_time_text(shift):

    config = SHIFT_CONFIG[shift]

    return (
        f"{config['mulai_jam']:02d}:{config['mulai_menit']:02d}"
        f" - "
        f"{config['batas_jam']:02d}:{config['batas_menit']:02d} WIB"
    )


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


async def my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):

    event = update.my_chat_member

    if not event:
        return

    chat = event.chat
    from_user = event.from_user

    if chat.type not in ["group", "supergroup"]:
        return

    new_status = event.new_chat_member.status

    if new_status in ["member", "administrator"]:

        if is_owner_admin(from_user.id):

            allowed_groups[str(chat.id)] = {
                "id": chat.id,
                "title": chat.title or "",
                "added_by_id": from_user.id,
                "added_by_name": from_user.full_name,
                "created_at": datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")
            }

            save_groups()

            await kirim_admin(
                context,
                (
                    "✅ *BOT ABSENSI BERHASIL DIAKTIFKAN*\n\n"
                    f"👥 Grup: {chat.title or '-'}\n"
                    f"🆔 Group ID: `{chat.id}`\n"
                    f"👤 Ditambahkan oleh: {from_user.full_name}"
                )
            )

        else:

            await kirim_admin(
                context,
                (
                    "🚨 *BOT DITAMBAHKAN OLEH NON ADMIN UTAMA*\n\n"
                    f"👥 Grup: {chat.title or '-'}\n"
                    f"🆔 Group ID: `{chat.id}`\n"
                    f"👤 Oleh: {from_user.full_name}\n"
                    f"🆔 User ID: `{from_user.id}`\n\n"
                    "Bot otomatis keluar dari grup."
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

    if not is_group_allowed(chat.id):
        return

    members[str(user.id)] = {
        "id": user.id,
        "nama": user.full_name,
        "username": user.username or "",
        "group_id": chat.id,
        "group_name": chat.title or "",
        "last_seen": datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")
    }

    save_members()


async def start_absensi(update: Update, context: ContextTypes.DEFAULT_TYPE):

    chat = update.effective_chat
    user = update.effective_user

    if not chat or not user:
        return

    if chat.type not in ["group", "supergroup"]:

        return await update.message.reply_text(
            "❌ Bot absensi hanya bisa digunakan di grup."
        )

    if not is_group_allowed(chat.id):

        await kirim_admin(
            context,
            (
                "🚨 *AKSES GRUP DITOLAK*\n\n"
                f"👥 Grup: {chat.title or '-'}\n"
                f"🆔 Group ID: `{chat.id}`\n"
                f"👤 User: {user.full_name}"
            )
        )

        return await update.message.reply_text(
            "❌ Grup belum terdaftar dalam sistem."
        )

    await track_member(update)

    user_shift = shift_history.get(str(user.id))

    if user_shift:

        config = SHIFT_CONFIG[user_shift]

        keyboard = [
            [
                InlineKeyboardButton(
                    config["button"],
                    callback_data=f"absen_{user_shift}"
                )
            ]
        ]

    else:

        keyboard = [
            [
                InlineKeyboardButton(
                    SHIFT_CONFIG["jam_6_pagi"]["button"],
                    callback_data="absen_jam_6_pagi"
                )
            ],

            [
                InlineKeyboardButton(
                    SHIFT_CONFIG["jam_11_siang"]["button"],
                    callback_data="absen_jam_11_siang"
                )
            ],

            [
                InlineKeyboardButton(
                    SHIFT_CONFIG["jam_6_sore"]["button"],
                    callback_data="absen_jam_6_sore"
                )
            ],

            [
                InlineKeyboardButton(
                    SHIFT_CONFIG["jam_11_malam"]["button"],
                    callback_data="absen_jam_11_malam"
                )
            ]
        ]

    text = (
        "📋 *SISTEM ABSENSI STAFF AKTIF*\n\n"

        "🕘 *JADWAL ABSENSI STAFF*\n\n"

        "🌅 *SHIFT JAM 6 PAGI*\n"
        f"• {shift_time_text('jam_6_pagi')}\n\n"

        "☀️ *SHIFT JAM 11 SIANG*\n"
        f"• {shift_time_text('jam_11_siang')}\n\n"

        "🌙 *SHIFT JAM 6 SORE*\n"
        f"• {shift_time_text('jam_6_sore')}\n\n"

        "🌌 *SHIFT JAM 11 MALAM*\n"
        f"• {shift_time_text('jam_11_malam')}\n\n"

        "⏰ Keterlambatan absensi dihitung otomatis oleh sistem.\n"
        f"💸 Denda keterlambatan: {rupiah(DENDA_PER_MENIT)} per menit.\n\n"

        "⚠️ Shift yang dipilih pertama kali akan menjadi shift tetap staff.\n"
        "👨‍💼 Hubungi admin grup apabila ingin melakukan pergantian shift."
    )

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_absen(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    if not query or not query.message:
        return

    await query.answer()

    user = query.from_user
    chat = query.message.chat

    if chat.type not in ["group", "supergroup"]:

        return await query.message.reply_text(
            "❌ Absensi hanya bisa dilakukan di grup."
        )

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
                f"❌ Kamu terdaftar pada "
                f"{SHIFT_CONFIG[saved_shift]['label']}.\n"
                "Hubungi admin untuk pergantian shift."
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
                f"❌ Absensi {config['label']} belum dibuka.\n\n"
                f"🕘 Jadwal: {shift_time_text(shift)}"
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

    if str(user.id) in absensi[today][shift]:

        data_lama = absensi[today][shift][str(user.id)]

        return await query.message.reply_text(
            (
                "✅ Kamu sudah melakukan absensi hari ini.\n\n"
                f"👤 Staff: {user.full_name}\n"
                f"📌 Shift: {config['label']}\n"
                f"🕘 Jam Absensi: {data_lama.get('jam', '-')}"
            )
        )

    absensi[today][shift][str(user.id)] = {
        "id": user.id,
        "nama": user.full_name,
        "username": user.username or "",
        "jam": now.strftime("%H:%M:%S"),
        "telat_menit": telat_menit,
        "denda": denda,
        "group_id": chat.id,
        "group_name": chat.title or "",
        "shift": shift
    }

    save_absensi()

    pesan = (
        "✅ *ABSENSI BERHASIL*\n\n"
        f"👤 Staff: {user.full_name}\n"
        f"📌 Shift: {config['label']}\n"
        f"🕘 Jam Absensi: {now.strftime('%H:%M:%S')} WIB"
    )

    if telat_menit > 0:

        pesan += (
            f"\n\n⚠️ Keterlambatan: {telat_menit} menit"
            f"\n💸 Denda: {rupiah(denda)}"
        )

    await query.message.reply_text(
        pesan,
        parse_mode="Markdown"
    )


async def cek_absensi(context: ContextTypes.DEFAULT_TYPE):

    now = datetime.now(TIMEZONE)

    today = ensure_today()

    for shift, config in SHIFT_CONFIG.items():

        notif_key = (
            f"{today}-{shift}-"
            f"{config['notif_jam']:02d}"
            f"{config['notif_menit']:02d}"
        )

        if notification_history.get(today, {}).get(notif_key):
            continue

        if (
            now.hour == config["notif_jam"]
            and now.minute == config["notif_menit"]
        ):

            data_shift = absensi[today].get(shift, {})

            belum_absen = []

            for uid, member_shift in shift_history.items():

                if member_shift != shift:
                    continue

                if uid not in data_shift:

                    nama = members.get(uid, {}).get("nama", uid)

                    belum_absen.append(f"• {nama}")

            if belum_absen:

                pesan = (
                    f"🚨 *STAFF BELUM ABSENSI*\n\n"
                    f"📌 {config['label']}\n\n"
                    + "\n".join(belum_absen)
                )

            else:

                pesan = (
                    f"✅ Semua staff "
                    f"{config['label']} sudah absensi."
                )

            await kirim_admin(context, pesan)

            notification_history.setdefault(today, {})
            notification_history[today][notif_key] = True

            save_notification_history()


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    if not user or not is_owner_admin(user.id):
        return

    today = ensure_today()

    text = "📋 *STATUS ABSENSI HARI INI*\n\n"

    for shift, config in SHIFT_CONFIG.items():

        text += f"{config['button']}\n"

        data = absensi[today].get(shift, {})

        if not data:

            text += "Belum ada absensi.\n\n"

            continue

        for item in data.values():

            text += (
                f"👤 {item.get('nama', '-')}\n"
                f"🕘 {item.get('jam', '-')}\n"
            )

            telat = int(item.get("telat_menit", 0))
            denda = int(item.get("denda", 0))

            if telat > 0:

                text += (
                    f"⚠️ Telat {telat} menit\n"
                    f"💸 {rupiah(denda)}\n"
                )

            text += "\n"

    await update.message.reply_text(
        text,
        parse_mode="Markdown"
    )


async def list_shift(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    if not user or not is_owner_admin(user.id):
        return

    if not shift_history:

        return await update.message.reply_text(
            "Belum ada data shift staff."
        )

    hasil = "📋 *DATA SHIFT STAFF*\n\n"

    for shift_key, config in SHIFT_CONFIG.items():

        hasil += f"{config['button']}\n"

        daftar = []

        for uid, shift in shift_history.items():

            if shift == shift_key:

                nama = members.get(uid, {}).get("nama", uid)

                daftar.append(f"• {nama}")

        hasil += (
            "\n".join(daftar)
            if daftar else
            "-"
        )

        hasil += "\n\n"

    await update.message.reply_text(
        hasil,
        parse_mode="Markdown"
    )


async def reset_shift(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    if not user or not is_owner_admin(user.id):
        return

    if not update.message.reply_to_message:

        return await update.message.reply_text(
            (
                "Reply pesan staff lalu gunakan:\n\n"
                "/resetshift jam_6_pagi\n"
                "/resetshift jam_11_siang\n"
                "/resetshift jam_6_sore\n"
                "/resetshift jam_11_malam"
            )
        )

    if len(context.args) < 1:

        return await update.message.reply_text(
            (
                "Masukkan shift baru.\n\n"
                "Contoh:\n"
                "/resetshift jam_6_sore"
            )
        )

    new_shift = context.args[0].lower()

    if new_shift not in SHIFT_CONFIG:

        return await update.message.reply_text(
            "❌ Shift tidak valid."
        )

    target = update.message.reply_to_message.from_user

    old_shift = shift_history.get(str(target.id), "-")

    shift_history[str(target.id)] = new_shift

    save_shift_history()

    old_label = (
        SHIFT_CONFIG[old_shift]["label"]
        if old_shift in SHIFT_CONFIG
        else "BELUM ADA"
    )

    await update.message.reply_text(
        (
            "✅ *PERGANTIAN SHIFT BERHASIL*\n\n"
            f"👤 Staff: {target.full_name}\n"
            f"📌 Shift Lama: {old_label}\n"
            f"📌 Shift Baru: {SHIFT_CONFIG[new_shift]['label']}"
        ),
        parse_mode="Markdown"
    )


async def id_grup(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user
    chat = update.effective_chat

    if not user or not is_owner_admin(user.id):
        return

    await update.message.reply_text(
        (
            f"👥 Nama Grup: {chat.title or '-'}\n"
            f"🆔 Group ID: {chat.id}"
        )
    )


async def track_all_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await track_member(update)


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
        CommandHandler("listshift", list_shift)
    )

    app.add_handler(
        CommandHandler("resetshift", reset_shift)
    )

    app.add_handler(
        CommandHandler("idgrup", id_grup)
    )

    app.add_handler(
        CallbackQueryHandler(
            handle_absen,
            pattern="^absen_"
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & (~filters.COMMAND),
            track_all_message
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
