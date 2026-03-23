#!/usr/bin/env python3
"""MCP Server: git-tools  (port 8101)
Exposes git diff, changed files, file reads as MCP HTTP tools."""

import json, subprocess, sys, http.server
from pathlib import Path

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8101

TOOLS = [
    {"name": "git_diff",          "description": "git diff vs base branch",
     "inputSchema": {"type":"object","properties":{"base":{"type":"string"}},"required":["base"]}},
    {"name": "git_diff_range",    "description": "git diff for commit range",
     "inputSchema": {"type":"object","properties":{"range":{"type":"string"}},"required":["range"]}},
    {"name": "git_changed_files", "description": "list changed files",
     "inputSchema": {"type":"object","properties":{"base":{"type":"string"},"range":{"type":"string"}}}},
    {"name": "git_log",           "description": "recent commit log",
     "inputSchema": {"type":"object","properties":{"n":{"type":"integer"}}}},
    {"name": "read_file",         "description": "read a repo file",
     "inputSchema": {"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}},
]

def run(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return r.stdout if r.returncode == 0 else f"[error: {r.stderr[:200]}]"
    except Exception as e:
        return f"[error: {e}]"

def call_tool(name, args):
    if name == "git_diff":
        out = run(["git","diff",f"{args.get('base','main')}...HEAD"])
        return out or run(["git","diff","--cached"]) or "[no diff]"
    elif name == "git_diff_range":
        return run(["git","diff",args.get("range","HEAD~1..HEAD")])
    elif name == "git_changed_files":
        if args.get("range"):
            out = run(["git","diff","--name-only",args["range"]])
        else:
            out = run(["git","diff","--name-only",f"{args.get('base','main')}...HEAD"])
            if not out.strip():
                out = run(["git","diff","--name-only","--cached"])
        return json.dumps([f.strip() for f in out.strip().splitlines() if f.strip()])
    elif name == "git_log":
        return run(["git","log",f"-{args.get('n',5)}","--oneline"])
    elif name == "read_file":
        try:
            return Path(args["path"]).read_text(errors="replace")[:4000]
        except Exception as e:
            return f"[cannot read: {e}]"
    return f"[unknown tool: {name}]"

class H(http.server.BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def send_json(self,d,s=200):
        b=json.dumps(d).encode()
        self.send_response(s); self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",len(b)); self.end_headers(); self.wfile.write(b)
    def read_body(self):
        n=int(self.headers.get("Content-Length",0))
        return json.loads(self.rfile.read(n)) if n else {}
    def do_GET(self):
        if self.path=="/mcp/tools": self.send_json({"tools":TOOLS})
        elif self.path=="/health":  self.send_json({"status":"ok","server":"git-tools"})
        else: self.send_json({"error":"not found"},404)
    def do_POST(self):
        if self.path=="/mcp/call":
            b=self.read_body()
            self.send_json({"content":[{"type":"text","text":call_tool(b.get("name",""),b.get("arguments",{}))}]})
        else: self.send_json({"error":"not found"},404)

if __name__=="__main__":
    print(f"[MCP] git-tools on port {PORT}")
    http.server.HTTPServer(("",PORT),H).serve_forever()
