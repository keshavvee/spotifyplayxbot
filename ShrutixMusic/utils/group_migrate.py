from pyrogram.errors import UserNotParticipant
from pyrogram.raw.functions.messages import MigrateChat

from ShrutixMusic.logging import LOGGER


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
    """Upgrade a basic group to a supergroup.

    The bot performs the migration: only the bot holds admin rights, and the
    assistant never needs anything beyond ordinary membership to stream.
    """
    try:
        updates = await bot.invoke(MigrateChat(chat_id=chat_id))
    except Exception as exc:
        LOGGER(__name__).warning("migration failed: %s", exc)
        return None, "migrate"

    new_id = _new_chat_id(updates)
    if not new_id:
        return None, "new_chat"

    # Pull the assistant into the new supergroup so /play works immediately.
    try:
        from ShrutixMusic.utils.database import get_assistant

        assistant = await get_assistant(new_id)
        try:
            member = await assistant.get_chat_member(new_id, assistant.id)
        except UserNotParticipant:
            member = None
        if member is None:
            link = await bot.export_chat_invite_link(new_id)
            if link.startswith("https://t.me/+"):
                link = link.replace("https://t.me/+", "https://t.me/joinchat/")
            await assistant.join_chat(link)
    except Exception as exc:
        LOGGER(__name__).warning("assistant join after migration failed: %s", exc)

    return new_id, None
