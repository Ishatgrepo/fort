import re
import asyncio 
from .utils import STS
from database import db
from config import temp 
from translation import Translation
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait 
from pyrogram.errors.exceptions.not_acceptable_406 import ChannelPrivate as PrivateChat
from pyrogram.errors.exceptions.bad_request_400 import ChannelInvalid, ChatAdminRequired, UsernameInvalid, UsernameNotModified, ChannelPrivate
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove

@Client.on_message(filters.private & filters.command(["fwd", "forward"]))
async def run(bot, message):
    user_id = message.from_user.id
    bots = await db.get_bots(user_id)
    if not bots:
        return await message.reply("<code>You didn't add any bots. Please add a bot using /settings!</code>")

    # Select target channel
    channels = await db.get_user_channels(user_id)
    if not channels:
        return await message.reply_text("Please set a target channel in /settings before forwarding")
    
    buttons = []
    btn_data = {}
    if len(channels) > 1:
        for channel in channels:
            buttons.append([KeyboardButton(f"{channel['title']}")])
            btn_data[channel['title']] = channel['chat_id']
        buttons.append([KeyboardButton("cancel")]) 
        _toid = await bot.ask(message.chat.id, Translation.TO_MSG.format("Multiple Bots", "N/A"), reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True))
        if _toid.text.startswith(('/', 'cancel')):
            return await message.reply_text(Translation.CANCEL, reply_markup=ReplyKeyboardRemove())
        to_title = _toid.text
        toid = btn_data.get(to_title)
        if not toid:
            return await message.reply_text("Wrong channel chosen!", reply_markup=ReplyKeyboardRemove())
    else:
        toid = channels[0]['chat_id']
        to_title = channels[0]['title']

    # Get multiple source chats
    await message.reply("Send multiple source chat links or forward messages (one per line). When done, send '/done'.")
    source_chats = []
    while True:
        fromid = await bot.ask(message.chat.id, Translation.FROM_MSG, reply_markup=ReplyKeyboardRemove())
        if fromid.text == '/done':
            break
        elif fromid.text and fromid.text.startswith('/'):
            await message.reply(Translation.CANCEL)
            return 
        elif fromid.text and not fromid.forward_date:
            regex = re.compile(r"(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$")
            match = regex.match(fromid.text.replace("?single", ""))
            if not match:
                await message.reply('Invalid link')
                continue
            chat_id = match.group(4)
            last_msg_id = int(match.group(5))
            if chat_id.isnumeric():
                chat_id = int(("-100" + chat_id))
            source_chats.append((chat_id, last_msg_id))
        elif fromid.forward_from_chat and fromid.forward_from_chat.type in [enums.ChatType.CHANNEL]:
            last_msg_id = fromid.forward_from_message_id
            chat_id = fromid.forward_from_chat.username or fromid.forward_from_chat.id
            if last_msg_id is None:
                await message.reply_text("**This may be a forwarded message from a group by an anonymous admin. Send the last message link instead.**")
                continue
            source_chats.append((chat_id, last_msg_id))
        else:
            await message.reply_text("**Invalid input!**")
            continue

    if not source_chats:
        return await message.reply("No valid source chats provided!")

    # Get skip number
    skipno = await bot.ask(message.chat.id, Translation.SKIP_MSG)
    if skipno.text.startswith('/'):
        await message.reply(Translation.CANCEL)
        return

    # Assign bots to source chats
    if len(bots) < len(source_chats):
        await message.reply(f"You have {len(bots)} bots, but provided {len(source_chats)} source chats. Using available bots cyclically.")
    
    tasks = []
    for idx, (chat_id, last_msg_id) in enumerate(source_chats):
        bot_choice = bots[idx % len(bots)]  # Cycle through available bots
        forward_id = f"{user_id}-{skipno.id}-{bot_choice['id']}-{idx}"
        try:
            title = (await bot.get_chat(chat_id)).title
        except (PrivateChat, ChannelPrivate, ChannelInvalid):
            title = "private"
        except (UsernameInvalid, UsernameNotModified):
            return await message.reply('Invalid Link specified.')
        except Exception as e:
            return await message.reply(f'Errors - {e}')

        buttons = [[
            InlineKeyboardButton('Yes', callback_data=f"start_public_{forward_id}"),
            InlineKeyboardButton('No', callback_data="close_btn")
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await message.reply_text(
            text=Translation.DOUBLE_CHECK.format(botname=bot_choice['name'], botuname=bot_choice['username'], from_chat=title, to_chat=to_title, skip=skipno.text),
            disable_web_page_preview=True,
            reply_markup=reply_markup
        )
        STS(forward_id).store(chat_id, toid, int(skipno.text), int(last_msg_id), bot_choice)
        tasks.append(forward_id)

    await message.reply(f"Initialized {len(tasks)} forwarding tasks. Confirm each task to start.")
