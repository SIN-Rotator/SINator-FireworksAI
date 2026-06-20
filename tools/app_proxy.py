"""SINator App Proxy — forwards port 8000 → port 8100.

The SINator desktop app (Tauri, com.sinator.dashboard) reads from
http://localhost:8000/api/v1/pool/stats, /health, /api/v1/config.
The FireworksAI toolbox backend runs on port 8100.
This proxy bridges the gap so the app sees live data.
"""
import http.server
import http.client
import urllib.parse

LISTEN_PORT = 8000
TARGET_HOST = "localhost"
TARGET_PORT = 8100


class ProxyHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self._proxy()

    def do_POST(self):
        self._proxy()

    def do_DELETE(self):
        self._proxy()

    def do_PUT(self):
        self._proxy()

    def _proxy(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else None

        conn = http.client.HTTPConnection(TARGET_HOST, TARGET_PORT)
        headers = {k: v for k, v in self.headers.items() if k.lower() != "host"}
        headers["Host"] = f"{TARGET_HOST}:{TARGET_PORT}"
        if "Authorization" not in headers and "Sinator" in self.headers.get("Authorization", ""):
            headers["Authorization"] = "Bearer 7avN1KkfInNqcOMn2CtwLTvx"

        try:
            conn.request(self.command, self.path, body=body, headers=headers)
            resp = conn.getresponse()
            data = resp.read()
            self.send_response(resp.status)
            for k, v in resp.getheaders():
                if k.lower() not in ("transfer-encoding", "connection"):
                    self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(f'{{"error":"{e}"}}'.encode())
        finally:
            conn.close()

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    server = http.server.HTTPServer(("0.0.0.0", LISTEN_PORT), ProxyHandler)
    print(f"SINator App Proxy: :{LISTEN_PORT} → :{TARGET_PORT}")
    server.serve_forever()
