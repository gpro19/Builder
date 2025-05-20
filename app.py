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
LOG_CHANNEL = -1001234567890   # Channel for logging

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
        # Get the appropriate message object (works for both commands and callback queries)
        message = update.message or update.callback_query.message
        user = update.effective_user
        
        if user.id != self.creator_id:
            message.reply_text("⛔ <b>Akses Ditolak</b>\n\nHanya pemilik bot yang bisa mengakses pengaturan ini.", 
                             parse_mode='HTML')
            return
        
        # Get current settings
        welcome_text = user_db.get(f'startText_{self.username}', 
                                 "👋 Halo! Selamat datang di bot menfes anonim.")
        auto_reply = user_db.get(f'kirimText_{self.username}', 
                               "✅ Pesan Anda telah terkirim secara anonim!")
        channel = user_db.get(f'channel_{self.username}')
        delete_time = user_db.get(f'del_{self.username}')
        is_paused = user_db.get(f'jeda_{self.username}') == 'iya'
        fsub_enabled = user_db.get(f'fsub_{self.username}') == 'iya'
        
        # Text mode status with emojis
        text_mode = "✅ Aktif" if not user_db.get(f'modeText_{self.username}') else "❌ Nonaktif"
        photo_mode = "✅ Aktif" if not user_db.get(f'modeFoto_{self.username}') else "❌ Nonaktif"
        sticker_mode = "✅ Aktif" if not user_db.get(f'modeSticker_{self.username}') else "❌ Nonaktif"
        doc_mode = "✅ Aktif" if not user_db.get(f'modeBerkas_{self.username}') else "❌ Nonaktif"
        
        # Button layout
        keyboard = [
            [InlineKeyboardButton("✏️ Edit Pesan Welcome", callback_data='set_welcome')],
            [InlineKeyboardButton("💬 Edit Auto Reply", callback_data='set_autoreply')],
        ]    
        
        if channel:
	        keyboard.append([InlineKeyboardButton("📢 Kelola Channel", callback_data='manage_channel')])
	    else:
	        keyboard.append([InlineKeyboardButton("📢 Set Channel", callback_data='set_channel')])
	   
        keyboard.extend([    
            [InlineKeyboardButton(f"⏱️ Auto Delete: {delete_time if delete_time else 'Off'} detik", callback_data='set_delete_time')],
            [InlineKeyboardButton(f"⏸️ Mode Jeda: {'Aktif' if is_paused else 'Nonaktif'}", callback_data='toggle_pause')],
            [InlineKeyboardButton(f"🔗 Force Sub: {'Aktif' if fsub_enabled else 'Nonaktif'}", callback_data='toggle_fsub')],
            [
                InlineKeyboardButton(f"Teks: {text_mode}", callback_data='toggle_text_mode'),
                InlineKeyboardButton(f"Foto: {photo_mode}", callback_data='toggle_photo_mode')
            ],
            [
                InlineKeyboardButton(f"Stiker: {sticker_mode}", callback_data='toggle_sticker_mode'),
                InlineKeyboardButton(f"Dokumen: {doc_mode}", callback_data='toggle_doc_mode')
            ],
            [InlineKeyboardButton("🔙 Tutup Pengaturan", callback_data='close_settings')]
        ])
     
	
	
        # Improved settings text with better formatting
        settings_text = (
            f"⚙️ <b>PENGATURAN BOT</b> @{self.username}\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"📝 <b>Pesan Welcome:</b>\n<code>{html.escape(welcome_text[:60])}{'...' if len(welcome_text) > 60 else ''}</code>\n\n"
            f"📩 <b>Auto Reply:</b>\n<code>{html.escape(auto_reply[:60])}{'...' if len(auto_reply) > 60 else ''}</code>\n\n"
            f"📢 <b>Channel Terhubung:</b> <code>{channel if channel else 'Tidak ada'}</code>\n"
            f"⏱️ <b>Auto Delete:</b> <code>{delete_time if delete_time else 'Off'} detik</code>\n\n"
            "🛠️ <b>Status Fitur:</b>\n"
            f"- Teks: <b>{text_mode}</b>\n"
            f"- Foto: <b>{photo_mode}</b>\n"
            f"- Stiker: <b>{sticker_mode}</b>\n"
            f"- Dokumen: <b>{doc_mode}</b>\n\n"
            "🔧 Silakan pilih opsi di bawah:"
        )
        
        # Edit message if it's a callback query, otherwise send new message
        if update.callback_query:
            update.callback_query.edit_message_text(
                settings_text,
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            message.reply_text(
                settings_text,
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
      
    def button_handler(self, update: Update, context: CallbackContext):
        """Handle inline button presses"""
        query = update.callback_query
        query.answer()
        
        action = query.data
        
        # Main settings actions
        if action == 'back_to_settings':
            self.settings(update, context)
        
        # Toggle actions
        elif action.startswith('toggle_'):
            self._handle_toggle_action(query, action[7:])
            self.settings(update, context)
        
        # Set actions
        elif action.startswith('set_'):
            self._handle_set_action(query, action[4:])
    
    def _handle_toggle_action(self, query, action_type):
        """Handle toggle actions (pause, fsub, modes)"""
        bot_username = self.username
        
        if action_type == 'pause':
            current = user_db.get(f'jeda_{bot_username}')
            user_db[f'jeda_{bot_username}'] = 'iya' if not current else None
            query.edit_message_text(f"⏸️ Mode jeda {'diaktifkan' if not current else 'dinonaktifkan'}")
        
        elif action_type == 'fsub':
            current = user_db.get(f'fsub_{bot_username}')
            user_db[f'fsub_{bot_username}'] = 'iya' if not current else None
            query.edit_message_text(f"🔗 Force sub {'diaktifkan' if not current else 'dinonaktifkan'}")
        
        elif action_type == 'text_mode':
            current = user_db.get(f'modeText_{bot_username}')
            user_db[f'modeText_{bot_username}'] = 'nonaktif' if not current else None
        
        elif action_type == 'photo_mode':
            current = user_db.get(f'modeFoto_{bot_username}')
            user_db[f'modeFoto_{bot_username}'] = 'nonaktif' if not current else None
        
        elif action_type == 'sticker_mode':
            current = user_db.get(f'modeSticker_{bot_username}')
            user_db[f'modeSticker_{bot_username}'] = 'nonaktif' if not current else None
        
        elif action_type == 'doc_mode':
            current = user_db.get(f'modeBerkas_{bot_username}')
            user_db[f'modeBerkas_{bot_username}'] = 'nonaktif' if not current else None
    
    def _handle_set_action(self, query, action_type):
        """Handle set actions (welcome, autoreply, channel, delete time)"""
        bot_username = self.username
        
        if action_type == 'welcome':
            current_text = user_db.get(f'startText_{bot_username}', 
                                     "Halo! Selamat datang di bot menfes anonim.")
            query.edit_message_text(
                f"📝 <b>Set Pesan Welcome</b>\n\nPesan saat ini:\n<code>{html.escape(current_text)}</code>\n\n"
                "Kirim pesan baru untuk mengganti:",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Kembali", callback_data='back_to_settings')]])
            )
            user_db[f'editing_{bot_username}'] = 'start_text'
        
        elif action_type == 'autoreply':
            current_text = user_db.get(f'kirimText_{bot_username}', "Pesan berhasil terkirim!")
            query.edit_message_text(
                f"📩 <b>Set Pesan Auto Reply</b>\n\nPesan saat ini:\n<code>{html.escape(current_text)}</code>\n\n"
                "Kirim pesan baru untuk mengganti:",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Kembali", callback_data='back_to_settings')]])
            )
            user_db[f'editing_{bot_username}'] = 'auto_reply'
        
        elif action_type == 'channel':
            # Check if channel is already set
            current_channel = user_db.get(f'channel_{bot_username}')
            
            if current_channel:
                # Show channel management options
                try:
                    channel_info = self.updater.bot.get_chat(current_channel)
                    channel_name = channel_info.title
                    channel_link = f"t.me/{channel_info.username}" if channel_info.username else f"ID: {current_channel}"
                    
                    query.edit_message_text(
                        f"📢 <b>Channel Settings</b>\n\n"
                        f"Channel saat ini:\n{channel_name}\n{channel_link}\n\n"
                        "Silakan pilih aksi:",
                        parse_mode='HTML',
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("🔄 Ganti Channel", callback_data='change_channel')],
                            [InlineKeyboardButton("❌ Putuskan Channel", callback_data='disconnect_channel')],
                            [InlineKeyboardButton("🔙 Kembali", callback_data='back_to_settings')]
                        ])
                    )
                except Exception as e:
                    logger.error(f"Error getting channel info: {e}")
                    query.edit_message_text(
                        "❌ Gagal mendapatkan info channel. Channel mungkin sudah dihapus.",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Kembali", callback_data='back_to_settings')]])
                    )
            else:
                # Show instructions to connect channel
                query.edit_message_text(
                    f"📢 <b>Connect Channel</b>\n\n"
                    "1. Tambahkan @{bot_username} ke channel Anda sebagai admin (dengan izin posting)\n"
                    "2. Kirim pesan apapun di channel tersebut\n"
                    "3. Teruskan pesan tersebut ke bot ini\n\n"
                    "Pastikan bot memiliki izin:\n"
                    "- Kirim pesan\n"
                    "- Lihat pesan\n"
                    "- Hapus pesan (jika auto-delete diaktifkan)",
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Kembali", callback_data='back_to_settings')]])
                )
                user_db[f'editing_{bot_username}'] = 'connect_channel'
        elif action_type == 'manage_channel':
		    current_channel = user_db.get(f'channel_{self.username}')
		    try:
		        channel_info = self.updater.bot.get_chat(current_channel)
		        channel_name = channel_info.title
		        channel_link = f"t.me/{channel_info.username}" if channel_info.username else f"ID: {current_channel}"
		        
		        query.edit_message_text(
		            f"📢 <b>Kelola Channel</b>\n\n"
		            f"Channel saat ini:\n{channel_name}\n{channel_link}\n\n"
		            "Silakan pilih aksi:",
		            parse_mode='HTML',
		            reply_markup=InlineKeyboardMarkup([
		                [InlineKeyboardButton("🔄 Ganti Channel", callback_data='change_channel')],
		                [InlineKeyboardButton("❌ Putuskan Channel", callback_data='disconnect_channel')],
		                [InlineKeyboardButton("🔙 Kembali", callback_data='back_to_settings')]
		            ])
		        )
		    except Exception as e:
		        logger.error(f"Error getting channel info: {e}")
		        query.edit_message_text(
		            "❌ Gagal mendapatkan info channel. Channel mungkin sudah dihapus.",
		            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Kembali", callback_data='back_to_settings')]])
		        )
		        
        elif action_type == 'change_channel':
            # Show instructions to change channel
            query.edit_message_text(
                f"📢 <b>Ganti Channel</b>\n\n"
                "1. Tambahkan @{bot_username} ke channel baru sebagai admin\n"
                "2. Kirim pesan apapun di channel tersebut\n"
                "3. Teruskan pesan tersebut ke bot ini\n\n"
                "Channel lama akan otomatis diganti.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Kembali", callback_data='back_to_settings')]])
            )
            user_db[f'editing_{bot_username}'] = 'connect_channel'
        
        elif action_type == 'disconnect_channel':
            user_db.pop(f'channel_{bot_username}', None)
            query.edit_message_text(
                "✅ Channel berhasil diputuskan. Pesan akan dikirim ke admin bot.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Kembali", callback_data='back_to_settings')]])
            )
        
        elif action_type == 'delete_time':
            current_time = user_db.get(f'del_{bot_username}')
            keyboard = [
                [InlineKeyboardButton("5 detik", callback_data='set_delete_5')],
                [InlineKeyboardButton("10 detik", callback_data='set_delete_10')],
                [InlineKeyboardButton("30 detik", callback_data='set_delete_30')],
                [InlineKeyboardButton("1 menit", callback_data='set_delete_60')],
                [InlineKeyboardButton("5 menit", callback_data='set_delete_300')],
                [InlineKeyboardButton("Nonaktifkan", callback_data='set_delete_0')],
                [InlineKeyboardButton("🔙 Kembali", callback_data='back_to_settings')]
            ]
            
            query.edit_message_text(
                f"⏱️ <b>Set Waktu Hapus Otomatis</b>\n\n"
                f"Saat ini: {current_time if current_time else 'Nonaktif'}",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        elif action_type.startswith('delete_'):
            time_seconds = action_type.split('_')[1]
            if time_seconds == '0':
                user_db.pop(f'del_{bot_username}', None)
                query.edit_message_text(
                    "⏱️ Auto-delete dinonaktifkan",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Kembali", callback_data='back_to_settings')]])
                )
            else:
                user_db[f'del_{bot_username}'] = time_seconds
                query.edit_message_text(
                    f"⏱️ Auto-delete diaktifkan ({time_seconds} detik)",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Kembali", callback_data='back_to_settings')]])
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
        if message.photo and not user_db.get(f'modeFoto_{self.username}'):
            self.handle_photo(update, context)
        elif message.sticker and not user_db.get(f'modeSticker_{self.username}'):
            self.handle_sticker(update, context)
        elif message.document and not user_db.get(f'modeBerkas_{self.username}'):
            self.handle_document(update, context)
        elif message.text and not message.text.startswith('/') and not user_db.get(f'modeText_{self.username}'):
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
                        # Verify bot permissions
                        if not (bot_member.can_post_messages and bot_member.can_delete_messages):
                            update.message.reply_text(
                                "❌ Bot membutuhkan izin:\n"
                                "- Kirim pesan\n"
                                "- Hapus pesan (untuk fitur auto-delete)\n\n"
                                "Silakan berikan izin tersebut dan coba lagi."
                            )
                            return
                        
                        user_db[f'channel_{self.username}'] = str(message.forward_from_chat.id)
                        user_db.pop(f'editing_{self.username}', None)
                        
                        # Get channel info for confirmation
                        channel_info = self.updater.bot.get_chat(message.forward_from_chat.id)
                        channel_name = channel_info.title
                        channel_link = f"t.me/{channel_info.username}" if channel_info.username else f"ID: {message.forward_from_chat.id}"
                        
                        update.message.reply_text(
                            f"✅ Channel berhasil terhubung!\n\n"
                            f"📢 <b>{channel_name}</b>\n"
                            f"🔗 {channel_link}\n\n"
                            "Pesan anonim akan dikirim ke channel ini.",
                            parse_mode='HTML'
                        )
                    else:
                        update.message.reply_text(
                            "❌ Bot harus menjadi admin di channel tersebut!\n\n"
                            "Pastikan Anda:\n"
                            "1. Menambahkan @{self.username} sebagai admin\n"
                            "2. Memberikan izin posting dan hapus pesan"
                        )
                except Exception as e:
                    logger.error(f"Error connecting channel: {e}")
                    update.message.reply_text(
                        "❌ Gagal memverifikasi bot sebagai admin channel.\n"
                        "Pastikan bot sudah ditambahkan sebagai admin dengan izin yang cukup."
                    )

    def handle_photo(self, update: Update, context: CallbackContext):
        """Handle photo messages"""
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
            logger.error(f"Failed to send text message: {e}")
            update.message.reply_text("❌ Gagal mengirim pesan teks. Silakan coba lagi.")
    
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

# Flask routes
@app.route('/')
def home():
    return "Anon Builder Bot is running!"

@app.route('/webhook', methods=['POST'])
def webhook():
    """Webhook for main bot"""
    if not bot_manager.main_bot:
        return jsonify(success=False, error="Main bot not initialized"), 500
    
    try:
        update = Update.de_json(request.get_json(), bot_manager.main_bot.bot)
        bot_manager.main_bot.dispatcher.process_update(update)
        return jsonify(success=True)
    except Exception as e:
        logger.error(f"Error processing main bot webhook: {e}")
        return jsonify(success=False, error=str(e)), 500

@app.route('/webhook/<token>', methods=['POST'])
def bot_webhook(token):
    """Webhook for created bots"""
    try:
        for user_id, bot in bot_manager.active_bots.items():
            if bot.token == token:
                update = Update.de_json(request.get_json(), bot.updater.bot)
                bot.dispatcher.process_update(update)
                return jsonify(success=True)
        
        return jsonify(success=False, error="Bot not found"), 404
    except Exception as e:
        logger.error(f"Error processing bot webhook: {e}")
        return jsonify(success=False, error=str(e)), 500

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
        [InlineKeyboardButton("📝 Tentang", callback_data='about')],
        [InlineKeyboardButton("🤖 Buat Bot", callback_data='build_bot')],
        [
            InlineKeyboardButton("🆘 Bantuan", callback_data='help'),
            InlineKeyboardButton("💬 Support", callback_data='support')
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
        f"🔄 Sedang membuat bot...</i>\n\n{message}",
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
    
    if query.data == 'build_bot':
        user_db[f'addbot_{query.message.chat.id}'] = True
        query.edit_message_text(
            "📝 <b>Panduan Membuat Bot</b>\n\n"
            "1. Buka @BotFather dan kirim /newbot\n"
            "2. Ikuti instruksi untuk membuat bot baru\n"
            "3. Setelah mendapatkan token, <b>teruskan pesan lengkap dari @BotFather</b> ke saya",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Kembali", callback_data='back_to_start')]])
        )
    
    elif query.data == 'about':
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
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Kembali", callback_data='back_to_start')]])
        )
    
    elif query.data == 'help':
        keyboard = [
            [InlineKeyboardButton("👮 Admin 1", url="tg://user?id=1910497806")],
            [InlineKeyboardButton("👮 Admin 2", url="tg://user?id=6013163225")],
            [InlineKeyboardButton("🔙 Kembali", callback_data='back_to_start')]
        ]
        query.edit_message_text(
            "<b>📞 Kontak Admin</b>\n\nHubungi admin jika Anda membutuhkan bantuan:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif query.data == 'support':
        user_db[f'support_{query.message.chat.id}'] = True
        keyboard = [[InlineKeyboardButton("❌ Batalkan", callback_data='cancel_support')]]
        query.edit_message_text(
            "💬 <b>Mode Support</b>\n\nSilakan kirim pesan Anda untuk admin support...",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif query.data == 'cancel_support':
        user_db.pop(f'support_{query.message.chat.id}', None)
        query.edit_message_text(
            "❌ Permintaan dibatalkan",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Kembali ke Menu", callback_data='back_to_start')]])
        )
    
    elif query.data == 'back_to_start':
        start(update, context)

def handle_support_message(update: Update, context: CallbackContext):
    """Handle messages sent in support mode"""
    user_id = update.message.from_user.id
    
    # Periksa apakah user dalam mode support
    if not user_db.get(f'support_{user_id}'):
        return
    
    # Hapus flag support setelah pesan dikirim
    user_db.pop(f'support_{user_id}', None)
    
    user = update.message.from_user
    name = html.escape(user.first_name)
    if user.last_name:
        name += f" {html.escape(user.last_name)}"
    
    # Format pesan untuk admin
    support_text = (
        f"🆘 <b>Pesan Support Baru</b>\n\n"
        f"👤 <b>Dari:</b> <a href='tg://user?id={user_id}'>{name}</a>\n"
        f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
        f"📝 <b>Pesan:</b>\n<code>{html.escape(update.message.text)}</code>"
    )
    
    # Kirim ke admin
    try:
        context.bot.send_message(
            chat_id=MAIN_ADMIN_ID,
            text=support_text,
            parse_mode='HTML'
        )
        
        # Beri feedback ke user
        update.message.reply_text(
            "✅ Pesan support Anda telah terkirim ke admin. Terima kasih!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Kembali ke Menu", callback_data='back_to_start')]])
        )
    except Exception as e:
        logger.error(f"Gagal mengirim pesan support: {e}")
        update.message.reply_text(
            "❌ Gagal mengirim pesan support. Silakan coba lagi nanti.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Kembali ke Menu", callback_data='back_to_start')]])
        )
        
        
def setup_telegram_bot():
    """Setup the main bot"""
    try:
        updater = Updater(TOKEN, use_context=True)
        dp = updater.dispatcher
        
        # Add handlers
        dp.add_handler(CommandHandler("start", start))
        dp.add_handler(MessageHandler(
            Filters.forwarded & Filters.chat_type.private & Filters.text,
            handle_forwarded_message
        ))
        dp.add_handler(CallbackQueryHandler(button_handler))
        
        # Tambahkan handler untuk pesan support
        dp.add_handler(MessageHandler(
            Filters.text & Filters.chat_type.private,
            handle_support_message
        ))

        
        # Set webhook
        webhook_url = f"{WEBHOOK_URL}/webhook"
        updater.bot.set_webhook(webhook_url)
        logger.info(f"Main bot webhook set to: {webhook_url}")
        
        # Initialize bot manager
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
        port = int(os.getenv('PORT', 8000))
        app.run(host='0.0.0.0', port=port)
    except Exception as e:
        logger.error(f"Application failed: {e}")

if __name__ == '__main__':
    run()
