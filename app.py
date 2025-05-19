import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackContext,
    CallbackQueryHandler
)
import html
import re
from flask import Flask, request, jsonify
import os

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
MAIN_ADMIN_ID = 7117744807
LOG_CHANNEL = 6172467461

# Simple database
user_db = {}

class AnonymousBot:
    def __init__(self, token: str, creator_id: int):
        """Initialize an anonymous messaging bot"""
        self.token = token
        self.creator_id = creator_id
        self.updater = Updater(token, use_context=True)
        self.dispatcher = self.updater.dispatcher
        self.username = self.updater.bot.get_me().username
        
        # Register handlers
        self._register_handlers()
        
        # Set webhook
        webhook_url = f"{WEBHOOK_URL}/webhook/{token}"
        self.updater.bot.set_webhook(webhook_url)
        logger.info(f"Webhook set for bot @{self.username} to {webhook_url}")

    def _register_handlers(self):
        """Register all handlers for the bot"""
        self.dispatcher.add_handler(CommandHandler("start", self.start))
        self.dispatcher.add_handler(CommandHandler("settings", self.settings))
        self.dispatcher.add_handler(CallbackQueryHandler(self.button_handler))
        self.dispatcher.add_handler(MessageHandler(Filters.all & ~Filters.command, self.message_handler))

    def start(self, update: Update, context: CallbackContext):
        """Handle /start command"""
        user = update.effective_user
        
        # Set commands for admin
        if user.id == self.creator_id:
            context.bot.set_my_commands([
                ("start", "Mulai Bot"),
                ("settings", "Pengaturan Bot")
            ])
        
        # Check force subscription
        if not self._check_subscription(update, context):
            return
        
        # Send welcome message
        welcome_text = user_db.get(f'startText_{self.username}', 
                                 "Halo! Selamat datang di bot menfes anonim.")
        update.message.reply_text(welcome_text)

    def _check_subscription(self, update: Update, context: CallbackContext) -> bool:
        """Check if user is subscribed to required channel"""
        channel_id = user_db.get(f'channel_{self.username}')
        if user_db.get(f'fsub_{self.username}') == 'iya' and channel_id:
            try:
                member = context.bot.get_chat_member(channel_id, update.effective_user.id)
                if member.status in ['left', 'kicked']:
                    channel_info = context.bot.get_chat(channel_id)
                    keyboard = [[InlineKeyboardButton("Join Channel", url=f"https://t.me/{channel_info.username}")]]
                    update.message.reply_text(
                        "🔗 <b>Anda harus join channel dulu</b>\n\nSetelah join, ketik /start lagi",
                        parse_mode='HTML',
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                    return False
            except Exception as e:
                logger.error(f"Error checking channel membership: {e}")
                update.message.reply_text("❌ Gagal memverifikasi keanggotaan channel.")
                return False
        return True

    def settings(self, update: Update, context: CallbackContext):
        """Handle /settings command (admin only)"""
        if update.effective_user.id != self.creator_id:
            update.message.reply_text("❌ Hanya admin yang bisa mengakses pengaturan.")
            return
        
        # Get current settings
        welcome_text = user_db.get(f'startText_{self.username}', "Default welcome text")
        auto_reply = user_db.get(f'kirimText_{self.username}', "Default auto reply")
        channel = user_db.get(f'channel_{self.username}')
        
        keyboard = [
            [InlineKeyboardButton("📝 Set Pesan Welcome", callback_data='st_start')],
            [InlineKeyboardButton("📩 Set Pesan Auto Reply", callback_data='st_kirim')],
            [InlineKeyboardButton("📢 Set Channel", callback_data='st_channel' if not channel else 'st_anon')],
            [InlineKeyboardButton("⏱️ Set Waktu Hapus", callback_data='st_del')],
            [InlineKeyboardButton("⏸️ Set Mode Jeda", callback_data='st_jeda')],
            [InlineKeyboardButton("🔗 Set Force Sub", callback_data='st_fsub')],
            [InlineKeyboardButton("✉️ Set Mode Kirim", callback_data='mode_All')]
        ]
        
        settings_text = (
            f"⚙️ <b>Pengaturan Bot @{self.username}</b>\n\n"
            f"📝 Pesan Welcome: <code>{html.escape(welcome_text[:50])}...</code>\n"
            f"📩 Auto Reply: <code>{html.escape(auto_reply[:50])}...</code>\n"
            f"📢 Channel: <code>{channel if channel else 'Tidak terhubung'}</code>\n\n"
            "Pilih opsi pengaturan:"
        )
        
        update.message.reply_text(
            settings_text,
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
            self._handle_settings(query)
        elif query.data.startswith('mode_'):
            self._handle_mode_settings(query)
        elif query.data.startswith('jeda_'):
            self._handle_pause_settings(query)
        elif query.data.startswith('fsub_'):
            self._handle_fsub_settings(query)
        elif query.data.startswith('del_'):
            self._handle_delete_settings(query)

    def _handle_settings(self, query):
        """Handle settings menu actions"""
        data = query.data
        bot_username = self.username
        
        if data == 'st_start':
            current_text = user_db.get(f'startText_{bot_username}', "Default welcome text")
            query.edit_message_text(
                f"📝 <b>Set Pesan Welcome</b>\n\nPesan saat ini:\n<code>{html.escape(current_text)}</code>\n\n"
                "Kirim pesan baru untuk mengganti:",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Kembali", callback_data='bt_start')]])
            )
            user_db[f'editing_{bot_username}'] = 'start_text'
        
        elif data == 'st_kirim':
            current_text = user_db.get(f'kirimText_{bot_username}', "Default auto reply")
            query.edit_message_text(
                f"📩 <b>Set Pesan Auto Reply</b>\n\nPesan saat ini:\n<code>{html.escape(current_text)}</code>\n\n"
                "Kirim pesan baru untuk mengganti:",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Kembali", callback_data='bt_start')]])
            )
            user_db[f'editing_{bot_username}'] = 'auto_reply'
        
        elif data == 'st_channel':
            query.edit_message_text(
                f"📢 <b>Connect Channel</b>\n\n"
                f"1. Tambahkan @{bot_username} ke channel Anda sebagai admin\n"
                f"2. Kirim /setchanneluser di channel Anda\n"
                f"3. Teruskan pesan tersebut ke bot ini",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Kembali", callback_data='bt_start')]])
            )
            user_db[f'editing_{bot_username}'] = 'connect_channel'
        
        elif data == 'st_anon':
            channel_id = user_db.get(f'channel_{bot_username}')
            try:
                channel_info = self.updater.bot.get_chat(channel_id)
                channel_name = channel_info.title
                channel_link = f"t.me/{channel_info.username}" if channel_info.username else f"ID: {channel_id}"
            except Exception:
                channel_name = "Unknown Channel"
                channel_link = f"ID: {channel_id}"
            
            query.edit_message_text(
                f"📢 <b>Channel Settings</b>\n\n"
                f"Terhubung dengan:\n{channel_name}\n{channel_link}",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("❌ Putuskan Channel", callback_data='st_putus')],
                    [InlineKeyboardButton("🔙 Kembali", callback_data='bt_start')]
                ])
            )
        
        elif data == 'st_putus':
            user_db.pop(f'channel_{bot_username}', None)
            query.edit_message_text(
                "✅ Channel berhasil diputuskan",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Kembali", callback_data='bt_start')]])
            )

    def _handle_mode_settings(self, query):
        """Handle message mode settings (text, photo, document, sticker)"""
        mode_type = query.data.split('_')[1] if '_' in query.data else 'All'
        bot_username = self.username
        
        if mode_type != 'All':
            # Toggle the specific mode
            current_setting = user_db.get(f'mode{mode_type}_{bot_username}', False)
            user_db[f'mode{mode_type}_{bot_username}'] = not current_setting
        
        # Prepare mode names for display
        mode_status = {
            'Text': "✅" if not user_db.get(f'modeText_{bot_username}') else "❌",
            'Foto': "✅" if not user_db.get(f'modeFoto_{bot_username}') else "❌",
            'Berkas': "✅" if not user_db.get(f'modeBerkas_{bot_username}') else "❌",
            'Sticker': "✅" if not user_db.get(f'modeSticker_{bot_username}') else "❌"
        }
        
        # Update the message
        query.edit_message_text(
            "✉️ <b>Pengaturan Mode Kirim</b>\n\n"
            "Pilih jenis pesan yang ingin diubah:\n\n"
            f"Teks {mode_status['Text']}\n"
            f"Foto {mode_status['Foto']}\n"
            f"Dokumen {mode_status['Berkas']}\n"
            f"Stiker {mode_status['Sticker']}",
            parse_mode='HTML',
            reply_markup=self._create_mode_settings_keyboard()
        )

    def _create_mode_settings_keyboard(self):
        """Create keyboard for mode settings"""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Teks", callback_data='mode_Text'),
                InlineKeyboardButton("Foto", callback_data='mode_Foto')
            ],
            [
                InlineKeyboardButton("Dokumen", callback_data='mode_Berkas'),
                InlineKeyboardButton("Stiker", callback_data='mode_Sticker')
            ],
            [InlineKeyboardButton("🔙 Kembali", callback_data='bt_start')]
        ])

    def _handle_pause_settings(self, query):
        """Handle pause mode settings"""
        action = query.data.split('_')[1]
        bot_username = self.username
        
        if action == 'on':
            user_db[f'jeda_{bot_username}'] = 'iya'
            status = "⏸️ DIJEDA"
        else:
            user_db[f'jeda_{bot_username}'] = 'tidak'
            status = "▶️ DIAKTIFKAN"
        
        query.edit_message_text(
            f"⏸️ <b>Mode Jeda</b>\n\nStatus bot: {status}\n\n"
            "Pilih aksi:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("⏸️ Jeda Bot", callback_data='jeda_on'),
                    InlineKeyboardButton("▶️ Aktifkan Bot", callback_data='jeda_off')
                ],
                [InlineKeyboardButton("🔙 Kembali", callback_data='bt_start')]
            ])
        )

    def _handle_fsub_settings(self, query):
        """Handle force subscription settings"""
        action = query.data.split('_')[1]
        bot_username = self.username
        
        if action == 'on':
            user_db[f'fsub_{bot_username}'] = 'iya'
            status = "🔗 AKTIF"
        else:
            user_db[f'fsub_{bot_username}'] = 'tidak'
            status = "🚫 NONAKTIF"
        
        query.edit_message_text(
            f"🔗 <b>Force Subscription</b>\n\nStatus: {status}\n\n"
            "Pilih aksi:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🔗 Aktifkan", callback_data='fsub_on'),
                    InlineKeyboardButton("🚫 Nonaktifkan", callback_data='fsub_off')
                ],
                [InlineKeyboardButton("🔙 Kembali", callback_data='bt_start')]
            ])
        )

    def _handle_delete_settings(self, query):
        """Handle auto-delete settings"""
        action = query.data.split('_')[1] if '_' in query.data else 'set'
        bot_username = self.username
        
        if action == 'set':
            user_db[f'editing_{bot_username}'] = 'delete_time'
            query.edit_message_text(
                "⏱️ <b>Set Waktu Hapus Otomatis</b>\n\n"
                "Kirim waktu dalam detik (contoh: 3600 untuk 1 jam)\n"
                "Atau 0 untuk menonaktifkan:",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Kembali", callback_data='bt_start')]
                ])
            )
        else:
            # Handle other delete actions if needed
            pass

    def message_handler(self, update: Update, context: CallbackContext):
        """Handle all incoming messages"""
        message = update.message
        if not message:
            return
        
        # Check if admin is editing settings
        if message.from_user.id == self.creator_id and user_db.get(f'editing_{self.username}'):
            self._handle_admin_settings(update, context)
            return
        
        # Check if bot is paused
        if user_db.get(f'jeda_{self.username}') == 'iya':
            update.message.reply_text("⏸️ <b>Bot sedang dijeda</b>\n\nAnda tidak bisa mengirim pesan sekarang.",
                                    parse_mode='HTML')
            return
        
        # Check force subscription
        if not self._check_subscription(update, context):
            return
        
        # Handle different message types
        if message.photo:
            self.handle_photo(update, context)
        elif message.sticker:
            self.handle_sticker(update, context)
        elif message.document:
            self.handle_document(update, context)
        elif message.text:
            self.handle_text(update, context)

    def _handle_admin_settings(self, update: Update, context: CallbackContext):
        """Handle admin setting updates"""
        message = update.message
        setting_type = user_db.get(f'editing_{self.username}')
        
        if setting_type == 'start_text':
            user_db[f'startText_{self.username}'] = message.text
            user_db.pop(f'editing_{self.username}', None)
            update.message.reply_text("✅ Pesan welcome berhasil diupdate!")
        
        elif setting_type == 'auto_reply':
            user_db[f'kirimText_{self.username}'] = message.text
            user_db.pop(f'editing_{self.username}', None)
            update.message.reply_text("✅ Pesan auto reply berhasil diupdate!")
        
        elif setting_type == 'connect_channel' and message.forward_from_chat:
            if message.forward_from_chat.type == 'channel':
                try:
                    # Check if bot is admin in channel
                    bot_member = self.updater.bot.get_chat_member(
                        message.forward_from_chat.id,
                        self.updater.bot.id
                    )
                    if bot_member.status in ['administrator', 'creator']:
                        user_db[f'channel_{self.username}'] = str(message.forward_from_chat.id)
                        user_db.pop(f'editing_{self.username}', None)
                        update.message.reply_text("✅ Channel berhasil terhubung!")
                    else:
                        update.message.reply_text("❌ Bot harus menjadi admin di channel tersebut!")
                except Exception as e:
                    logger.error(f"Error connecting channel: {e}")
                    update.message.reply_text("❌ Gagal memverifikasi bot sebagai admin channel.")
        
        elif setting_type == 'delete_time':
            try:
                seconds = int(message.text)
                if seconds < 0:
                    raise ValueError
                
                user_db[f'del_{self.username}'] = seconds
                user_db.pop(f'editing_{self.username}', None)
                
                if seconds == 0:
                    update.message.reply_text("✅ Auto-delete dinonaktifkan")
                else:
                    update.message.reply_text(f"✅ Auto-delete diatur ke {seconds} detik")
            except ValueError:
                update.message.reply_text("❌ Masukkan angka yang valid dalam detik (0 untuk menonaktifkan)")

    def handle_photo(self, update: Update, context: CallbackContext):
        """Handle photo messages"""
        if user_db.get(f'modeFoto_{self.username}'):
            return
        
        channel_id = user_db.get(f'channel_{self.username}', str(MAIN_ADMIN_ID))
        caption = update.message.caption or ""
        
        try:
            sent_message = context.bot.send_photo(
                chat_id=channel_id,
                photo=update.message.photo[-1].file_id,
                caption=caption,
                has_spoiler=True
            )
            
            # Send confirmation
            reply_text = user_db.get(f'kirimText_{self.username}', "✅ Pesan berhasil terkirim!")
            update.message.reply_text(reply_text)
            
            # Auto-delete if enabled
            self._auto_delete(channel_id, sent_message.message_id)
        except Exception as e:
            logger.error(f"Failed to send photo: {e}")
            update.message.reply_text("❌ Gagal mengirim foto. Silakan coba lagi.")

    def handle_sticker(self, update: Update, context: CallbackContext):
        """Handle sticker messages"""
        if user_db.get(f'modeSticker_{self.username}'):
            return
        
        channel_id = user_db.get(f'channel_{self.username}', str(MAIN_ADMIN_ID))
        
        try:
            sent_message = context.bot.send_sticker(
                chat_id=channel_id,
                sticker=update.message.sticker.file_id
            )
            
            # Send confirmation
            reply_text = user_db.get(f'kirimText_{self.username}', "✅ Pesan berhasil terkirim!")
            update.message.reply_text(reply_text)
            
            # Auto-delete if enabled
            self._auto_delete(channel_id, sent_message.message_id)
        except Exception as e:
            logger.error(f"Failed to send sticker: {e}")
            update.message.reply_text("❌ Gagal mengirim stiker. Silakan coba lagi.")

    def handle_document(self, update: Update, context: CallbackContext):
        """Handle document messages"""
        if user_db.get(f'modeBerkas_{self.username}'):
            return
        
        channel_id = user_db.get(f'channel_{self.username}', str(MAIN_ADMIN_ID))
        
        try:
            sent_message = context.bot.send_document(
                chat_id=channel_id,
                document=update.message.document.file_id,
                caption=update.message.caption or ""
            )
            
            # Send confirmation
            reply_text = user_db.get(f'kirimText_{self.username}', "✅ Pesan berhasil terkirim!")
            update.message.reply_text(reply_text)
            
            # Auto-delete if enabled
            self._auto_delete(channel_id, sent_message.message_id)
        except Exception as e:
            logger.error(f"Failed to send document: {e}")
            update.message.reply_text("❌ Gagal mengirim dokumen. Silakan coba lagi.")

    def handle_text(self, update: Update, context: CallbackContext):
        """Handle text messages"""
        if (update.message.text.startswith('/') or 
            user_db.get(f'modeText_{self.username}')):
            return
        
        channel_id = user_db.get(f'channel_{self.username}', str(MAIN_ADMIN_ID))
        
        try:
            sent_message = context.bot.send_message(
                chat_id=channel_id,
                text=update.message.text
            )
            
            # Send confirmation
            reply_text = user_db.get(f'kirimText_{self.username}', "✅ Pesan berhasil terkirim!")
            update.message.reply_text(reply_text)
            
            # Auto-delete if enabled
            self._auto_delete(channel_id, sent_message.message_id)
        except Exception as e:
            logger.error(f"Failed to send text message: {e}")
            update.message.reply_text("❌ Gagal mengirim pesan. Silakan coba lagi.")

    def _auto_delete(self, chat_id: str, message_id: int):
        """Auto-delete message after delay if enabled"""
        delay = user_db.get(f'del_{self.username}')
        if not delay or int(delay) <= 0:
            return
        
        try:
            def delete_message():
                try:
                    self.updater.bot.delete_message(chat_id, message_id)
                except Exception as e:
                    logger.error(f"Failed to auto-delete message: {e}")
            
            # Schedule deletion
            self.updater.job_queue.run_once(
                lambda _: delete_message(),
                int(delay)
            )
        except Exception as e:
            logger.error(f"Error scheduling auto-delete: {e}")

class BotManager:
    """Manager for creating and managing anonymous bots"""
    def __init__(self):
        self.active_bots = {}  # {user_id: bot_instance}
        self.main_bot = None
    
    def set_main_bot(self, updater: Updater):
        """Set the main builder bot"""
        self.main_bot = updater
        logger.info("Main bot initialized")
    
    def create_bot(self, token: str, creator_id: int):
        """Create a new anonymous bot"""
        if creator_id in self.active_bots:
            return False, "Anda sudah memiliki bot aktif"
        
        try:
            # Validate token format
            if not re.match(r'^\d{9,10}:[a-zA-Z0-9_-]{35}$', token):
                return False, "❌ Format token tidak valid"
            
            # Try to create the bot
            bot = AnonymousBot(token, creator_id)
            self.active_bots[creator_id] = bot
            
            return True, f"✅ Bot berhasil dibuat!\n\nUsername: @{bot.username}\n\nGunakan /settings untuk konfigurasi."
        except Exception as e:
            logger.error(f"Failed to create bot: {e}")
            return False, f"❌ Gagal membuat bot: {str(e)}"

# Initialize bot manager
bot_manager = BotManager()

# Flask app
app = Flask(__name__)

@app.route('/')
def home():
    return "Anon Builder Bot is running!"

@app.route('/webhook', methods=['POST'])
def webhook():
    """Webhook for main bot"""
    if not bot_manager.main_bot:
        return jsonify(success=False, error="Main bot not initialized"), 500
    
    update = Update.de_json(request.get_json(), bot_manager.main_bot.bot)
    bot_manager.main_bot.dispatcher.process_update(update)
    return jsonify(success=True)

@app.route('/webhook/<token>', methods=['POST'])
def bot_webhook(token):
    """Webhook for created bots"""
    for user_id, bot in bot_manager.active_bots.items():
        if bot.token == token:
            update = Update.de_json(request.get_json(), bot.updater.bot)
            bot.dispatcher.process_update(update)
            return jsonify(success=True)
    
    return jsonify(success=False, error="Bot not found"), 404

def setup_telegram_bot():
    """Setup the main bot"""
    try:
        updater = Updater(TOKEN, use_context=True)
        dp = updater.dispatcher
        
        # Register handlers
        dp.add_handler(CommandHandler("start", start))
        dp.add_handler(MessageHandler(
            Filters.forwarded & Filters.chat_type.private & Filters.text,
            handle_forwarded_message
        ))
        dp.add_handler(CallbackQueryHandler(button_handler))
        
        # Set webhook
        webhook_url = f"{WEBHOOK_URL}/webhook"
        updater.bot.set_webhook(webhook_url)
        logger.info(f"Main bot webhook set to: {webhook_url}")
        
        bot_manager.set_main_bot(updater)
        logger.info("Bot setup completed")
        
        return updater
    except Exception as e:
        logger.error(f"Failed to setup bot: {e}")
        raise

def run():
    """Run the application"""
    try:
        # Start the main bot
        main_bot = setup_telegram_bot()
        
        # Start Flask app
        app.run(host='0.0.0.0', port=int(os.getenv('PORT', 8000)))
    except Exception as e:
        logger.error(f"Application failed: {e}")

if __name__ == '__main__':
    run()
