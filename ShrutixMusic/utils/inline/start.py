import config
from pyrogram.enums import ButtonStyle
from pyrogram.types import InlineKeyboardButton

from ShrutixMusic import nand

GROUP_ADD = "https://t.me/{username}?startgroup=true&admin=invite_users+delete_messages+manage_video_chats+pin_messages+manage_chat+ban_users+manage_topics+change_info"


def _add_url():
    return GROUP_ADD.format(username=nand.username)


def start_panel(_):
    return [
        [
            InlineKeyboardButton(
                text=_["S_B_1"],
                url=_add_url(),
                style=ButtonStyle.PRIMARY,
            ),
            InlineKeyboardButton(
                text=_["S_B_2"],
                url=config.SUPPORT_CHAT,
                style=ButtonStyle.PRIMARY,
            ),
        ],
    ]


def private_panel(_):
    return [
        [
            InlineKeyboardButton(
                text=_["S_B_3"],
                url=_add_url(),
                style=ButtonStyle.PRIMARY,
            )
        ],
        [
            InlineKeyboardButton(
                text=_["S_B_6"],
                user_id=config.OWNER_ID,
                style=ButtonStyle.DANGER,
            ),
            InlineKeyboardButton(
                text=_["S_B_5"],
                url=config.SUPPORT_CHANNEL,
                style=ButtonStyle.SUCCESS,
            ),
        ],
        [
            InlineKeyboardButton(
                text=_["S_B_4"],
                callback_data="settings_back_helper",
                style=ButtonStyle.SUCCESS,
            )
        ],
    ]
