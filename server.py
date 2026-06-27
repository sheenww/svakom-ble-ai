import os
import json
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

SECRET = os.environ.get("BRIDGE_SECRET", "")
command_queue = {"cmd": None, "updated_at": 0}
lock = threading.Lock()

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        secret = qs.get("secret", [""])[0]

        if parsed.path == "/mcp" or parsed.path.startswith("/mcp"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "name": "svakom-controller",
                "version": "1.0",
                "tools": [
                    {"name": "toy_set_speed", "description": "设置振动强度 0.0-1.0", "parameters": {"type": "object", "properties": {"speed": {"type": "number"}}, "required": ["speed"]}},
                    {"name": "toy_set_pattern", "description": "设置振动花样 1-8，强度 0.0-1.0", "parameters": {"type": "object", "properties": {"pattern": {"type": "integer"}, "level": {"type": "number"}}, "required": ["pattern"]}},
                    {"name": "toy_stop", "description": "立即停止", "parameters": {"type": "object", "properties": {}}},
                    {"name": "toy_status", "description": "查询中继是否在线", "parameters": {"type": "object", "properties": {}}}
                ]
            }).encode())
            return

        if parsed.path == "/toy-next":
            if secret != SECRET:
                self.send_response(403)
                self.end_headers()
                return
            with lock:
                cmd = command_queue.get("cmd")
                command_queue["cmd"] = None
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"cmd": cmd}).encode())
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        secret = qs.get("secret", [""])[0]
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")

        if parsed.path.startswith("/mcp/call"):
            tool = body.get("name")
            params = body.get("parameters", {})
            with lock:
                if tool == "toy_set_speed":
                    command_queue["cmd"] = {"type": "speed", "value": params.get("speed", 0)}
                elif tool == "toy_set_pattern":
                    command_queue["cmd"] = {"type": "pattern", "pattern": params.get("pattern", 1), "level": params.get("level", 0.5)}
                elif tool == "toy_stop":
                    command_queue["cmd"] = {"type": "stop"}
                elif tool == "toy_status":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"result": "online"}).encode())
                    return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"result": "ok"}).encode())
            return

        self.send_response(404)
        self.end_headers()

port = int(os.environ.get("PORT", 8080))
print(f"Server starting on port {port}")
HTTPServer(("0.0.0.0", port), Handler).serve_forever()
