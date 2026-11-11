import http.server, socketserver, os
os.chdir('/home/user/fallout-2d20-site/public')
class H(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        p = self.path.split('?')[0]
        if p != '/' and not os.path.splitext(p)[1]:
            if os.path.isdir('.' + p):
                self.path = p.rstrip('/') + '/index.html'
        return super().do_GET()
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()
socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(('0.0.0.0', 8000), H) as httpd:
    httpd.serve_forever()
