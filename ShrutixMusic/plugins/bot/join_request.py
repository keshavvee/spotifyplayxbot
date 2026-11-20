import html

from pyrogram.enums import ButtonStyle, ParseMode
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from ShrutixMusic import nand
from ShrutixMusic.logging import LOGGER
from ShrutixMusic.utils.database import add_served_user, get_served_users
from ShrutixMusic.utils.logger import send_log
from config import START_IMG_URL


@nand.on_chat_join_request()
async def join_request_welcome(client, request):
    title = html.escape((request.chat.title or "the group").strip())
    caption = (
        "ʜᴇʟʟᴏ,\n\n"
        f"ᴛʜᴀɴᴋ ʏᴏᴜ ꜰᴏʀ sᴇɴᴅɪɴɢ ᴀ ʀᴇǫᴜᴇsᴛ ᴛᴏ ᴊᴏɪɴ <b>{title}</b>.\n\n"
        "ᴡᴇ’ᴠᴇ ʀᴇᴄᴇɪᴠᴇᴅ ɪᴛ ᴀɴᴅ ᴀʀᴇ ɢʟᴀᴅ ᴛᴏ sᴇᴇ ʏᴏᴜ ʜᴇʀᴇ. "
        "ᴏᴜʀ ᴀᴅᴍɪɴs ᴡɪʟʟ ʀᴇᴠɪᴇᴡ ʏᴏᴜʀ ʀᴇǫᴜᴇsᴛ sʜᴏʀᴛʟʏ "
        "ᴀɴᴅ ᴀᴘᴘʀᴏᴠᴇ ɪᴛ ᴀs sᴏᴏɴ ᴀs ᴘᴏssɪʙʟᴇ.\n\n"
        "ɪɴ ᴛʜᴇ ᴍᴇᴀɴᴛɪᴍᴇ, ʏᴏᴜ’ʀᴇ ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ᴇxᴘʟᴏʀᴇ ᴛʜᴇ ʙᴏᴛ "
        "ᴀɴᴅ ᴅɪsᴄᴏᴠᴇʀ ᴡʜᴀᴛ ɪᴛ ᴄᴀɴ ᴅᴏ ꜰᴏʀ ʏᴏᴜ.\n\n"
        "✦ ᴛᴀᴘ ʙᴇʟᴏᴡ ᴛᴏ sᴛᴀʀᴛ ✦"
    )
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✦ ᴛᴀᴘ ʜᴇʀᴇ ᴛᴏ sᴛᴀʀᴛ ✦",
                    url=f"https://t.me/{nand.username}?start=start",
                    style=ButtonStyle.DANGER,
                )
            ]
        ]
    )
    try:
        await client.send_photo(
            chat_id=request.from_user.id,
            photo=START_IMG_URL,
            caption=caption,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
        )
        await add_served_user(request.from_user.id)
        total_users = len(await get_served_users())
        await send_log(
            "<b>👤 ɴᴇᴡ ᴜsᴇʀ ғʀᴏᴍ ᴊᴏɪɴ ʀᴇǫᴜᴇsᴛ</b>\n\n"
            f"<b>ɴᴀᴍᴇ :</b> {request.from_user.mention}\n"
            f"<b>ᴜsᴇʀ ɪᴅ :</b> <code>{request.from_user.id}</code>\n"
            f"<b>ᴄʜᴀᴛ :</b> {html.escape(request.chat.title or 'the group')}\n"
            f"<b>ᴄʜᴀᴛ ɪᴅ :</b> <code>{request.chat.id}</code>\n"
            f"<b>ᴛᴏᴛᴀʟ ᴜsᴇʀs :</b> <code>{total_users}</code>"
        )
    except Exception as exc:
        LOGGER(__name__).exception(
            "join request welcome failed for %s: %s",
            request.from_user.id,
            exc,
        )
