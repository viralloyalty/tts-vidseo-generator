import http.server
import socketserver

PORT = 8000

class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # Add required headers for SharedArrayBuffer (COOP / COEP)
        self.send_header('Cross-Origin-Opener-Policy', 'same-origin')
        self.send_header('Cross-Origin-Embedder-Policy', 'credentialless')
        # Prevent HTML from being cached by the service worker (avoids stale JS loading)
        if self.path.endswith('.html') or self.path == '/' or ('?' not in self.path and '.' not in self.path.split('/')[-1]):
            self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        super().end_headers()

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"Serving at port {PORT} with COOP/COEP headers")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()
