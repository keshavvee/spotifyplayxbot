import html
from pathlib import Path

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus, ChatType
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

import config
from ShrutixMusic import nand
from ShrutixMusic.logging import LOGGER
from ShrutixMusic.utils.database import (
    add_on,
    get_log_group,
    get_served_chats,
    get_served_users,
    remove_log_group,
    set_log_group,
)

OWNER = filters.user(config.OWNER_ID)
LOG_TYPES = (ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL)


def _panel():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Set This Group", callback_data="loggroup:set"),
                InlineKeyboardButton("Remove", callback_data="loggroup:remove"),
            ],
            [
                InlineKeyboardButton("View", callback_data="loggroup:view"),
                InlineKeyboardButton("Resend .txt", callback_data="loggroup:resend"),
            ],
            [InlineKeyboardButton("Close", callback_data="loggroup:close")],
        ]
    )


def _tail(path: Path, limit: int = 2500) -> str:
    if not path.is_file():
        return "log.txt not found."
    try:
        with path.open("rb") as handle:
            handle.seek(max(0, path.stat().st_size - 65536))
            data = handle.read().decode("utf-8", "replace")
    except OSError as exc:
        return f"Could not read log.txt: {exc}"
    return data[-limit:].strip() or "Log file is empty."


async def _summary() -> str:
    current = await get_log_group()
    users = len(await get_served_users())
    chats = len(await get_served_chats())
    path = Path("log.txt")
    size = round(path.stat().st_size / 1024, 1) if path.is_file() else 0
    return (
        "<b>🗂 ʟᴏɢ ɢʀᴏᴜᴘ</b>\n\n"
        f"<b>ᴄᴜʀʀᴇɴᴛ :</b> <code>{current or config.LOGGER_ID}</code>\n"
        f"<b>sᴛᴀᴛᴜs :</b> {'ᴄᴏɴғɪɢᴜʀᴇᴅ' if current else 'ᴅᴇғᴀᴜʟᴛ ʟᴏɢ ɢʀᴏᴜᴘ'}\n"
        f"<b>ᴛᴏᴛᴀʟ ᴜsᴇʀs :</b> <code>{users}</code>\n"
        f"<b>ᴛᴏᴛᴀʟ ɢʀᴏᴜᴘs :</b> <code>{chats}</code>\n"
        f"<b>ʟᴏɢ ғɪʟᴇ :</b> <code>{size} KB</code>"
    )


async def _view_text() -> str:
    text = await _summary()
    tail = _tail(Path("log.txt"), 1400)
    return f"{text}\n\n<b>📄 ʟᴀsᴛ ʟᴏɢ</b>\n<pre>{html.escape(tail)}</pre>"


async def _set(chat_id: int) -> bool:
    try:
        member = await nand.get_chat_member(chat_id, nand.id)
        if member.status not in (
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        ):
            try:
                await nand.send_message(
                    chat_id,
                    "<b>⚠️ ʙᴏᴛ ɴᴇᴇᴅs ᴀᴅᴍɪɴ ʀɪɢʜᴛs</b>\n\n"
                    "ᴘʀᴏᴍᴏᴛᴇ ᴛʜᴇ ʙᴏᴛ ɪɴ ᴛʜɪs ɢʀᴏᴜᴘ ᴛᴏ ʀᴇᴄᴇɪᴠᴇ ʟᴏɢs.",
                )
            except Exception:
                pass
            return False
    except Exception as exc:
        LOGGER(__name__).warning("log group admin check failed: %s", exc)
        return False
    await set_log_group(chat_id)
    await add_on(2)
    try:
        await nand.send_message(
            chat_id,
            "<b>✅ ʟᴏɢ ɢʀᴏᴜᴘ sᴇᴛ</b>\n\n"
            "ɴᴇᴡ ᴜsᴇʀs, ɢʀᴏᴜᴘ ᴀᴅᴅ/ʀᴇᴍᴏᴠᴇ ᴀɴᴅ sᴛʀᴇᴀᴍ ʟᴏɢs ᴡɪʟʟ ʙᴇ sᴇɴᴛ ʜᴇʀᴇ.",
        )
    except Exception as exc:
        LOGGER(__name__).warning("log group test message failed: %s", exc)
    return True


@nand.on_message(filters.command(["loggroup"]) & OWNER)
async def loggroup_cmd(_, message):
    args = message.text.split()[1:]
    action = args[0].lower() if args else "view"
    if action == "set":
        if len(args) > 1:
            try:
                chat_id = int(args[1])
            except ValueError:
                return await message.reply_text("Chat ID must be numeric.")
        elif message.chat.type in LOG_TYPES:
            chat_id = message.chat.id
        else:
            return await message.reply_text(
                "Run <code>/loggroup set</code> inside the target group, "
                "or use <code>/loggroup set -1001234567890</code>."
            )
        if not await _set(chat_id):
            return await message.reply_text(
                "Log group was not set. Promote the bot to admin in that chat and retry.",
                reply_markup=_panel(),
            )
        return await message.reply_text(
            f"<b>✅ ʟᴏɢ ɢʀᴏᴜᴘ sᴇᴛ</b>\n<code>{chat_id}</code>",
            reply_markup=_panel(),
        )
    if action == "remove":
        await remove_log_group()
        return await message.reply_text(
            "<b>✅ ʟᴏɢ ɢʀᴏᴜᴘ ʀᴇᴍᴏᴠᴇᴅ</b>\n\n"
            f"Fallback log group: <code>{config.LOGGER_ID}</code>",
            reply_markup=_panel(),
        )
    if action == "tail":
        path = Path("log.txt")
        return await message.reply_text(
            f"<b>📄 ʟᴏɢ ᴛᴀɪʟ</b>\n<pre>{html.escape(_tail(path, 3500))}</pre>",
            reply_markup=_panel(),
        )
    if action == "resend":
        path = Path("log.txt")
        if not path.is_file():
            return await message.reply_text("log.txt not found.")
        target = await get_log_group()
        if target:
            try:
                await nand.send_document(
                    target,
                    document=str(path),
                    caption="<b>📄 ʙᴏᴛ ʟᴏɢ</b>",
                    file_name="bot-log.txt",
                )
            except Exception as exc:
                LOGGER(__name__).warning("log resend to group failed: %s", exc)
        return await message.reply_document(
            document=str(path),
            caption="<b>📄 ʙᴏᴛ ʟᴏɢ</b>",
            file_name="bot-log.txt",
        )
    if action == "view":
        return await message.reply_text(await _view_text(), reply_markup=_panel())
    text = await _summary()
    return await message.reply_text(text, reply_markup=_panel())


@nand.on_callback_query(filters.regex(r"^loggroup:") & OWNER)
async def loggroup_callback(_, query):
    action = query.data.split(":", 1)[1]
    if action == "close":
        await query.message.delete()
        return await query.answer()
    if action == "set":
        if query.message.chat.type not in LOG_TYPES:
            return await query.answer(
                "Run /loggroup set inside the group you want to use.",
                show_alert=True,
            )
        if not await _set(query.message.chat.id):
            return await query.answer(
                "Promote the bot to admin in this chat first.",
                show_alert=True,
            )
        await query.answer("Log group set.", show_alert=True)
        return await query.message.edit_text(await _summary(), reply_markup=_panel())
    if action == "remove":
        await remove_log_group()
        await query.answer("Log group removed.", show_alert=True)
        return await query.message.edit_text(await _summary(), reply_markup=_panel())
    if action == "resend":
        path = Path("log.txt")
        if not path.is_file():
            return await query.answer("log.txt not found.", show_alert=True)
        target = await get_log_group()
        if target:
            try:
                await nand.send_document(
                    target,
                    document=str(path),
                    caption="<b>📄 ʙᴏᴛ ʟᴏɢ</b>",
                    file_name="bot-log.txt",
                )
            except Exception as exc:
                LOGGER(__name__).warning("log resend to group failed: %s", exc)
        await query.message.reply_document(
            document=str(path),
            caption="<b>📄 ʙᴏᴛ ʟᴏɢ</b>",
            file_name="bot-log.txt",
        )
        return await query.answer("Log file sent.")
    if action == "view":
        await query.answer()
        return await query.message.edit_text(await _view_text(), reply_markup=_panel())
    await query.answer()
