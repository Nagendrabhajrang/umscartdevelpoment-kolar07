"""Serve the Flutter web build with a same-origin proxy in front of Django.

Why this exists: a browser will not let the app call http://localhost:8000 from
http://localhost:8099 (different origin, and the session cookie is HttpOnly).
Serving the build and proxying /api and /media from one origin keeps the app
same-origin, so cookies and CSRF work exactly as they do on the real device.

    flutter build web --release --dart-define=API_BASE=relative
    python3 serve_web.py            # http://localhost:8099

Android does not need this file: build the APK with the default API_BASE,
which points at 10.0.2.2:8000 from the emulator.
"""

import http.server
import json
import os
import socketserver
import socket
import sys
import urllib.error
import urllib.request

API = os.environ.get("API_UPSTREAM", "http://127.0.0.1:8000")
WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "build", "web")
PORT = int(os.environ.get("PORT", "8099"))

PROXY_PREFIXES = ("/api/", "/media/")
HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "host", "content-length",
}
# Django rejects an unsafe request whose Origin is not in CSRF_TRUSTED_ORIGINS.
# When the app is opened through a preview/tunnel host that origin is unknown to
# Django, so the proxy rewrites it to the upstream origin. The CSRF *token*
# check is untouched: the token still has to match the cookie.
REWRITE_TO_UPSTREAM = {"origin", "referer"}


def _framed_cookie(value):
    """Keep the sign-in cookie alive when the app is shown inside a frame of
    another site (a preview panel). Browsers that block third-party cookies
    still accept a cookie marked "Partitioned". Only cookies that are already
    "SameSite=None; Secure" are touched, so a plain http://localhost run is
    not changed."""
    low = value.lower()
    if "samesite=none" in low and "secure" in low and "partitioned" not in low:
        return value + "; Partitioned"
    return value


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB, **kwargs)

    def _is_proxy(self):
        return self.path.startswith(PROXY_PREFIXES)

    def _proxy(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None

        origin = API.rstrip("/")
        headers = {}
        for key, value in self.headers.items():
            low = key.lower()
            if low in HOP_BY_HOP:
                continue
            if low in REWRITE_TO_UPSTREAM:
                headers[key] = origin if low == "origin" else origin + "/"
                continue
            headers[key] = value
        # The browser copy of the app keeps the sign-in cookie itself and sends
        # it in "X-App-Cookie" (a browser may refuse cookies inside a preview
        # frame). Hand it to Django as a normal cookie.
        app_cookie = None
        for key in list(headers):
            if key.lower() == "x-app-cookie":
                app_cookie = headers.pop(key)
        if app_cookie is not None:
            for key in list(headers):
                if key.lower() == "cookie":
                    headers.pop(key)
            headers["Cookie"] = app_cookie
        headers["X-Forwarded-Proto"] = "http"
        headers["X-Forwarded-Host"] = self.headers.get("Host", "")

        req = urllib.request.Request(
            API + self.path, data=body, headers=headers, method=self.command
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as upstream:
                self._relay(upstream.status, upstream.headers, upstream.read())
        except urllib.error.HTTPError as exc:
            self._relay(exc.code, exc.headers, exc.read())
        except Exception as exc:  # upstream down, DNS failure, timeout
            payload = f'{{"error":{{"code":"upstream_unreachable","message":"{exc}"}}}}'
            self._relay(502, {}, payload.encode())

    # Requests that only the OLD app makes. A browser that is still running an
    # old stored copy is told to throw that copy away, so the next reload gets
    # the new app. The new app never sends these, so it is not affected.
    OLD_APP_MARKERS = ("/api/v1/cart/?guest_cart=", "/products/featured/?page_size=12")

    def _relay(self, status, headers, payload):
        self.send_response(status)
        if any(mark in self.path for mark in self.OLD_APP_MARKERS):
            self.send_header("Clear-Site-Data", '"cache", "storage"')
        for key, value in (headers.items() if headers else []):
            if key.lower() in HOP_BY_HOP:
                continue
            if key.lower() == "set-cookie":
                value = _framed_cookie(value)
            self.send_header(key, value)
        cookies = headers.get_all("Set-Cookie") if hasattr(headers, "get_all") else None
        if cookies:
            # Repeated for the app, which cannot read "Set-Cookie" in a browser.
            self.send_header("X-App-Set-Cookie", json.dumps(cookies))
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)

    def end_headers(self):
        # Never let the browser keep an old copy of the app: after a rebuild
        # the very next page load must show the new screens.
        if not self._is_proxy():
            self.send_header("Cache-Control", "no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
        super().end_headers()

    def do_GET(self):
        if self._is_proxy():
            return self._proxy()
        # Ignore "If-Modified-Since" so a cached old copy is never confirmed.
        if "If-Modified-Since" in self.headers:
            del self.headers["If-Modified-Since"]
        if "If-None-Match" in self.headers:
            del self.headers["If-None-Match"]
        page = self.path.split("?", 1)[0]
        if page in ("/", "/index.html"):
            return self._stamped("index.html", "text/html; charset=utf-8",
                                 "flutter_bootstrap.js", "flutter_bootstrap.js?v=%s")
        if page == "/flutter_bootstrap.js":
            return self._stamped("flutter_bootstrap.js", "application/javascript",
                                 '"main.dart.js"', '"main.dart.js?v=%s"')
        return super().do_GET()

    def _stamped(self, name, content_type, find, replace):
        """Serve a start-up file with the build time added to the next file's
        address. A browser that kept an old copy of the app then has to fetch
        the new one, because the address is new after every build."""
        try:
            stamp = str(int(os.path.getmtime(os.path.join(WEB, "main.dart.js"))))
            with open(os.path.join(WEB, name), "r", encoding="utf-8") as handle:
                text = handle.read()
        except OSError:
            return super().do_GET()
        payload = text.replace(find, replace % stamp).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_HEAD(self):
        if self._is_proxy():
            return self._proxy()
        return super().do_HEAD()

    def do_POST(self):
        return self._proxy()

    def do_PUT(self):
        return self._proxy()

    def do_PATCH(self):
        return self._proxy()

    def do_DELETE(self):
        return self._proxy()

    def do_OPTIONS(self):
        return self._proxy()

    def log_message(self, fmt, *args):
        note = ""
        if self.path.startswith("/api/auth/session"):
            note = "  [sign-in cookie sent: %s]" % (
                "yes" if "sessionid" in ((self.headers.get("X-App-Cookie") or "")
                                         + (self.headers.get("Cookie") or "")) else "no")
        sys.stderr.write("%s %s%s\n" % (self.address_string(), fmt % args, note))


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    if not os.path.isdir(WEB):
        sys.exit("No build/web — run: flutter build web --release --dart-define=API_BASE=relative")
    host = "0.0.0.0"
    try:
        with socket.create_connection(("127.0.0.1", 8000), timeout=2):
            print(f"API upstream {API} is reachable.")
    except OSError:
        print(f"WARNING: {API} is not answering — start Django first.", file=sys.stderr)
    print(f"Flutter customer app on http://localhost:{PORT}  (proxy: /api, /media -> {API})")
    with Server((host, PORT), Handler) as httpd:
        httpd.serve_forever()
