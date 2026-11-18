import os
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in ("/", "/healthz"):
            self.send_response(404)
            self.end_headers()
            return
        body = b"ok\n"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        return


def self_ping():
    url = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
    if not url:
        return
    time.sleep(45)
    while True:
        try:
            urllib.request.urlopen(url + "/healthz", timeout=15).read(16)
        except Exception:
            pass
        time.sleep(600)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    threading.Thread(target=self_ping, daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
