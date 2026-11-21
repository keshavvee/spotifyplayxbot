import asyncio
from datetime import datetime, timedelta

from pyrogram.enums import ChatType

import config
from ShrutixMusic import nand
from ShrutixMusic.core.call import Shruti, autoend
from ShrutixMusic.utils.database import (
    get_client,
    group_assistant,
    is_active_chat,
    is_autoend,
)


async def auto_leave():
    if config.AUTO_LEAVING_ASSISTANT:
        while not await asyncio.sleep(900):
            from ShrutixMusic.core.userbot import assistants

            for num in assistants:
                client = await get_client(num)
                left = 0
                try:
                    async for i in client.get_dialogs():
                        if i.chat.type in [
                            ChatType.SUPERGROUP,
                            ChatType.GROUP,
                            ChatType.CHANNEL,
                        ]:
                            if (
                                i.chat.id != config.LOGGER_ID
                                and i.chat.id != -1001686672798
                                and i.chat.id != -1001549206010
                            ):
                                if left >= 20:
                                    break
                                if not await is_active_chat(i.chat.id):
                                    try:
                                        members = await client.get_call_members(i.chat.id)
                                        if members:
                                            continue
                                    except Exception:
                                        pass
                                    try:
                                        await client.leave_chat(i.chat.id)
                                        left += 1
                                    except:
                                        continue
                except:
                    pass


asyncio.create_task(auto_leave())


async def auto_end():
    while not await asyncio.sleep(5):
        ender = await is_autoend()
        if not ender:
            continue
        for chat_id in autoend:
            timer = autoend.get(chat_id)
            if not timer:
                continue
            if datetime.now() > timer:
                if not await is_active_chat(chat_id):
                    autoend[chat_id] = {}
                    continue
                # Re-check at expiry.  The timer is created when playback
                # starts; a listener may join afterwards, so the old timer
                # must never evict a live audience.
                try:
                    assistant = await group_assistant(Shruti, chat_id)
                    participants = await assistant.get_participants(chat_id)
                    listeners = len(participants)
                except Exception:
                    autoend[chat_id] = datetime.now() + timedelta(minutes=1)
                    continue
                if listeners > 1:
                    autoend[chat_id] = datetime.now() + timedelta(minutes=1)
                    continue
                # Confirm once more after a short grace period. This avoids
                # evicting a listener who joined while the old timer expired.
                await asyncio.sleep(2)
                try:
                    participants = await assistant.get_participants(chat_id)
                    listeners = len(participants)
                except Exception:
                    autoend[chat_id] = datetime.now() + timedelta(minutes=1)
                    continue
                if listeners > 1:
                    autoend[chat_id] = datetime.now() + timedelta(minutes=1)
                    continue
                autoend[chat_id] = {}
                try:
                    await Shruti.stop_stream(chat_id)
                except:
                    continue
                try:
                    await nand.send_message(
                        chat_id,
                        "» Playback stopped because no active listeners were detected. "
                        "If you were listening, please make the bot and assistant "
                        "administrators with Manage Video Chats and Invite Users "
                        "permissions, then run /play again.",
                    )
                except:
                    continue


asyncio.create_task(auto_end())
