import os
import json
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

SECRET = os.environ.get("BRIDGE_SECRET", "")
command_queue = {"cmd": None}
lock = threading.Lock()

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        
        if parsed.path == "/mcp":
            self.send_json({
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "svakom-controller", "version": "1.0.0"},
                "capabilities": {"tools": {}}
            })
            return

        if parsed.path == "/toy-next":
            qs = parse_qs(parsed.query)
            secret = qs.get("secret", [""])[0]
            if SECRET and secret != SECRET:
                self.send_response(403)
                self.end_headers()
                return
            with lock:
                cmd = command_queue.get("cmd")
                command_queue["cmd"] = None
            self.send_json(cmd or {})
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")

        if parsed.path == "/mcp":
            method = body.get("method", "")
            msg_id = body.get("id", 1)

            if method == "initialize":
                self.send_json({
                    "jsonrpc": "2.0", "id": msg_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "serverInfo": {"name": "svakom-controller", "version": "1.0.0"},
                        "capabilities": {"tools": {}}
                    }
                })
                return

            if method == "tools/list":
                self.send_json({
                    "jsonrpc": "2.0", "id": msg_id,
                    "result": {"tools": [
                        {"name": "toy_set_speed", "description": "设置强度 0.0-1.0", "inputSchema": {"type": "object", "properties": {"speed": {"type": "number"}}, "required": ["speed"]}},
                        {"name": "toy_set_pattern", "description": "设置振动花样 1-8", "inputSchema": {"type": "object", "properties": {"pattern": {"type": "integer"}, "level": {"type": "number"}}, "required": ["pattern"]}},
                        {"name": "toy_stop", "description": "立即停止", "inputSchema": {"type": "object", "properties": {}}},
                        {"name": "toy_status", "description": "查询是否在线", "inputSchema": {"type": "object", "properties": {}}}
                    ]}
                })
                return

            if method == "tools/call":
                tool = body.get("params", {}).get("name")
                args = body.get("params", {}).get("arguments", {})
                with lock:
                    if tool == "toy_set_speed":
                        command_queue["cmd"] = {"type": "speed", "value": args.get("speed", 0)}
                    elif tool == "toy_set_pattern":
                        command_queue["cmd"] = {"type": "pattern", "pattern": args.get("pattern", 1), "level": args.get("level", 0.5)}
                    elif tool == "toy_stop":
                        command_queue["cmd"] = {"type": "stop"}
                    elif tool == "toy_status":
                        self.send_json({"jsonrpc": "2.0", "id": msg_id, "result": {"content": [{"type": "text", "text": "online"}]}})
                        return
                self.send_json({"jsonrpc": "2.0", "id": msg_id, "result": {"content": [{"type": "text", "text": "ok"}]}})
                return

            self.send_json({"jsonrpc": "2.0", "id": msg_id, "result": {}})
            return

        self.send_response(404)
        self.end_headers()

port = int(os.environ.get("PORT", 8080))
print(f"Server starting on port {port}")
HTTPServer(("0.0.0.0", port), Handler).serve_forever()
