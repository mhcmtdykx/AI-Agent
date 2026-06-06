"""简单的HTTP服务器"""
import http.server
import socketserver
import json
import sys
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

PORT = 8080

class MyHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.path = "/index.html"
            return http.server.SimpleHTTPRequestHandler.do_GET(self)
        self.send_response(404)
        self.end_headers()
    
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b""
        self.send_response(200)
        self.send_header("Content-type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok"}).encode("utf-8"))

print(f"服务器启动在端口 {PORT}")
print(f"请访问: http://127.0.0.1:{PORT}")
sys.stdout.flush()

with socketserver.TCPServer(("", PORT), MyHandler) as httpd:
    httpd.serve_forever()
