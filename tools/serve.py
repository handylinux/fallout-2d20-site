#!/usr/bin/env python3
"""
Локальная раздача собранного сайта (public/) для просмотра.

  python3 tools/serve.py          # http://0.0.0.0:8000
  PORT=3000 python3 tools/serve.py

Особенности:
  * адреса без завершающего слэша и без расширения (/perki) ведут на /perki/index.html;
  * Cache-Control: no-store, чтобы правки после пересборки сразу были видны;
  * ThreadingHTTPServer — превью не подвисает на параллельных запросах.
"""
import http.server
import os
import posixpath
import socketserver
import sys
import urllib.parse

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
PUBLIC = os.path.join(ROOT, 'public')
HOST = os.environ.get('HOST', '0.0.0.0')
PORT = int(os.environ.get('PORT', '8000'))


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PUBLIC, **kwargs)

    def translate_path(self, path):
        """Каталог без индекса и путь без расширения → index.html внутри."""
        path = urllib.parse.urlsplit(path).path
        path = urllib.parse.unquote(path)
        path = posixpath.normpath(path)
        parts = [p for p in path.split('/') if p and p not in ('.', '..')]
        local = os.path.join(PUBLIC, *parts)
        if not os.path.splitext(local)[1] or os.path.isdir(local):
            index = os.path.join(local, 'index.html')
            if os.path.isfile(index):
                local = index
        return local

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, must-revalidate')
        super().end_headers()

    def log_message(self, fmt, *args):
        sys.stderr.write('%s - %s\n' % (self.address_string(), fmt % args))


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    if not os.path.isdir(PUBLIC):
        sys.exit('нет каталога public/ — сначала выполните: python3 tools/sitegen/build.py')
    with Server((HOST, PORT), Handler) as httpd:
        print('Раздаю %s на http://%s:%d' % (PUBLIC, HOST, PORT), flush=True)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
