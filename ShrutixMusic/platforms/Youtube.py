import asyncio
import glob
import os
import time
import re
import urllib.parse
from typing import Union
import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from py_yt import VideosSearch, Playlist
import aiohttp

API_URL = os.environ.get("SHRUTI_API_URL", "https://api.shrutibots.in")

API_KEY = os.environ.get("SHRUTI_API_KEY", "YOUR_API_KEY") ## Get This API KEY FROM https://dash.shrutibots.in

DOWNLOAD_DIR = "downloads"

_DOWNLOAD_GATE = asyncio.Semaphore(int(os.getenv("MAX_CONCURRENT_DOWNLOADS", "3")))
_PROVIDER_TEST_ID = os.getenv("PROVIDER_TEST_VIDEO_ID", "BddP6PYo2gs")
_PROVIDER_RETEST_SECONDS = int(os.getenv("PROVIDER_RETEST_SECONDS", "900"))
_PROVIDER_COOLDOWN_SECONDS = int(os.getenv("PROVIDER_COOLDOWN_SECONDS", "300"))
_PROVIDER_DEFAULT_ORDER = {"audio": ["api", "ytdlp"], "video": ["ytdlp", "api"]}
_PROVIDER_STATS = {
    "audio": {"api": {"ewma": None, "fails": 0, "until": 0.0}, "ytdlp": {"ewma": None, "fails": 0, "until": 0.0}},
    "video": {"ytdlp": {"ewma": None, "fails": 0, "until": 0.0}, "api": {"ewma": None, "fails": 0, "until": 0.0}},
}
_PROVIDER_LOCK = asyncio.Lock()
_PROVIDER_MONITOR_TASK = None


def _env_dir(name: str) -> str:
    value = os.environ.get(name, "").strip()
    return os.path.abspath(os.path.expanduser(value)) if value else ""


AUDIO_DOWNLOAD_PATH = _env_dir("AUDIO_DOWNLOAD_PATH")
VIDEO_DOWNLOAD_PATH = _env_dir("VIDEO_DOWNLOAD_PATH")
AUDIO_EXTENSIONS = ("webm", "m4a", "mp3", "ogg")
VIDEO_EXTENSIONS = ("mp4", "mkv", "webm")


def is_external_path(path) -> bool:
    if not path:
        return False
    full = os.path.abspath(str(path))
    for base in (AUDIO_DOWNLOAD_PATH, VIDEO_DOWNLOAD_PATH):
        if base and full.startswith(base + os.sep):
            return True
    return False


def _find_external(directory: str, video_id: str, extensions, resp=None):
    names = []
    if resp is not None:
        disposition = resp.content_disposition
        if disposition and disposition.filename:
            name = os.path.basename(disposition.filename)
            if name.startswith(video_id + "."):
                names.append(name)
    names.extend(f"{video_id}.{ext}" for ext in extensions)
    for name in names:
        path = os.path.join(directory, name)
        if os.path.isfile(path) and os.path.getsize(path) > 0:
            return path
    return None


def time_to_seconds(time):
    stringt = str(time)
    return sum(int(x) * 60 ** i for i, x in enumerate(reversed(stringt.split(":"))))


async def _download_media(link: str, kind: str, timeout: int) -> str:
    async with _DOWNLOAD_GATE:
        return await _download_media_inner(link, kind, timeout)


async def _download_media_inner(link: str, kind: str, timeout: int) -> str:
    video_id = link.split("v=")[-1].split("&")[0] if "v=" in link else link
    if not video_id or len(video_id) < 3:
        return None

    is_audio = kind == "audio"
    external = AUDIO_DOWNLOAD_PATH if is_audio else VIDEO_DOWNLOAD_PATH
    extensions = AUDIO_EXTENSIONS if is_audio else VIDEO_EXTENSIONS

    if external:
        found = _find_external(external, video_id, extensions)
        if found:
            return found

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    file_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.{'mp3' if is_audio else 'mp4'}")
    if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
        return file_path

    base = (API_URL or "").strip().rstrip("/")
    key = (API_KEY or "").strip()
    api_ready = bool("riteshyt" in base and key and key != "YOUR_API_KEY")
    order = _provider_order(kind, api_ready)
    for provider in order:
        started = time.monotonic()
        try:
            if provider == "api":
                result = await _download_api(video_id, kind, timeout, file_path, external, extensions, base, key)
            else:
                result = await _ytdlp_fallback(video_id, kind, timeout)
        except Exception:
            result = None
        if result:
            await _record_provider(kind, provider, True, time.monotonic() - started)
            return result
        await _record_provider(kind, provider, False, time.monotonic() - started)
    return None


async def _download_api(video_id, kind, timeout, file_path, external, extensions, base, key):
    if not ("riteshyt" in base and key and key != "YOUR_API_KEY"):
        return None
    ext = "mp3" if kind == "audio" else "mp4"
    direct = f"{base}/downloads/{key}/{video_id}.{ext}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(direct, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                if resp.status != 200:
                    return None
                if external:
                    found = _find_external(external, video_id, extensions, resp)
                    if found:
                        return found
                with open(file_path, "wb") as f:
                    async for chunk in resp.content.iter_chunked(131072):
                        f.write(chunk)
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            return file_path
    except Exception:
        pass
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception:
        pass
    return None


def _provider_order(kind, api_ready=False):
    now = time.monotonic()
    stats = _PROVIDER_STATS[kind]
    names = list(_PROVIDER_DEFAULT_ORDER[kind])
    if not api_ready and "api" in names:
        names.remove("api")
    def key(name):
        st = stats[name]
        cooling = 1 if st["until"] > now else 0
        default_score = 3.0 if name == _PROVIDER_DEFAULT_ORDER[kind][0] else 5.0
        score = default_score if kind == "video" else (st["ewma"] if st["ewma"] is not None else default_score)
        return (cooling, score + min(st["fails"], 5) * 2)
    return sorted(names, key=key)


async def _record_provider(kind, provider, ok, seconds):
    async with _PROVIDER_LOCK:
        st = _PROVIDER_STATS[kind][provider]
        if ok:
            st["ewma"] = seconds if st["ewma"] is None else (st["ewma"] * 0.7 + seconds * 0.3)
            st["fails"] = 0
            st["until"] = 0.0
        else:
            st["fails"] += 1
            if st["fails"] >= 2:
                st["until"] = time.monotonic() + _PROVIDER_COOLDOWN_SECONDS


async def _probe_api(kind, timeout=30):
    base = (API_URL or "").strip().rstrip("/")
    key = (API_KEY or "").strip()
    if not ("riteshyt" in base and key and key != "YOUR_API_KEY"):
        return None
    ext = "mp3" if kind == "audio" else "mp4"
    started = time.monotonic()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{base}/downloads/{key}/{_PROVIDER_TEST_ID}.{ext}",
                headers={"Range": "bytes=0-65535"},
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                data = await resp.content.read(65536)
                if resp.status in (200, 206) and data:
                    return time.monotonic() - started
    except Exception:
        pass
    return None


def _probe_ytdlp_sync(kind, timeout=30):
    fmt = "bestaudio[ext=m4a]/bestaudio/best" if kind == "audio" else "bestvideo[height<=480]+bestaudio/best[height<=480]/best"
    started = time.monotonic()
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "noplaylist": True, "format": fmt}) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={_PROVIDER_TEST_ID}", download=False)
        if not info or not info.get("url"):
            return None
        return time.monotonic() - started
    except Exception:
        return None


async def _probe_provider(kind, provider):
    if provider == "api":
        return await _probe_api(kind)
    return await asyncio.to_thread(_probe_ytdlp_sync, kind)


def provider_snapshot():
    now = time.monotonic()
    result = {}
    for kind in ("audio", "video"):
        rows = []
        for name in _PROVIDER_DEFAULT_ORDER[kind]:
            stats = _PROVIDER_STATS[kind][name]
            rows.append(
                {
                    "name": name,
                    "ewma": stats["ewma"],
                    "fails": stats["fails"],
                    "until": stats["until"],
                    "cooling": max(0.0, stats["until"] - now),
                }
            )
        result[kind] = rows
    return result


def set_provider_order(kind, first):
    if kind not in _PROVIDER_DEFAULT_ORDER:
        raise ValueError("unknown media kind")
    if first not in _PROVIDER_DEFAULT_ORDER[kind]:
        raise ValueError("unknown provider")
    _PROVIDER_DEFAULT_ORDER[kind] = [first] + [
        name for name in _PROVIDER_DEFAULT_ORDER[kind] if name != first
    ]
    return list(_PROVIDER_DEFAULT_ORDER[kind])


async def test_providers():
    results = {"audio": {}, "video": {}}
    for kind in ("audio", "video"):
        for provider in ("api", "ytdlp"):
            result = await _probe_provider(kind, provider)
            await _record_provider(kind, provider, result is not None, result or 0.0)
            results[kind][provider] = result
    return results


async def _provider_monitor():
    while True:
        await asyncio.sleep(_PROVIDER_RETEST_SECONDS)
        for kind in ("audio", "video"):
            for provider in _PROVIDER_DEFAULT_ORDER[kind]:
                result = await _probe_provider(kind, provider)
                await _record_provider(kind, provider, result is not None, result or 0.0)


async def start_provider_monitor():
    global _PROVIDER_MONITOR_TASK
    if _PROVIDER_MONITOR_TASK is None or _PROVIDER_MONITOR_TASK.done():
        _PROVIDER_MONITOR_TASK = asyncio.create_task(_provider_monitor())
    return _PROVIDER_MONITOR_TASK


async def _ytdlp_fallback(video_id: str, kind: str, timeout: int):
    return await asyncio.to_thread(_ytdlp_fallback_sync, video_id, kind, timeout)


def _ytdlp_fallback_sync(video_id: str, kind: str, timeout: int):
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    pattern = os.path.join(DOWNLOAD_DIR, f"{video_id}.*")
    existing = [p for p in glob.glob(pattern) if os.path.getsize(p) > 0]
    if existing:
        return existing[0]
    is_audio = kind == "audio"
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": timeout,
        "retries": 2,
        "outtmpl": os.path.join(DOWNLOAD_DIR, f"{video_id}.%(ext)s"),
        "format": "bestaudio[ext=m4a]/bestaudio/best" if is_audio else "bestvideo[height<=480]+bestaudio/best[height<=480]/best",
    }
    cookie_file = os.getenv("YTDLP_COOKIEFILE") or os.getenv("COOKIES_FILE")
    if cookie_file and os.path.isfile(cookie_file):
        opts["cookiefile"] = cookie_file
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
    except Exception:
        return None
    found = [p for p in glob.glob(pattern) if os.path.getsize(p) > 0]
    return found[0] if found else None


async def download_song(link: str) -> str:
    return await _download_media(link, "audio", 300)


async def download_video(link: str) -> str:
    return await _download_media(link, "video", 600)


AUTOPLAY_REQUEST_TIMEOUT = 20
AUTOPLAY_MAX_RETRIES = 3
AUTOPLAY_RETRY_DELAY = 1
AUTOPLAY_RETRYABLE_STATUS = (408, 425, 429, 500, 502, 503, 504)


async def get_autoplay(
    video_id: str,
    timeout: int = AUTOPLAY_REQUEST_TIMEOUT,
    retries: int = AUTOPLAY_MAX_RETRIES,
    seed_id: str = None,
) -> list:
    video_id = video_id.split("v=")[-1].split("&")[0] if "v=" in video_id else video_id
    if not video_id or len(video_id) < 3:
        return []

    params = {"video_id": video_id, "api_key": API_KEY}
    if seed_id and seed_id != video_id:
        params["seed_id"] = seed_id

    attempt = 0
    while attempt < retries:
        attempt += 1
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{API_URL}/autoplay",
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=timeout),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("tracks", [])
                    if resp.status in AUTOPLAY_RETRYABLE_STATUS and attempt < retries:
                        await asyncio.sleep(AUTOPLAY_RETRY_DELAY)
                        continue
                    return []
        except (asyncio.TimeoutError, aiohttp.ClientError):
            if attempt < retries:
                await asyncio.sleep(AUTOPLAY_RETRY_DELAY)
                continue
            return []
        except Exception:
            return []

    return []


class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        for message in messages:
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        return text[entity.offset: entity.offset + entity.length]
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        return None

    async def _api_search(self, query: str, limit: int = 1):
        base = (API_URL or "").strip().rstrip("/")
        key = (API_KEY or "").strip()
        if not base or not key or key == "YOUR_API_KEY":
            return []
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{base}/search",
                    params={"q": query, "limit": limit, "api_key": key},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        return []
                    payload = await resp.json()
                    return payload.get("result") or []
        except Exception:
            return []

    def _api_item_to_result(self, item):
        thumbnails = item.get("thumbnails") or [{}]
        channel = item.get("channel") or {}
        return {
            "title": item.get("title") or "Unknown",
            "duration": item.get("duration") or "0:00",
            "id": item.get("id") or "",
            "link": item.get("link") or "",
            "thumbnails": thumbnails,
            "channel": channel,
        }

    async def _search_one(self, query: str):
        items = await self._api_search(query, 1)
        if items:
            return self._api_item_to_result(items[0])
        results = VideosSearch(query, limit=1)
        for result in (await results.next())["result"]:
            return result
        return None

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        result = await self._search_one(link)
        if not result:
            raise Exception("no search results")
        title = result["title"]
        duration_min = result["duration"]
        thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        vidid = result["id"]
        duration_sec = int(time_to_seconds(duration_min)) if duration_min else 0
        return title, duration_min, duration_sec, thumbnail, vidid

    async def title(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        result = await self._search_one(link)
        return result["title"] if result else None

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        result = await self._search_one(link)
        return result["duration"] if result else None

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        result = await self._search_one(link)
        return result["thumbnails"][0]["url"].split("?")[0] if result else None

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        try:
            downloaded_file = await download_video(link)
            if downloaded_file:
                return 1, downloaded_file
            return 0, "Video download failed"
        except Exception as e:
            return 0, f"Video download error: {e}"

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]
        try:
            plist = await Playlist.get(link)
        except Exception:
            return []
        videos = plist.get("videos") or []
        ids = []
        for data in videos[:limit]:
            if not data:
                continue
            vid = data.get("id")
            if not vid:
                continue
            ids.append(vid)
        return ids

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        result = await self._search_one(link)
        if not result:
            raise Exception("no search results")
        title = result["title"]
        duration_min = result["duration"]
        vidid = result["id"]
        yturl = result["link"]
        thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        track_details = {
            "title": title,
            "link": yturl,
            "vidid": vidid,
            "duration_min": duration_min,
            "thumb": thumbnail,
        }
        return track_details, vidid

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        ytdl_opts = {"quiet": True}
        ydl = yt_dlp.YoutubeDL(ytdl_opts)
        with ydl:
            formats_available = []
            r = ydl.extract_info(link, download=False)
            for format in r["formats"]:
                try:
                    if "dash" not in str(format["format"]).lower():
                        formats_available.append(
                            {
                                "format": format["format"],
                                "filesize": format.get("filesize"),
                                "format_id": format["format_id"],
                                "ext": format["ext"],
                                "format_note": format["format_note"],
                                "yturl": link,
                            }
                        )
                except Exception:
                    continue
        return formats_available, link

    async def slider(self, link: str, query_type: int, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        a = VideosSearch(link, limit=10)
        result = (await a.next()).get("result")
        title = result[query_type]["title"]
        duration_min = result[query_type]["duration"]
        vidid = result[query_type]["id"]
        thumbnail = result[query_type]["thumbnails"][0]["url"].split("?")[0]
        return title, duration_min, thumbnail, vidid

    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ) -> str:
        if videoid:
            link = self.base + link
        try:
            if video:
                downloaded_file = await download_video(link)
            else:
                downloaded_file = await download_song(link)
            if downloaded_file:
                return downloaded_file, True
            return None, False
        except Exception:
            return None, False


YouTube = YouTubeAPI()
