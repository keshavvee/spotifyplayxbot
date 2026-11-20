import asyncio
import html
import importlib
import logging
import queue
import threading
import traceback

try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

from pyrogram import idle
from pyrogram.enums import ParseMode
from pyrogram.errors import FloodWait
from pytgcalls.exceptions import NoActiveGroupCall

import config
from ShrutixMusic import LOGGER, nand, userbot
from ShrutixMusic.core.call import Shruti
from ShrutixMusic.logging import enqueue_error
from ShrutixMusic.misc import sudo
from ShrutixMusic.plugins import ALL_MODULES
from ShrutixMusic.utils.database import get_banned_users, get_gbanned
from config import BANNED_USERS


class _EndedCallNoiseFilter(logging.Filter):
    def filter(self, record):
        message = record.getMessage()
        return not ("SetVideoCallStatus" in message and "GROUPCALL_FORBIDDEN" in message)


logging.getLogger("asyncio").addFilter(_EndedCallNoiseFilter())


async def _error_forwarder():
    from ShrutixMusic.logging import ERROR_QUEUE
    from ShrutixMusic.utils.logger import send_log

    while True:
        try:
            title, text = await asyncio.to_thread(ERROR_QUEUE.get, True, 1.0)
        except queue.Empty:
            continue
        try:
            body = (
                f"<b>🚨 ʙᴏᴛ ᴇʀʀᴏʀ — {html.escape(title)}</b>\n\n"
                f"<pre>{html.escape(text[-3500:])}</pre>"
            )
            await send_log(body)
            await nand.send_message(
                config.OWNER_ID,
                body,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
        except FloodWait as exc:
            await asyncio.sleep(exc.value)
            try:
                ERROR_QUEUE.put_nowait((title, text))
            except Exception:
                pass
        except Exception:
            pass
        finally:
            ERROR_QUEUE.task_done()


async def _start_error_forwarder():
    loop = asyncio.get_running_loop()

    def _on_loop_error(loop, context):
        exc = context.get("exception")
        if exc is not None:
            text = "".join(
                traceback.format_exception(type(exc), exc, exc.__traceback__)
            )
        else:
            text = context.get("message") or "unhandled loop error"
        enqueue_error("ASYNCIO", text)

    def _on_thread_error(args):
        exc_type, exc, tb = args.exc_type, args.exc_value, args.exc_traceback
        if exc_type is None:
            enqueue_error("THREAD", str(exc))
            return
        enqueue_error("THREAD", "".join(traceback.format_exception(exc_type, exc, tb)))

    def _on_sys_error(exc_type, exc, tb):
        enqueue_error("SYSTEM", "".join(traceback.format_exception(exc_type, exc, tb)))

    loop.set_exception_handler(_on_loop_error)
    threading.excepthook = _on_thread_error
    sys.excepthook = _on_sys_error
    return asyncio.create_task(_error_forwarder())


async def init():
    if (
        not config.STRING1
        and not config.STRING2
        and not config.STRING3
        and not config.STRING4
        and not config.STRING5
    ):
        LOGGER(__name__).error("Assistant client variables not defined, exiting...")
        exit()
    await sudo()
    try:
        users = await get_gbanned()
        for user_id in users:
            BANNED_USERS.add(user_id)
        users = await get_banned_users()
        for user_id in users:
            BANNED_USERS.add(user_id)
    except:
        pass
    await nand.start()
    await _start_error_forwarder()
    for all_module in ALL_MODULES:
        importlib.import_module("ShrutixMusic.plugins" + all_module)
    LOGGER("ShrutixMusic.plugins").info("Successfully Imported Modules...")
    await userbot.start()
    await Shruti.start()
    try:
        await Shruti.stream_call("https://te.legra.ph/file/29f784eb49d230ab62e9e.mp4")
    except NoActiveGroupCall:
        LOGGER("ShrutixMusic").error(
            "Please turn on the videochat of your log group\\channel.\n\nStopping Bot..."
        )
        exit()
    except:
        pass
    await Shruti.decorators()
    try:
        from ShrutixMusic.platforms.Youtube import start_provider_monitor

        await start_provider_monitor()
    except Exception:
        pass
    LOGGER("ShrutixMusic").info(
    "\x53\x68\x72\x75\x74\x69\x78\x20\x4d\x75\x73\x69\x63\x20\x42\x6f\x74\x20\x53\x74\x61\x72\x74\x65\x64\x20\x53\x75\x63\x63\x65\x73\x73\x66\x75\x6c\x6c\x79\x2e\n\n\x44\x6f\x6e'\x74\x20\x66\x6f\x72\x67\x65\x74\x20\x74\x6f\x20\x76\x69\x73\x69\x74\x20\x40\x53\x68\x72\x75\x74\x69\x42\x6f\x74\x73"
)
    await idle()
    await nand.stop()
    await userbot.stop()
    LOGGER("ShrutixMusic").info("Stopping ShrutixMusic Music Bot...")


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(init())
