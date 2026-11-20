from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import UserNotParticipant
from pyrogram.raw.functions.messages import MigrateChat
from pyrogram.types import ChatPrivileges

from ShrutixMusic.logging import LOGGER


def _is_admin(member) -> bool:
    if member is None:
        return False
    if getattr(member, "status", None) == ChatMemberStatus.OWNER:
        return True
    return getattr(member, "status", None) == ChatMemberStatus.ADMINISTRATOR


def _new_chat_id(updates):
    new_id = None
    for chat in getattr(updates, "chats", None) or []:
        if getattr(chat, "megagroup", False):
            new_id = getattr(chat, "id", None)
            break
        migrated = getattr(chat, "migrated_to", None)
        if migrated is not None:
            new_id = getattr(migrated, "channel_id", None)
            break
    if new_id and new_id > 0:
        return int(f"-100{new_id}")
    return new_id


async def migrate_basic_group(chat_id: int, bot):
    from ShrutixMusic.utils.database import get_assistant

    try:
        assistant = await get_assistant(chat_id)
    except Exception as exc:
        LOGGER(__name__).warning("migration assistant lookup failed: %s", exc)
        return None, "assistant"

    try:
        member = await assistant.get_chat_member(chat_id, assistant.id)
    except UserNotParticipant:
        try:
            link = await bot.export_chat_invite_link(chat_id)
            if link.startswith("https://t.me/+"):
                link = link.replace("https://t.me/+", "https://t.me/joinchat/")
            await assistant.join_chat(link)
            member = await assistant.get_chat_member(chat_id, assistant.id)
        except Exception as exc:
            LOGGER(__name__).warning("migration assistant join failed: %s", exc)
            return None, "assistant_join"
    except Exception as exc:
        LOGGER(__name__).warning("migration member lookup failed: %s", exc)
        return None, "member"

    if not _is_admin(member):
        try:
            await bot.promote_chat_member(
                chat_id,
                assistant.id,
                privileges=ChatPrivileges(can_invite_users=True),
            )
            member = await assistant.get_chat_member(chat_id, assistant.id)
        except Exception as exc:
            LOGGER(__name__).warning("migration assistant promote failed: %s", exc)
            return None, "assistant_admin"
        if not _is_admin(member):
            return None, "assistant_admin"

    try:
        updates = await assistant.invoke(MigrateChat(chat_id=chat_id))
    except Exception as exc:
        LOGGER(__name__).warning("migration failed: %s", exc)
        return None, "migrate"

    new_id = _new_chat_id(updates)
    if not new_id:
        return None, "new_chat"
    return new_id, None
