import html
import os
import shutil
import time
from datetime import datetime
from pathlib import Path

import psutil
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

import config
from ShrutixMusic import nand
from ShrutixMusic.core.call import Shruti
from ShrutixMusic.core.userbot import assistants
from ShrutixMusic.misc import _boot_, mongodb
from ShrutixMusic.platforms.Youtube import (
    provider_snapshot,
    set_provider_order,
    test_providers,
)
from ShrutixMusic.plugins import ALL_MODULES
from ShrutixMusic.utils import bot_sys_stats
from ShrutixMusic.utils.database import (
    get_active_chats,
    get_active_video_chats,
    get_banned_count,
    get_served_chats,
    get_served_users,
    get_sudoers,
    is_active_chat,
    is_active_video_chat,
)
from ShrutixMusic.utils.formatters import get_readable_time

OWNER = filters.user(config.OWNER_ID)


def _close_markup():
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Close", callback_data="close")]]
    )


def _esc(value):
    return html.escape(str(value), quote=False)


def _provider_line(kind, rows, now):
    parts = []
    for row in rows:
        cooling = row["until"] - now
        status = f"cool {cooling:.0f}s" if cooling > 0 else "ready"
        ewma = f"{row['ewma']:.2f}s" if row["ewma"] is not None else "n/a"
        parts.append(f"{row['name']}: {ewma} | fails {row['fails']} | {status}")
    return f"<b>{kind}</b>: " + " → ".join(parts)


@nand.on_message(filters.command(["health", "diag"]) & OWNER)
async def owner_health(_, message: Message):
    checks = []
    checks.append(f"Bot: {_esc(nand.name)} (@{_esc(nand.username)})")
    checks.append(f"Uptime: {get_readable_time(int(time.time() - _boot_))}")
    try:
        started = time.perf_counter()
        await mongodb.command("ping")
        checks.append(f"Database: OK ({round((time.perf_counter() - started) * 1000, 1)} ms)")
    except Exception as exc:
        checks.append(f"Database: FAIL ({_esc(type(exc).__name__)})")
    connected = sum(1 for item in assistants if getattr(item, "is_connected", False))
    checks.append(f"Assistants: {connected}/{len(assistants)} connected")
    try:
        checks.append(f"PyTgCalls: {await Shruti.ping()} ms")
    except Exception as exc:
        checks.append(f"PyTgCalls: FAIL ({_esc(type(exc).__name__)})")
    checks.append(f"FFmpeg: {'found' if shutil.which('ffmpeg') else 'missing'}")
    try:
        now = time.monotonic()
        snapshot = provider_snapshot()
        for kind in ("audio", "video"):
            checks.append(_provider_line(kind, snapshot[kind], now))
    except Exception as exc:
        checks.append(f"Providers: FAIL ({_esc(type(exc).__name__)})")
    checks.append(f"Disk: {psutil.disk_usage('/').percent}%")
    checks.append(f"CPU: {psutil.cpu_percent(interval=0.2)}%")
    checks.append(f"RAM: {psutil.virtual_memory().percent}%")
    try:
        checks.append(f"Active VC: {len(await get_active_chats())}")
        checks.append(f"Active video: {len(await get_active_video_chats())}")
    except Exception as exc:
        checks.append(f"Streams: FAIL ({_esc(type(exc).__name__)})")
    await message.reply_text(
        "<b>🩺 BOT HEALTH</b>\n\n" + "\n".join(f"• {line}" for line in checks),
        reply_markup=_close_markup(),
    )


@nand.on_message(filters.command(["globalstats", "gstats_owner"]) & OWNER)
async def owner_globalstats(_, message: Message):
    served_chats = len(await get_served_chats())
    served_users = len(await get_served_users())
    active_vc = len(await get_active_chats())
    active_video = len(await get_active_video_chats())
    sudoers = len(await get_sudoers())
    banned = await get_banned_count()
    uptime, cpu, ram, disk = await bot_sys_stats()
    db_line = "unavailable"
    try:
        stats = await mongodb.command("dbstats")
        data_size = round(stats["dataSize"] / 1024, 1)
        storage_size = round(stats["storageSize"] / 1024, 1)
        db_line = f"{data_size} KB data / {storage_size} KB storage"
    except Exception:
        pass
    text = (
        "<b>🌐 GLOBAL STATS</b>\n\n"
        f"• Bot: {_esc(nand.mention)}\n"
        f"• Uptime: {uptime}\n"
        f"• Users: <code>{served_users}</code>\n"
        f"• Chats: <code>{served_chats}</code>\n"
        f"• Active VC: <code>{active_vc}</code>\n"
        f"• Active video: <code>{active_video}</code>\n"
        f"• Sudoers: <code>{sudoers}</code>\n"
        f"• Blocked: <code>{banned}</code>\n"
        f"• Modules: <code>{len(ALL_MODULES)}</code>\n"
        f"• CPU: {cpu} | RAM: {ram} | Disk: {disk}\n"
        f"• Database: {_esc(db_line)}"
    )
    await message.reply_text(text, reply_markup=_close_markup())


@nand.on_message(filters.command(["provider", "providerstatus"]) & OWNER)
async def owner_provider(_, message: Message):
    args = message.text.split()[1:]
    action = args[0].lower() if args else "status"
    if action in ("status", "show"):
        now = time.monotonic()
        snapshot = provider_snapshot()
        text = (
            "<b>🎛 PROVIDER STATUS</b>\n\n"
            + _provider_line("audio", snapshot["audio"], now)
            + "\n"
            + _provider_line("video", snapshot["video"], now)
            + "\n\n<b>Usage</b>\n"
            "• <code>/provider test</code>\n"
            "• <code>/provider audio api|ytdlp</code>\n"
            "• <code>/provider video api|ytdlp</code>"
        )
        return await message.reply_text(text, reply_markup=_close_markup())
    if action == "test":
        status = await message.reply_text("<b>Testing providers...</b>")
        results = await test_providers()
        now = time.monotonic()
        lines = ["<b>🧪 PROVIDER TEST</b>"]
        for kind in ("audio", "video"):
            for provider in ("api", "ytdlp"):
                seconds = results[kind][provider]
                lines.append(
                    f"• <b>{kind}/{provider}</b>: "
                    + (f"{seconds:.2f}s" if seconds is not None else "FAILED")
                )
        lines.append("")
        lines.append(_provider_line("audio", provider_snapshot()["audio"], now))
        lines.append(_provider_line("video", provider_snapshot()["video"], now))
        return await status.edit_text("\n".join(lines), reply_markup=_close_markup())
    if action in ("audio", "video") and len(args) >= 2:
        provider = args[1].lower()
        if provider not in ("api", "ytdlp"):
            return await message.reply_text("Provider must be <code>api</code> or <code>ytdlp</code>.")
        set_provider_order(action, provider)
        return await message.reply_text(
            f"<b>{action}</b> order set: <b>{provider}</b> first."
        )
    await message.reply_text(
        "Usage:\n<code>/provider status</code>\n"
        "<code>/provider test</code>\n"
        "<code>/provider audio api|ytdlp</code>\n"
        "<code>/provider video api|ytdlp</code>"
    )


@nand.on_message(filters.command(["killstream", "killvc"]) & OWNER)
async def owner_killstream(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text(
            "Usage: <code>/killstream -1001234567890</code>"
        )
    try:
        chat_id = int(message.command[1])
    except ValueError:
        return await message.reply_text("Chat ID must be numeric.")
    active = await is_active_chat(chat_id) or await is_active_video_chat(chat_id)
    await Shruti.stop_stream_force(chat_id)
    suffix = "" if active else " (was not marked active)"
    await message.reply_text(
        f"Stream killed in <code>{chat_id}</code>{suffix}.",
        reply_markup=_close_markup(),
    )


@nand.on_message(filters.command(["clearcache", "cacheclear"]) & OWNER)
async def owner_clearcache(_, message: Message):
    status = await message.reply_text("<b>Clearing cache...</b>")
    total = 0
    count = 0
    for name in ("downloads", "raw_files", "cache", "playback"):
        path = Path(name)
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            continue
        for item in path.rglob("*"):
            if item.is_file():
                try:
                    total += item.stat().st_size
                    count += 1
                except OSError:
                    pass
        for item in list(path.iterdir()):
            try:
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
            except OSError:
                pass
    await status.edit_text(
        f"<b>🧹 CACHE CLEARED</b>\n\n"
        f"• Files removed: <code>{count}</code>\n"
        f"• Space freed: <code>{round(total / (1024 * 1024), 2)} MB</code>",
        reply_markup=_close_markup(),
    )


@nand.on_message(filters.command(["trace", "lasterror"]) & OWNER)
async def owner_trace(_, message: Message):
    path = Path("log.txt")
    if not path.is_file():
        return await message.reply_text("log.txt not found.")
    try:
        with path.open("rb") as handle:
            handle.seek(max(0, path.stat().st_size - 262144))
            lines = handle.read().decode("utf-8", "replace").splitlines()
    except OSError as exc:
        return await message.reply_text(f"Could not read log.txt: <code>{_esc(exc)}</code>")
    start = None
    for index in range(len(lines) - 1, -1, -1):
        if "Traceback (most recent call last):" in lines[index]:
            start = index
            break
    if start is None:
        selected = [line for line in lines if "ERROR" in line or "CRITICAL" in line][-25:]
        title = "LAST ERRORS"
    else:
        selected = lines[start:][-80:]
        title = "LAST TRACEBACK"
    body = "\n".join(selected).strip() or "No errors found in the recent log."
    body = body[-3500:]
    await message.reply_text(
        f"<b>🧾 {title}</b>\n<pre>{_esc(body)}</pre>",
        reply_markup=_close_markup(),
    )


@nand.on_message(filters.command(["ownerhelp", "sudohelp"]) & OWNER)
async def owner_help(_, message: Message):
    text = (
        "<b>👑 OWNER PANEL</b>\n\n"
        "<b>Diagnostics</b>\n"
        "/health — system and stream health\n"
        "/globalstats — users, chats, DB and streams\n"
        "/trace — last traceback from log.txt\n\n"
        "<b>Providers & streams</b>\n"
        "/provider status\n"
        "/provider test\n"
        "/provider audio api|ytdlp\n"
        "/provider video api|ytdlp\n"
        "/killstream &lt;chat_id&gt;\n"
        "/activevc | /activev\n\n"
        "<b>Maintenance</b>\n"
        "/clearcache\n"
        "/logs | /restart | /update\n\n"
        "<b>Users & chats</b>\n"
        "/broadcast | /block | /unblock | /blocked\n"
        "/gban | /ungban | /gbanlist\n"
        "/blchat | /whitelistchat | /blchats\n\n"
        "<b>Sudo & runtime</b>\n"
        "/addsudo | /delsudo | /sudolist\n"
        "/eval | /sh\n"
        "/maintenance | /logger | /autoend"
    )
    await message.reply_text(text, reply_markup=_close_markup())
