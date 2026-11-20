import hashlib
import logging
import queue
import time
import traceback

ERROR_QUEUE = queue.Queue(maxsize=100)
_DEDUPE_WINDOW = 300.0
_recent = {}


def enqueue_error(title: str, text: str) -> None:
    key = hashlib.blake2b(text.encode("utf-8", "replace"), digest_size=8).digest()
    now = time.monotonic()
    last = _recent.get(key)
    if last is not None and now - last < _DEDUPE_WINDOW:
        return
    if len(_recent) > 512:
        for stale in [k for k, v in _recent.items() if now - v >= _DEDUPE_WINDOW]:
            _recent.pop(stale, None)
    _recent[key] = now
    try:
        ERROR_QUEUE.put_nowait((title, text))
    except queue.Full:
        pass


class ErrorQueueHandler(logging.Handler):
    def emit(self, record):
        if record.levelno < logging.ERROR:
            return
        try:
            text = self.format(record)
            if record.exc_info:
                text += "\n" + "".join(
                    traceback.format_exception(*record.exc_info)
                )
            enqueue_error(record.levelname, text)
        except Exception:
            pass


logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s - %(levelname)s] - %(name)s - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
    handlers=[
        logging.FileHandler("log.txt"),
        logging.StreamHandler(),
    ],
)

logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("pymongo").setLevel(logging.ERROR)
logging.getLogger("pyrogram").setLevel(logging.ERROR)
logging.getLogger("pytgcalls").setLevel(logging.ERROR)

_error_handler = ErrorQueueHandler()
_error_handler.setLevel(logging.ERROR)
logging.getLogger().addHandler(_error_handler)


def LOGGER(name: str) -> logging.Logger:
    return logging.getLogger(name)
