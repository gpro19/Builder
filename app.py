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
import re
from flask import Flask, request, jsonify
import os
import html

app = Flask(__name__)

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN environment variable not set")

WEBHOOK_URL = os.getenv("WEBHOOK_URL")
if not WEBHOOK_URL:
    raise ValueError("WEBHOOK_URL environment variable not set")

MAIN_ADMIN_ID = 7117744807  # Admin of the main bot
LOG_CHANNEL = 6172467461   # Channel for logging

# Improved database using dictionary with persistence
user_db = {}

class AnonymousBot:
    def __init__(self, token: str, creator_id: int):
        """Initialize an anonymous messaging bot"""
        self.token = token
        self.creator_id = creator_id  # The user who created this bot becomes admin
        
        try:
            self.updater = Updater(token, use_context=True)
            self.dispatcher = self.updater.dispatcher
            
            # Get bot info
            self.username = self.updater.bot.get_me().username
            
            # Register handlers
            self._register_handlers()
            
            # Set webhook
            webhook_url = f"{WEBHOOK_URL}/webhook/{token}"
            self.updater.bot.set_webhook(webhook_url)
            logger.info(f"Webhook set for bot @{self.username} to {webhook_url}")
            
            # Send confirmation to creator
            self.updater.bot.send_message(
                chat_id=creator_id,
                text=f"✅ Bot @{self.username} berhasil diaktifkan!\n\n"
                     f"Gunakan /settings di bot untuk mengkonfigurasinya."
            )
            
        except Exception as e:
            logger.error(f"Failed to initialize bot: {e}")
            raise
        
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
        welcome_text = user_db.get(f'startText_{self.username}', "Halo! Selamat datang di bot menfes anonim.")
        auto_reply = user_db.get(f'kirimText_{self.username}', "✅ Pesan berhasil terkirim!")
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
            current_text = user_db.get(f'startText_{bot_username}', 
                                     "Halo! Selamat datang di bot menfes anonim.")
            query.edit_message_text(
                f"📝 <b>Set Pesan Welcome</b>\n\nPesan saat ini:\n<code>{html.escape(current_text)}</code>\n\n"
                "Kirim pesan baru untuk mengganti:",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Kembali", callback_data='bt_start')]])
            )
            user_db[f'editing_{bot_username}'] = 'start_text'
        
        elif data == 'st_kirim':
            current_text = user_db.get(f'kirimText_{bot_username}', "Pesan berhasil terkirim!")
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
                f"1. Tambahkan @{bot_username} ke channel Anda sebagai admin (dengan izin posting)\n"
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
            
            # Log the message
            self._log_message(update, "Photo", caption)
            
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
            
            # Log the message
            self._log_message(update, "Sticker")
            
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
            
            # Log the message
            self._log_message(update, "Document", update.message.caption)
            
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

            # Log the message
            self._log_message(update, "Text", update.message.text)
            
            # Auto-delete if enabled
            self._auto_delete(channel_id, sent_message.message_id)
        except Exception as e:
            logger.error(f"Failed to log message: {e}")
	


    def _log_message(self, update: Update, msg_type: str, caption: str = ""):
        """Log messages to channels"""
        user = update.effective_user
        name = html.escape(user.first_name)
        if user.last_name:
            name += f" {html.escape(user.last_name)}"
        
        log_text = (
            f"📩 <b>New {msg_type} from @{self.username}</b>\n"
            f"👤 <b>From:</b> {name} (<code>{user.id}</code>)\n"
        )
        
        if caption:
            log_text += f"\n<code>{html.escape(caption)}</code>"
        
        try:
            # Send to log channel
            self.updater.bot.send_message(
                chat_id=LOG_CHANNEL,
                text=log_text,
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Failed to log message: {e}")

    def _auto_delete(self, chat_id: str, message_id: int):
        """Auto-delete message after delay if enabled"""
        delay = user_db.get(f'del_{self.username}')
        if not delay:
            return
        
        try:
            delay_seconds = int(delay)
            
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

    def _handle_mode_settings(self, query):
        """Handle message mode settings"""
        bot_username = self.username
        mode = query.data.split('_')[1]
        
        # Toggle modes
        if mode == 'All':
            user_db.pop(f'modeText_{bot_username}', None)
            user_db.pop(f'modeFoto_{bot_username}', None)
            user_db.pop(f'modeSticker_{bot_username}', None)
            user_db.pop(f'modeBerkas_{bot_username}', None)
            text = "✅ Semua mode pesan diaktifkan"
        else:
            current_state = user_db.get(f'mode{mode}_{bot_username}')
            if current_state:
                user_db.pop(f'mode{mode}_{bot_username}', None)
                text = f"✅ Mode {mode} diaktifkan"
            else:
                user_db[f'mode{mode}_{bot_username}'] = 'nonaktif'
                text = f"❌ Mode {mode} dinonaktifkan"
        
        # Update keyboard
        keyboard = [
            [InlineKeyboardButton("📝 Set Pesan Welcome", callback_data='st_start')],
            [InlineKeyboardButton("📩 Set Pesan Auto Reply", callback_data='st_kirim')],
            [InlineKeyboardButton("📢 Set Channel", callback_data='st_channel' if not user_db.get(f'channel_{bot_username}') else 'st_anon')],
            [InlineKeyboardButton("⏱️ Set Waktu Hapus", callback_data='st_del')],
            [InlineKeyboardButton("⏸️ Set Mode Jeda", callback_data='st_jeda')],
            [InlineKeyboardButton("🔗 Set Force Sub", callback_data='st_fsub')],
            [InlineKeyboardButton("✉️ Set Mode Kirim", callback_data='mode_All')]
        ]
        
        query.edit_message_text(
            f"⚙️ <b>Pengaturan Bot @{bot_username}</b>\n\n"
            f"{text}\n\n"
            "Pilih opsi pengaturan:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    def _handle_pause_settings(self, query):
        """Handle pause mode settings"""
        bot_username = self.username
        current_state = user_db.get(f'jeda_{bot_username}')
        
        if current_state == 'iya':
            user_db.pop(f'jeda_{bot_username}', None)
            text = "✅ Bot kembali aktif"
        else:
            user_db[f'jeda_{bot_username}'] = 'iya'
            text = "⏸️ Bot dijeda"
        
        # Update keyboard
        keyboard = [
            [InlineKeyboardButton("📝 Set Pesan Welcome", callback_data='st_start')],
            [InlineKeyboardButton("📩 Set Pesan Auto Reply", callback_data='st_kirim')],
            [InlineKeyboardButton("📢 Set Channel", callback_data='st_channel' if not user_db.get(f'channel_{bot_username}') else 'st_anon')],
            [InlineKeyboardButton("⏱️ Set Waktu Hapus", callback_data='st_del')],
            [InlineKeyboardButton("⏸️ Set Mode Jeda", callback_data='st_jeda')],
            [InlineKeyboardButton("🔗 Set Force Sub", callback_data='st_fsub')],
            [InlineKeyboardButton("✉️ Set Mode Kirim", callback_data='mode_All')]
        ]
        
        query.edit_message_text(
            f"⚙️ <b>Pengaturan Bot @{bot_username}</b>\n\n"
            f"{text}\n\n"
            "Pilih opsi pengaturan:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    def _handle_fsub_settings(self, query):
        """Handle force subscription settings"""
        bot_username = self.username
        current_state = user_db.get(f'fsub_{bot_username}')
        
        if current_state == 'iya':
            user_db.pop(f'fsub_{bot_username}', None)
            text = "❌ Force subscribe dinonaktifkan"
        else:
            user_db[f'fsub_{bot_username}'] = 'iya'
            text = "✅ Force subscribe diaktifkan"
        
        # Update keyboard
        keyboard = [
            [InlineKeyboardButton("📝 Set Pesan Welcome", callback_data='st_start')],
            [InlineKeyboardButton("📩 Set Pesan Auto Reply", callback_data='st_kirim')],
            [InlineKeyboardButton("📢 Set Channel", callback_data='st_channel' if not user_db.get(f'channel_{bot_username}') else 'st_anon')],
            [InlineKeyboardButton("⏱️ Set Waktu Hapus", callback_data='st_del')],
            [InlineKeyboardButton("⏸️ Set Mode Jeda", callback_data='st_jeda')],
            [InlineKeyboardButton("🔗 Set Force Sub", callback_data='st_fsub')],
            [InlineKeyboardButton("✉️ Set Mode Kirim", callback_data='mode_All')]
        ]
        
        query.edit_message_text(
            f"⚙️ <b>Pengaturan Bot @{bot_username}</b>\n\n"
            f"{text}\n\n"
            "Pilih opsi pengaturan:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    def _handle_delete_settings(self, query):
        """Handle auto-delete settings"""
        bot_username = self.username
        current_delay = user_db.get(f'del_{bot_username}')
        
        keyboard = [
            [InlineKeyboardButton("5 detik", callback_data='del_5')],
            [InlineKeyboardButton("10 detik", callback_data='del_10')],
            [InlineKeyboardButton("30 detik", callback_data='del_30')],
            [InlineKeyboardButton("1 menit", callback_data='del_60')],
            [InlineKeyboardButton("5 menit", callback_data='del_300')],
            [InlineKeyboardButton("Nonaktifkan", callback_data='del_0')],
            [InlineKeyboardButton("🔙 Kembali", callback_data='bt_start')]
        ]
        
        if current_delay:
            text = f"⏱️ Waktu hapus saat ini: {current_delay} detik"
        else:
            text = "⏱️ Auto-delete saat ini dinonaktifkan"
        
        query.edit_message_text(
            f"⚙️ <b>Set Waktu Hapus Otomatis</b>\n\n"
            f"{text}\n\n"
            "Pilih waktu hapus otomatis:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    def _handle_delete_confirmation(self, query):
        """Handle auto-delete confirmation"""
        bot_username = self.username
        delay = query.data.split('_')[1]
        
        if delay == '0':
            user_db.pop(f'del_{bot_username}', None)
            text = "❌ Auto-delete dinonaktifkan"
        else:
            user_db[f'del_{bot_username}'] = delay
            text = f"✅ Auto-delete diaktifkan ({delay} detik)"
        
        # Get current settings for the settings menu
        welcome_text = user_db.get(f'startText_{bot_username}', "Halo! Selamat datang di bot menfes anonim.")
        auto_reply = user_db.get(f'kirimText_{bot_username}', "✅ Pesan berhasil terkirim!")
        channel = user_db.get(f'channel_{bot_username}')
        
        # Prepare keyboard for settings menu
        keyboard = [
            [InlineKeyboardButton("📝 Set Pesan Welcome", callback_data='st_start')],
            [InlineKeyboardButton("📩 Set Pesan Auto Reply", callback_data='st_kirim')],
            [InlineKeyboardButton("📢 Set Channel", callback_data='st_channel' if not channel else 'st_anon')],
            [InlineKeyboardButton("⏱️ Set Waktu Hapus", callback_data='st_del')],
            [InlineKeyboardButton("⏸️ Set Mode Jeda", callback_data='st_jeda')],
            [InlineKeyboardButton("🔗 Set Force Sub", callback_data='st_fsub')],
            [InlineKeyboardButton("✉️ Set Mode Kirim", callback_data='mode_All')]
        ]
        
        # Update message with confirmation and return to settings
        query.edit_message_text(
            f"⚙️ <b>Pengaturan Bot @{bot_username}</b>\n\n"
            f"{text}\n\n"
            f"📝 Pesan Welcome: <code>{html.escape(welcome_text[:50])}...</code>\n"
            f"📩 Auto Reply: <code>{html.escape(auto_reply[:50])}...</code>\n"
            f"📢 Channel: <code>{channel if channel else 'Tidak terhubung'}</code>\n\n"
            "Pilih opsi pengaturan:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

	


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

# Main bot handlers
def start(update: Update, context: CallbackContext):
    """Handle /start command for main bot"""
    user = update.effective_user
    name = html.escape(user.first_name)
    if user.last_name:
        name += f" {html.escape(user.last_name)}"
    
    message = (
        f"Halo <b>{name}</b>! 👋\n\n"
        "Saya adalah Anon Builder yang membantu Anda membuat bot menfes anonim "
        "tanpa perlu server sendiri.\n\n"
        "Silakan pilih opsi di bawah ini:"
    )
    
    keyboard = [
        [InlineKeyboardButton("📝 Tentang", callback_data='bt_about')],
        [InlineKeyboardButton("🤖 Buat Bot", callback_data='bt_build')],
        [
            InlineKeyboardButton("🆘 Bantuan", callback_data='bt_admin'),
            InlineKeyboardButton("💬 Support", callback_data='bt_support')
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        update.message.reply_html(message, reply_markup=reply_markup)
    elif update.callback_query:
        update.callback_query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)

def handle_forwarded_message(update: Update, context: CallbackContext):
    """Handler untuk pesan yang diteruskan dari BotFather"""
    if not (update.message and update.message.forward_from and 
            str(update.message.forward_from.id) == '93372553'):  # BotFather ID
        return
    
    chat_id = update.effective_chat.id
    if not user_db.get(f'addbot_{chat_id}'):
        return
    
    user = update.effective_user
    name = html.escape(user.first_name)
    if user.last_name:
        name += f' {html.escape(user.last_name)}'
    
    # Kirim notifikasi ke admin
    context.bot.send_message(
        chat_id=MAIN_ADMIN_ID,
        text=(
            f"<b>Permintaan Bot Baru</b>\n\n"
            f"👤 <b>User:</b> <a href='tg://user?id={chat_id}'>{name}</a>\n"
            f"🆔 <b>ID:</b> <code>{chat_id}</code>\n"
            f"🤖 <b>Pesan:</b>\n<code>{html.escape(update.message.text)}</code>"
        ),
        parse_mode='HTML'
    )
    
    # Ekstrak token dari pesan
    token_match = re.search(r'\d{9,10}:[a-zA-Z0-9_-]{35}', update.message.text)
    if not token_match:
        update.message.reply_text(
            "❌ Token tidak ditemukan dalam pesan. Pastikan Anda meneruskan pesan lengkap dari @BotFather",
            reply_to_message_id=update.message.message_id
        )
        return
    
    token = token_match.group(0)
    success, message = bot_manager.create_bot(token, user.id)
    
    update.message.reply_html(
        f"<i>🔄 Sedang membuat bot...</i>\n\n{message}",
        reply_to_message_id=update.message.message_id
    )
    
    # Clear the flag
    user_db.pop(f'addbot_{chat_id}', None)

def button_handler(update: Update, context: CallbackContext):
    """Handle inline button presses for main bot"""
    query = update.callback_query
    if not query:
        return
    
    query.answer()
    
    if query.data == 'bt_build':
        user_db[f'addbot_{query.message.chat.id}'] = True
        query.edit_message_text(
            "📝 <b>Panduan Membuat Bot</b>\n\n"
            "1. Buka @BotFather dan kirim /newbot\n"
            "2. Ikuti instruksi untuk membuat bot baru\n"
            "3. Setelah mendapatkan token, <b>teruskan pesan lengkap dari @BotFather</b> ke saya",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Kembali", callback_data='bt_start')]])
        )
    
    elif query.data == 'bt_about':
        query.edit_message_text(
            "🤖 <b>Tentang Anon Builder Bot</b>\n\n"
            "Anon Builder adalah solusi mudah untuk membuat bot menfes Telegram tanpa perlu:\n"
            "- Server pribadi\n"
            "- Pengetahuan pemrograman\n"
            "- Konfigurasi rumit\n\n"
            "Dengan beberapa klik, Anda bisa memiliki bot menfes sendiri!\n\n"
            "📊 Fitur:\n"
            "• Posting anonim ke channel\n"
            "• Pengaturan pesan welcome\n"
            "• Auto reply\n"
            "• Force subscribe channel\n"
            "• Dan banyak lagi!",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Kembali", callback_data='bt_start')]])
        )
    
    elif query.data == 'bt_admin':
        keyboard = [
            [InlineKeyboardButton("👮 Admin 1", url="tg://user?id=1910497806")],
            [InlineKeyboardButton("👮 Admin 2", url="tg://user?id=6013163225")],
            [InlineKeyboardButton("🔙 Kembali", callback_data='bt_start')]
        ]
        query.edit_message_text(
            "<b>📞 Kontak Admin</b>\n\nHubungi admin jika Anda membutuhkan bantuan:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif query.data == 'bt_support':
        user_db[f'support_{query.message.chat.id}'] = True
        keyboard = [[InlineKeyboardButton("❌ Batalkan", callback_data='bt_cancel')]]
        query.edit_message_text(
            "💬 <b>Mode Support</b>\n\nSilakan kirim pesan Anda untuk admin support...",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif query.data == 'bt_cancel':
        user_db.pop(f'support_{query.message.chat.id}', None)
        query.edit_message_text(
            "❌ Permintaan dibatalkan",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Kembali ke Menu", callback_data='bt_start')]])
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
        
        dp.add_handler(CommandHandler("start", start))
        dp.add_handler(MessageHandler(
            Filters.forwarded & Filters.chat_type.private & Filters.text,
            handle_forwarded_message
        ))
        dp.add_handler(CallbackQueryHandler(button_handler))
        
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

