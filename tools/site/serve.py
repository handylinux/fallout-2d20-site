#!/usr/bin/env python3
"""Локальный просмотр нового каркаса: site/ на http://localhost:8080"""
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
SITE = os.path.join(ROOT, 'site')
PORT = int(os.environ.get('PORT') or 8080)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=SITE, **kw)

    def translate_path(self, path):
        p = super().translate_path(path)
        if os.path.isdir(p):
            idx = os.path.join(p, 'index.html')
            if os.path.exists(idx):
                return idx
        return p

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()


if __name__ == '__main__':
    if not os.path.isdir(SITE):
        sys.exit('нет site/ — сначала python3 tools/site/build_site.py')
    ThreadingHTTPServer(('0.0.0.0', PORT), Handler).serve_forever()
