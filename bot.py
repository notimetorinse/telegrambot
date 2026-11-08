import os
import sqlite3
import time
from collections import defaultdict, deque
from datetime import timedelta
from pathlib import Path

from telegram import Update, ChatPermissions
from telegram.constants import ChatMemberStatus
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ChatMemberHandler, ContextTypes, filters

TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
DB_PATH = os.environ.get('DB_PATH', 'party_room.sqlite3')
WARN_LIMIT = int(os.environ.get('WARN_LIMIT', '3'))
FLOOD_COUNT = int(os.environ.get('FLOOD_COUNT', '6'))
FLOOD_WINDOW = int(os.environ.get('FLOOD_WINDOW_SECONDS', '10'))
FLOOD_MUTE_MINUTES = int(os.environ.get('FLOOD_MUTE_MINUTES', '10'))
WARN_MUTE_HOURS = int(os.environ.get('WARN_MUTE_HOURS', '24'))

RULES = ('🎰 NOTIMETORINSE PARTY ROOM — OFFICIAL RULES\n\n'
         '1️⃣ RESPECT EVERYONE: No harassment, discrimination, bullying, or unnecessary drama. Respect members, moderators, and the casino platform.\n\n'
         '2️⃣ KEEP IT PROFESSIONAL: No spam, unauthorized promotions, inappropriate content, or misleading information.\n\n'
         '3️⃣ KEEP THE PARTY FAIR: No scamming, impersonation, begging, or exploiting members. Follow site rules and play responsibly.\n\n'
         'Violations may result in warnings, mutes, or bans.')

flood = defaultdict(deque)

def db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.execute('CREATE TABLE IF NOT EXISTS warnings (chat_id INTEGER NOT NULL, user_id INTEGER NOT NULL, count INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(chat_id,user_id))')
    return connection

async def is_mod(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat or chat.type == 'private':
        return False
    member = await context.bot.get_chat_member(chat.id, user.id)
    return member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)

async def mod_required(update, context):
    if not await is_mod(update, context):
        if update.effective_message:
            await update.effective_message.reply_text('⛔ This command is for Party Room moderators only.')
        return False
    return True

async def rules(update, context):
    await update.effective_message.reply_text(RULES)

async def start(update, context):
    await update.effective_message.reply_text('🎰 NoTimeToRinse Party Room Bot is online! Add me as a group administrator. Use /rules to view the house rules.')

async def welcome(update, context):
    if update.effective_chat.type == 'private':
        return
    for member in update.effective_message.new_chat_members:
        if member.is_bot:
            continue
        await update.effective_message.reply_text(
            f'🎰 Welcome {member.mention_html()} to the NoTimeToRinse Party Room!\n\n'
            '🤝 Respect everyone and the casino platform.\n'
            '📜 Read our three house rules with /rules.\n'
            '🎲 Enjoy the party, play responsibly, and good luck!', parse_mode='HTML')

async def target_user(update):
    msg = update.effective_message
    if msg.reply_to_message and msg.reply_to_message.from_user:
        return msg.reply_to_message.from_user
    return None

async def protected_target(update, context, target):
    if target.id == context.bot.id:
        return True
    member = await context.bot.get_chat_member(update.effective_chat.id, target.id)
    return member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)

async def warn(update, context):
    if not await mod_required(update, context):
        return
    target = await target_user(update)
    if not target:
        await update.effective_message.reply_text('Reply to a member’s message with /warn [reason].')
        return
    if await protected_target(update, context, target):
        await update.effective_message.reply_text('I cannot warn an administrator or myself.')
        return
    chat_id = update.effective_chat.id
    with db() as conn:
        conn.execute('INSERT INTO warnings(chat_id,user_id,count) VALUES(?,?,1) ON CONFLICT(chat_id,user_id) DO UPDATE SET count=count+1', (chat_id, target.id))
        count = conn.execute('SELECT count FROM warnings WHERE chat_id=? AND user_id=?', (chat_id, target.id)).fetchone()[0]
    reason = ' '.join(context.args).strip() or 'Breaking Party Room rules'
    if count >= WARN_LIMIT:
        until = int(time.time()) + WARN_MUTE_HOURS * 3600
        await context.bot.restrict_chat_member(chat_id, target.id, permissions=ChatPermissions(can_send_messages=False), until_date=until)
        with db() as conn:
            conn.execute('DELETE FROM warnings WHERE chat_id=? AND user_id=?', (chat_id, target.id))
        await update.effective_message.reply_text(f'🔇 {target.full_name} reached {WARN_LIMIT} warnings and was muted for {WARN_MUTE_HOURS} hours. Reason: {reason}')
    else:
        await update.effective_message.reply_text(f'⚠️ {target.full_name}: warning {count}/{WARN_LIMIT}. Reason: {reason}')

async def warnings(update, context):
    if not await mod_required(update, context):
        return
    target = await target_user(update)
    if not target:
        await update.effective_message.reply_text('Reply to a member’s message with /warnings.')
        return
    with db() as conn:
        row = conn.execute('SELECT count FROM warnings WHERE chat_id=? AND user_id=?', (update.effective_chat.id, target.id)).fetchone()
    await update.effective_message.reply_text(f'⚠️ {target.full_name}: {row[0] if row else 0}/{WARN_LIMIT} warnings.')

async def clearwarns(update, context):
    if not await mod_required(update, context):
        return
    target = await target_user(update)
    if not target:
        await update.effective_message.reply_text('Reply to a member’s message with /clearwarns.')
        return
    with db() as conn:
        conn.execute('DELETE FROM warnings WHERE chat_id=? AND user_id=?', (update.effective_chat.id, target.id))
    await update.effective_message.reply_text(f'✅ Cleared warnings for {target.full_name}.')

async def mute(update, context):
    if not await mod_required(update, context):
        return
    target = await target_user(update)
    if not target:
        await update.effective_message.reply_text('Reply to a member’s message with /mute [minutes] (default 60).')
        return
    if await protected_target(update, context, target):
        await update.effective_message.reply_text('I cannot mute an administrator or myself.')
        return
    try:
        minutes = max(1, min(10080, int(context.args[0]))) if context.args else 60
    except ValueError:
        await update.effective_message.reply_text('Minutes must be a number, e.g. /mute 60.')
        return
    await context.bot.restrict_chat_member(update.effective_chat.id, target.id, permissions=ChatPermissions(can_send_messages=False), until_date=int(time.time()) + minutes * 60)
    await update.effective_message.reply_text(f'🔇 Muted {target.full_name} for {minutes} minutes.')

async def unmute(update, context):
    if not await mod_required(update, context):
        return
    target = await target_user(update)
    if not target:
        await update.effective_message.reply_text('Reply to a member’s message with /unmute.')
        return
    await context.bot.restrict_chat_member(update.effective_chat.id, target.id, permissions=ChatPermissions(can_send_messages=True, can_send_audios=True, can_send_documents=True, can_send_photos=True, can_send_videos=True, can_send_video_notes=True, can_send_voice_notes=True, can_send_polls=True, can_send_other_messages=True, can_add_web_page_previews=True))
    await update.effective_message.reply_text(f'🔊 Unmuted {target.full_name}.')

async def ban(update, context):
    if not await mod_required(update, context):
        return
    target = await target_user(update)
    if not target:
        await update.effective_message.reply_text('Reply to a member’s message with /ban.')
        return
    if await protected_target(update, context, target):
        await update.effective_message.reply_text('I cannot ban an administrator or myself.')
        return
    await context.bot.ban_chat_member(update.effective_chat.id, target.id)
    await update.effective_message.reply_text(f'🚫 Banned {target.full_name}.')

async def flood_guard(update, context):
    msg = update.effective_message
    if not msg or not update.effective_user or update.effective_chat.type == 'private' or update.effective_user.is_bot:
        return
    if await is_mod(update, context):
        return
    key = (update.effective_chat.id, update.effective_user.id)
    now = time.monotonic()
    q = flood[key]
    while q and now - q[0] > FLOOD_WINDOW:
        q.popleft()
    q.append(now)
    if len(q) >= FLOOD_COUNT:
        q.clear()
        try:
            await context.bot.delete_message(update.effective_chat.id, msg.message_id)
            await context.bot.restrict_chat_member(update.effective_chat.id, update.effective_user.id, permissions=ChatPermissions(can_send_messages=False), until_date=int(time.time()) + FLOOD_MUTE_MINUTES * 60)
            await context.bot.send_message(update.effective_chat.id, f'🔇 {update.effective_user.full_name} was muted for {FLOOD_MUTE_MINUTES} minutes due to message flooding.')
        except Exception as exc:
            print('Flood moderation failed:', repr(exc), flush=True)

async def on_error(update, context):
    print('Bot error:', repr(context.error), flush=True)

def main():
    if not TOKEN:
        raise SystemExit('Set TELEGRAM_BOT_TOKEN in your hosting environment.')
    with db():
        pass
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('rules', rules))
    app.add_handler(CommandHandler('warn', warn))
    app.add_handler(CommandHandler('warnings', warnings))
    app.add_handler(CommandHandler('clearwarns', clearwarns))
    app.add_handler(CommandHandler('mute', mute))
    app.add_handler(CommandHandler('unmute', unmute))
    app.add_handler(CommandHandler('ban', ban))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND & ~filters.StatusUpdate.ALL, flood_guard))
    app.add_error_handler(on_error)
    print('NoTimeToRinse Party Bot started', flush=True)
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
