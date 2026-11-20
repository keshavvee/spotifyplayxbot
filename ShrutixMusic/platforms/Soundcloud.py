import asyncio
from os import path

from yt_dlp import YoutubeDL

from ShrutixMusic.utils.formatters import seconds_to_min


class SoundAPI:
    def __init__(self):
        self.opts = {
            "outtmpl": "downloads/%(id)s.%(ext)s",
            "format": "best",
            "retries": 3,
            "nooverwrites": False,
            "continuedl": True,
        }

    async def valid(self, link: str):
        if "soundcloud" in link:
            return True
        else:
            return False

    def _extract_sync(self, url, download=False):
        opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "retries": 3,
            "socket_timeout": 30,
            "format": "bestaudio[ext=m4a]/bestaudio/best",
        }
        if download:
            opts.update(self.opts)
        with YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=download)

    def _track_details(self, info, filepath):
        return {
            "title": info["title"],
            "duration_sec": info.get("duration") or 0,
            "duration_min": seconds_to_min(info.get("duration") or 0),
            "uploader": info.get("uploader") or "SoundCloud",
            "filepath": filepath,
        }

    async def stream(self, url):
        try:
            info = await asyncio.to_thread(self._extract_sync, url, False)
        except Exception:
            return False
        direct = info.get("url") if info else None
        if not direct:
            return False
        return self._track_details(info, direct), direct

    async def download(self, url):
        try:
            info = await asyncio.to_thread(self._extract_sync, url, True)
        except Exception:
            return False
        xyz = path.join("downloads", f"{info['id']}.{info['ext']}")
        return self._track_details(info, xyz), xyz
