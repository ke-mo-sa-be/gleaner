"""Local fake directory site for integration tests. Synthetic data only; binds to 127.0.0.1."""

import threading
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

PAD = "<!-- " + "padding " * 80 + "-->"  # keep pages above the fetcher's blank-page threshold

# id -> (name, phone or None). 6 is a duplicate of 1; 5 has no phone.
DOCTORS = {
    1: ("DR. ALPHA", "98450 00001"),
    2: ("DR. BETA", "98450 00002"),
    3: ("DR. GAMMA", "080-2345 6789"),
    4: ("DR. DELTA", "98450 00004"),
    5: ("DR. EPSILON", None),
    6: ("DR. ALPHA", "98450 00001"),
    # second "city", served at /list-b (one page)
    101: ("DR. KAPPA", "98450 00101"),
    102: ("DR. LAMBDA", "98450 00102"),
}
PER_PAGE = 3


def page(body):
    return f"<html><head><title>Fixture</title></head><body>{body}{PAD}</body></html>"


def listing(ids, next_page=None, detail_prefix="/doc/"):
    rows = "".join(
        f'<li class="item"><b class="name">{DOCTORS.get(i, ("DR. X", None))[0]}</b>'
        f'<a class="more" href="{detail_prefix}{i}">View</a></li>' for i in ids
    )
    nxt = f'<a class="next" href="/list?page={next_page}">Next</a>' if next_page else ""
    return page(f'<ul id="results">{rows}</ul>{nxt}')


def detail(i):
    name, phone = DOCTORS[i]
    phone_row = f"<tr><td>Phone Number</td><td>{phone}</td></tr>" if phone else ""
    return page(f'<table class="info"><tr><td>Name</td><td>{name}</td></tr>{phone_row}'
                f"<tr><td>Address :</td><td>{i} Main Rd, Bengaluru 5600{i:02d}</td></tr></table>")


class Handler(BaseHTTPRequestHandler):
    hits: Counter = Counter()

    def log_message(self, *args):
        pass

    def send(self, status, body=""):
        data = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parts = urlsplit(self.path)
        path = parts.path
        Handler.hits[path] += 1
        q = parse_qs(parts.query)
        if path == "/robots.txt":
            return self.send(200, "User-agent: *\nDisallow: /private/\n")
        if path == "/list-b":
            n = int(q.get("page", ["1"])[0])
            return self.send(200, listing([101, 102] if n == 1 else []))
        if path in ("/list", "/private/list"):
            n = int(q.get("page", ["1"])[0])
            ids = [i for i in DOCTORS if i < 100 and (i - 1) // PER_PAGE == n - 1]
            return self.send(200, listing(ids, next_page=n + 1 if ids and n < 2 else None))
        if path.startswith("/doc/"):
            return self.send(200, detail(int(path.rsplit("/", 1)[1])))
        if path == "/blocked-list":
            return self.send(200, listing([1, 2], detail_prefix="/limited/"))
        if path.startswith("/limited/"):
            return self.send(429, "Too Many Requests")
        if path == "/blank-list":
            return self.send(200, listing([1, 2, 3, 4], detail_prefix="/blank/"))
        if path.startswith("/blank/"):
            return self.send(200, "")
        if path == "/empty-list":
            return self.send(200, page("<p>No results</p>"))
        return self.send(404, page("not found"))


class FixtureSite:
    def __enter__(self):
        Handler.hits.clear()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self

    @property
    def hits(self):
        return Handler.hits

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()
