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

TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = [
    int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
]

GROUP_ID = int(os.getenv("GROUP_ID", "0"))

DATA_DIR = os.getenv("DATA_DIR", "data")
os.makedirs(DATA_DIR, exist_ok=True)

MEMBER_FILE = os.path.join(DATA_DIR, "members.json")
ABSEN_FILE = os.path.join(DATA_DIR, "absensi.json")

SHIFT_CONFIG = {
    "pagi": {
        "jam": 6,
        "menit": 15
    },
    "malam": {
        "jam": 18,
        "menit": 15
    }
}

DENDA_PER_MENIT = 50000

members = {}
absensi = {}

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except:
            return default
    return default

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def load_data():
    global members, absensi
    members = load_json(MEMBER_FILE, {})
    absensi = load_json(ABSEN_FILE, {})

def save_members():
    save_json(MEMBER_FILE, members)

def save_absensi():
    save_json(ABSEN_FILE, absensi)

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

def get_today_key():
    return datetime.now(TIMEZONE).strftime("%Y-%m-%d")

def ensure_today():
    key = get_today_key()
    if key not in absensi:
        absensi[key] = {
            "pagi": {},
            "malam": {}
        }
    return key

async def track_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ["group", "supergroup"]:
        return

    user = update.effective_user

    members[str(user.id)] = {
        "id": user.id,
        "nama": user.full_name
    }

    save_members()

async def start_absensi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ["group", "supergroup"]:
        return await update.message.reply_text(
            "Bot hanya bisa digunakan di grup."
        )

    await track_member(update, context)

    keyboard = [
        [
            InlineKeyboardButton("🌅 SHIFT PAGI", callback_data="absen_pagi")
        ],
        [
            InlineKeyboardButton("🌙 SHIFT MALAM", callback_data="absen_malam")
        ]
    ]

    teks = (
        "📋 *SISTEM ABSENSI AKTIF*\n\n"
        "Silakan pilih shift:\n"
        "• Shift Pagi 06:15 WIB\n"
        "• Shift Malam 18:15 WIB\n\n"
        "Terlambat dihitung Rp50.000 / menit."
    )

    await update.message.reply_text(
        teks,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_absen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user

    members[str(user.id)] = {
        "id": user.id,
        "nama": user.full_name
    }
    save_members()

    shift = query.data.replace("absen_", "")

    now = datetime.now(TIMEZONE)

    config = SHIFT_CONFIG[shift]

    batas = now.replace(
        hour=config["jam"],
        minute=config["menit"],
        second=0,
        microsecond=0
    )

    telat_menit = 0

    if now > batas:
        selisih = int((now - batas).total_seconds() // 60)
        telat_menit = max(1, selisih)

    denda = telat_menit * DENDA_PER_MENIT

    today = ensure_today()

    absensi[today][shift][str(user.id)] = {
        "nama": user.full_name,
        "jam": now.strftime("%H:%M:%S"),
        "telat_menit": telat_menit,
        "denda": denda
    }

    save_absensi()

    pesan = (
        f"✅ *ABSENSI BERHASIL*\n\n"
        f"👤 Nama: {user.full_name}\n"
        f"🕒 Jam: {now.strftime('%H:%M:%S')} WIB\n"
        f"📌 Shift: {shift.upper()}"
    )

    if telat_menit > 0:
        pesan += (
            f"\n⚠️ Telat: {telat_menit} menit\n"
            f"💸 Denda: Rp{denda:,}"
        )

        admin_pesan = (
            f"🚨 *ABSENSI TELAT*\n\n"
            f"👤 Nama: {user.full_name}\n"
            f"📌 Shift: {shift.upper()}\n"
            f"🕒 Jam Absen: {now.strftime('%H:%M:%S')} WIB\n"
            f"⏰ Telat: {telat_menit} menit\n"
            f"💸 Denda: Rp{denda:,}"
        )

        await kirim_admin(context, admin_pesan)

    await query.message.reply_text(
        pesan,
        parse_mode="Markdown"
    )

async def cek_absensi(context: ContextTypes.DEFAULT_TYPE):
    if GROUP_ID == 0:
        return

    now = datetime.now(TIMEZONE)

    today = ensure_today()

    checks = [
        {
            "shift": "pagi",
            "jam": 6,
            "menit": 25
        },
        {
            "shift": "malam",
            "jam": 18,
            "menit": 25
        }
    ]

    for item in checks:
        if now.hour == item["jam"] and now.minute == item["menit"]:
            belum_absen = []

            data_shift = absensi[today][item["shift"]]

            for uid, member in members.items():
                if uid not in data_shift:
                    belum_absen.append(f"• {member['nama']}")

            if belum_absen:
                pesan = (
                    f"🚨 *BELUM ABSENSI SHIFT {item['shift'].upper()}*\n\n"
                    + "\n".join(belum_absen)
                )

                await kirim_admin(context, pesan)

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return

    today = ensure_today()

    teks = "📋 *STATUS ABSENSI HARI INI*\n\n"

    for shift in ["pagi", "malam"]:
        teks += f"📌 SHIFT {shift.upper()}\n"

        data = absensi[today][shift]

        if not data:
            teks += "Belum ada absensi.\n\n"
            continue

        for uid, item in data.items():
            teks += (
                f"👤 {item['nama']}\n"
                f"🕒 {item['jam']}\n"
            )

            if item["telat_menit"] > 0:
                teks += (
                    f"⚠️ Telat {item['telat_menit']} menit\n"
                    f"💸 Rp{item['denda']:,}\n"
                )

            teks += "\n"

    await update.message.reply_text(
        teks,
        parse_mode="Markdown"
    )

def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN belum diisi di Railway Variables")

    if not ADMIN_IDS:
        raise RuntimeError("ADMIN_IDS belum diisi di Railway Variables")

    load_data()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start_absensi))
    app.add_handler(CommandHandler("status", status))

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

    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
