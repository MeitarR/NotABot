#!/usr/bin/env python
import logging
from typing import Dict

from telegram import (Bot, ChatMember, ChatPermissions, InlineKeyboardButton,
                      InlineKeyboardMarkup, Message, Update, User)
from telegram.ext import (CallbackContext, CallbackQueryHandler,
                          CommandHandler, Filters, Job, MessageHandler,
                          Updater)

NEEDED_PERMISSIONS_TO_OPERATE = ['can_restrict_members', 'can_delete_messages']

TIMEOUT_SEC = 60
DELETE_SEC = 5

RESTRICT_ALL = ChatPermissions(
    can_send_messages=False,
    can_send_media_messages=False,
    can_send_polls=False,
    can_send_other_messages=False,
    can_add_web_page_previews=False,
    can_change_info=False,
    can_invite_users=False,
    can_pin_messages=False)

ALLOW_ALL = ChatPermissions(
    can_send_messages=True,
    can_send_media_messages=True,
    can_send_polls=True,
    can_send_other_messages=True,
    can_add_web_page_previews=True,
    can_change_info=True,
    can_invite_users=True,
    can_pin_messages=True)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

job_queue = None

jobs: Dict[int, Dict[int, Job]] = dict()


def send_answer(message: Message, user: User, answer):
    message.edit_text(
        text=f"[{user.username}](tg://user?id={user.id}) (user id: `{user.id}`) treated as *{answer}*", parse_mode='Markdown')
    job_queue.run_once(lambda c: message.delete(), DELETE_SEC)


def action_bot(message: Message, user: User):
    send_answer(message, user, 'Bot')
    message.bot.kick_chat_member(message.chat_id, user.id)
    message.bot.unban_chat_member(message.chat_id, user.id)


def action_human(message: Message, user: User):
    send_answer(message, user, 'Human')
    message.bot.restrict_chat_member(message.chat_id, user.id, ALLOW_ALL)


def start(update: Update, context: CallbackContext) -> None:
    global jobs
    global job_queue
    bot: Bot = update.message.bot

    bot_in_group: ChatMember = bot.get_chat_member(
        update.effective_chat.id, bot.id)

    if not all([getattr(bot_in_group, perm) for perm in NEEDED_PERMISSIONS_TO_OPERATE]):
        perms = {perm.replace("can_", "").replace("_", " "): getattr(
            bot_in_group, perm) for perm in NEEDED_PERMISSIONS_TO_OPERATE}
        formated_permissions = '\n'.join(
            f'{"Y" if can else "X"} {perm}' for perm, can in perms.items())
        update.effective_chat.send_message(
            f'Please give me admin and make sure I have the folowing permissions so I can work properly :)\n\n{formated_permissions}')
        return
    else:
        update.message.delete()

    for member in update.message.new_chat_members:
        member: User
        if not member.is_bot:
            keyboard = [
                [
                    InlineKeyboardButton(
                        "I'm a bot!", callback_data=f'{member.id},bot'),
                    InlineKeyboardButton(
                        "I'm a human!", callback_data=f'{member.id},human'),
                ]
            ]

            reply_markup = InlineKeyboardMarkup(keyboard)

            msg = update.effective_chat.send_message(f'Welcome [{member.username}](tg://user?id={member.id}) (user id: `{member.id}`) to our server!\n\n'
                                                     f'Please state if you are *human* or *bot*\n\n'
                                                     f'hurry up, you only have {TIMEOUT_SEC} secods',
                                                     reply_markup=reply_markup, parse_mode='Markdown')
            job = job_queue.run_once(
                lambda c: action_bot(msg, member), TIMEOUT_SEC)
            jobs[update.effective_chat.id] = {member.id: job}

            bot.restrict_chat_member(
                update.effective_chat.id, member.id, RESTRICT_ALL)


def button(update: Update, context: CallbackContext) -> None:
    global jobs
    query = update.callback_query

    member_id, answer = query.data.split(',')
    member_id = int(member_id)

    if update.effective_user.id == member_id:
        query.answer()

        jobs[update.effective_chat.id][update.effective_user.id].schedule_removal()

        if answer == 'human':
            action_human(query.message, update.effective_user)
        else:
            action_bot(query.message, update.effective_user)


def help_command(update: Update, context: CallbackContext) -> None:
    update.message.reply_text("Use /start to test this bot.")


def main(token):
    global job_queue
    updater = Updater(token, use_context=True)

    job_queue = updater.job_queue

    updater.dispatcher.add_handler(CommandHandler('start', start))
    updater.dispatcher.add_handler(CallbackQueryHandler(button))
    updater.dispatcher.add_handler(CommandHandler('help', help_command))

    updater.dispatcher.add_handler(MessageHandler(
        Filters.status_update.new_chat_members, start))

    # Start the Bot
    updater.start_polling()

    # Run the bot until the user presses Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT
    updater.idle()


if __name__ == '__main__':
    with open('TOKEN') as f:
        TOKEN = f.read()
    main(TOKEN)
