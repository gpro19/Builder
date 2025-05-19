import logging
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackContext,
    Dispatcher,
    CallbackQueryHandler
)
import threading
import html
import re
from flask import Flask, request, jsonify
import os

app = Flask(__name__)

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Konfigurasi
TOKEN = os.getenv("TELEGRAM_TOKEN")  # Ambil token dari environment variable
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Contoh: https://yourdomain.com/webhook
ADMIN_CHAT_ID = 7117744807  # Ganti dengan chat ID admin

# Simpan data user sederhana (untuk demo)
user_db = {}

class BotManager:
    """Kelas untuk mengelola bot-bot yang dibuat"""
    def __init__(self):
        self.active_bots = {}  # {user_id: bot_instance}
    
    def create_bot(self, token: str, user_id: int):
        """Membuat dan menjalankan bot baru dengan webhook"""
        if user_id in self.active_bots:
            return False, "Anda sudah memiliki bot aktif"
        
        try:
            # Validasi token
            if not re.match(r'^\d{9,10}:[a-zA-Z0-9_-]{35}$', token):
                return False, "Format token tidak valid"
            
            # Buat bot baru
            new_bot = Bot(token)
            updater = Updater(token)
            
            # Daftarkan handler dasar
            dp = updater.dispatcher
            dp.add_handler(CommandHandler("start", self._new_bot_start))
            dp.add_handler(MessageHandler(Filters.text & ~Filters.command, self._new_bot_echo))
            
            # Set webhook untuk bot baru
            webhook_url = f"{WEBHOOK_URL}/{token}"  # Unique endpoint untuk setiap bot
            updater.bot.set_webhook(webhook_url)
            
            # Simpan referensi
            self.active_bots[user_id] = {
                'bot': new_bot,
                'updater': updater,
                'webhook_url': webhook_url
            }
            
            return True, "✅ Bot berhasil dibuat dan dijalankan!\n\n" \
                       "Username bot Anda: @" + new_bot.get_me().username
        except Exception as e:
            logger.error(f"Gagal membuat bot: {e}")
            return False, f"❌ Gagal membuat bot: {str(e)}"
    
    def _new_bot_start(self, update: Update, context: CallbackContext):
        """Handler command /start untuk bot yang dibuat"""
        update.message.reply_text(
            "👋 Hai! Saya adalah bot yang dibuat oleh Anon Builder.\n\n"
            "Gunakan /help untuk melihat fitur."
        )
    
    def _new_bot_echo(self, update: Update, context: CallbackContext):
        """Handler pesan untuk bot yang dibuat"""
        update.message.reply_text(f"Anda mengatakan: {update.message.text}")

# Inisialisasi bot manager
bot_manager = BotManager()

# Handler untuk bot utama
def start(update: Update, context: CallbackContext):
    """Handler command /start untuk bot utama"""
    user = update.effective_user
    nama = user.first_name
    if user.last_name:
        nama += ' ' + user.last_name
    
    pesan = (
        f"Hallo <b>{html.escape(nama)}</b>, saya adalah Anon Builder yang mempermudah kalian untuk membuat anon bot "
        "tanpa harus memiliki server sendiri. Silahkan klik tombol dibawah ini untuk memulainya"
    )
    
    keyboard = [
        [InlineKeyboardButton("📝 About", callback_data='bt_about')],
        [
            InlineKeyboardButton("🆘 Help", callback_data='bt_admin'),
            InlineKeyboardButton("🤖 Buat Bot", callback_data='bt_build')
        ],
        [InlineKeyboardButton("💬 Support", callback_data='bt_sp')]
    ]
    
    if update.message:
        update.message.reply_html(
            pesan,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        update.callback_query.edit_message_text(
            pesan,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

def handle_forwarded_message(update: Update, context: CallbackContext):
    """Handler untuk pesan yang diteruskan dari BotFather"""
    if (update.message.forward_from and 
        str(update.message.forward_from.id) == '93372553'):
        
        chat_id = update.effective_chat.id
        buatbot = user_db.get(f'addbot_{chat_id}')
        
        if buatbot:
            user = update.effective_user
            nama = user.first_name
            if user.last_name:
                nama += ' ' + user.last_name
            
            nama = html.escape(nama)
            dari = chat_id
            idnama = f'<a href="tg://user?id={dari}">{nama}</a>'
            
            # Kirim notifikasi ke admin
            context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"<b>Permintaan Bot Baru</b>\n"
                     f"<b>User:</b> {idnama}\n"
                     f"<b>ID:</b> {dari}\n"
                     f"<b>Token:</b> <code>{update.message.text}</code>",
                parse_mode='HTML',
                disable_web_page_preview=True
            )
            
            # Hapus status pembuatan bot
            user_db.pop(f'addbot_{chat_id}', None)
            
            # Ekstrak token dari pesan
            token = re.search(r'\d{9,10}:[a-zA-Z0-9_-]{35}', update.message.text)
            if token:
                token = token.group(0)
                # Buat bot baru
                success, message = bot_manager.create_bot(token, user.id)
                update.message.reply_html(
                    f"<i>🔄 Sedang membuat bot...</i>\n\n"
                    f"{message}",
                    reply_to_message_id=update.message.message_id
                )
            else:
                update.message.reply_text(
                    "❌ Token tidak ditemukan dalam pesan. Pastikan Anda meneruskan pesan lengkap dari @BotFather",
                    reply_to_message_id=update.message.message_id
                )

def button_handler(update: Update, context: CallbackContext):
    """Handler untuk semua tombol inline"""
    query = update.callback_query
    query.answer()
    
    if query.data == 'bt_build':
        # Set status pembuatan bot
        user_db[f'addbot_{query.message.chat.id}'] = True
        
        # Kirim instruksi
        pesan = (
            "📝 <b>Panduan Membuat Bot</b>\n\n"
            "1. Buka @BotFather dan kirim /newbot\n"
            "2. Ikuti instruksi untuk membuat bot baru\n"
            "3. Setelah mendapatkan token, <b>teruskan pesan lengkap dari @BotFather</b> ke saya"
        )
        
        keyboard = [
            [InlineKeyboardButton("🔙 Kembali", callback_data='bt_start')]
        ]
        
        query.edit_message_text(
            pesan,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif query.data == 'bt_about':
        pesan = (
            "🤖 <b>Anon Builder Bot</b>\n\n"
            "Anon Builder adalah bot yang dirancang khusus untuk memudahkan pembuatan bot Telegram.\n\n"
            "Dengan beberapa langkah sederhana, Anda bisa memiliki bot sendiri tanpa perlu:\n"
            "- Server pribadi\n"
            "- Pengetahuan pemrograman\n"
            "- Konfigurasi rumit\n\n"
            "Happy Building! 🚀"
        )
        keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data='bt_start')]]
        query.edit_message_text(pesan, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
    elif query.data == 'bt_admin':
        keyboard = [
            [
                InlineKeyboardButton("👮 Admin 1", url="tg://user?id=1910497806"),
                InlineKeyboardButton("👮 Admin 2", url="tg://user?id=6013163225")
            ],
            [InlineKeyboardButton("🔙 Kembali", callback_data='bt_start')]
        ]
        query.edit_message_text(
            "<b>📞 Kontak Admin</b>\n\n"
            "Hubungi admin jika Anda membutuhkan bantuan:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif query.data == 'bt_sp':
        user_db[f'support_{query.message.chat.id}'] = True
        keyboard = [[InlineKeyboardButton("❌ Batalkan", callback_data='bt_cancel')]]
        query.edit_message_text(
            "💬 <b>Mode Support</b>\n\n"
            "Silahkan kirim pesan Anda untuk admin support...",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif query.data == 'bt_cancel':
        user_db.pop(f'support_{query.message.chat.id}', None)
        query.delete_message()
        context.bot.send_message(
            chat_id=query.message.chat.id,
            text="❌ Permintaan dibatalkan"
        )
    elif query.data == 'bt_start':
        start(update, context)
        
        
# Flask Routes
@app.route('/')
def home():
    return "Anon Builder Bot is running!"

@app.route('/webhook', methods=['POST'])
def webhook():
    """Main webhook untuk bot utama"""
    update = Update.de_json(request.get_json(), bot_manager.active_bots[0]['bot'])
    dispatcher.process_update(update)
    return jsonify(success=True)

@app.route('/webhook/<token>', methods=['POST'])
def bot_webhook(token):
    """Webhook untuk bot-bot yang dibuat"""
    for user_id, bot_data in bot_manager.active_bots.items():
        if token in bot_data['webhook_url']:
            update = Update.de_json(request.get_json(), bot_data['bot'])
            bot_data['updater'].dispatcher.process_update(update)
            return jsonify(success=True)
    return jsonify(success=False, error="Bot not found"), 404

def setup_telegram_bot():
    """Setup bot utama dengan webhook"""
    updater = Updater(TOKEN)
    dp = updater.dispatcher
    
    # Register handlers
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(
        Filters.forwarded & Filters.chat_type.private,
        handle_forwarded_message
    ))
    dp.add_handler(CallbackQueryHandler(button_handler))
    
    # Set webhook
    updater.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    logger.info(f"Webhook set untuk bot utama: {WEBHOOK_URL}/webhook")
    
    return updater

if __name__ == '__main__':
    # Jalankan bot utama
    main_bot = setup_telegram_bot()
    
    # Jalankan Flask
    app.run(host='0.0.0.0', port=8000, ssl_context='adhoc')  # Gunakan SSL nyata di production
