#!/usr/bin/env python3
import argparse
import json
import mimetypes
import os
import socket
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse


SESSIONS = {}


def _json_response(handler, status, payload):
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.end_headers()
    handler.wfile.write(body)


def _request_json(handler):
    length = int(handler.headers.get("Content-Length") or 0)
    if length == 0:
        return {}
    raw = handler.rfile.read(length)
    return json.loads(raw.decode("utf-8"))


def _lan_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


class ClickersHandler(SimpleHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path == "/api/server-info":
            host = self.headers.get("Host", "")
            port = host.split(":")[-1] if ":" in host else str(self.server.server_port)
            lan_ip = _lan_ip()
            _json_response(self, 200, {
                "ok": True,
                "lanIp": lan_ip,
                "preferredOrigin": f"http://{lan_ip}:{port}",
                "currentOrigin": f"http://{host}" if host else "",
            })
            return

        if path.startswith("/api/session/"):
            session_id = path.split("/")[3] if len(path.split("/")) > 3 else ""
            session = SESSIONS.setdefault(session_id, {
                "responses": {},
                "createdAt": int(time.time() * 1000),
                "updatedAt": int(time.time() * 1000),
            })
            _json_response(self, 200, {
                "ok": True,
                "sessionId": session_id,
                "responses": session["responses"],
                "updatedAt": session["updatedAt"],
            })
            return

        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path.startswith("/api/session/"):
            parts = path.strip("/").split("/")
            session_id = parts[2] if len(parts) >= 3 else ""
            action = parts[3] if len(parts) >= 4 else ""
            session = SESSIONS.setdefault(session_id, {
                "responses": {},
                "createdAt": int(time.time() * 1000),
                "updatedAt": int(time.time() * 1000),
            })

            if action == "reset":
                session["responses"] = {}
                session["updatedAt"] = int(time.time() * 1000)
                _json_response(self, 200, {"ok": True, "sessionId": session_id})
                return

            if action == "response":
                try:
                    data = _request_json(self)
                    card_id = str(int(data.get("cardId")))
                    answer = str(data.get("answer", "")).upper()
                    if answer not in {"A", "B", "C", "D"}:
                        raise ValueError("answer must be A, B, C, or D")
                    timestamp = int(data.get("timestamp") or int(time.time() * 1000))
                    session["responses"][card_id] = {
                        "answer": answer,
                        "timestamp": timestamp,
                    }
                    session["updatedAt"] = int(time.time() * 1000)
                    _json_response(self, 200, {"ok": True, "sessionId": session_id})
                except Exception as exc:
                    _json_response(self, 400, {"ok": False, "error": str(exc)})
                return

        _json_response(self, 404, {"ok": False, "error": "Not found"})


def main():
    parser = argparse.ArgumentParser(description="Serve Clickers with phone scanner sync.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    mimetypes.add_type("text/html", ".html")
    server = ThreadingHTTPServer((args.host, args.port), ClickersHandler)
    lan = _lan_ip()
    print(f"Clickers teacher screen: http://localhost:{args.port}/index.html")
    print(f"Phone/network URL:      http://{lan}:{args.port}/index.html")
    server.serve_forever()


if __name__ == "__main__":
    main()
