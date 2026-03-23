"""
A2A Protocol — Agent-to-Agent HTTP communication.
Each agent runs as an HTTP server on its own port.
The Orchestrator sends structured task messages to each agent.
"""

import json, uuid, threading, http.server
import urllib.request, urllib.error


class A2AClient:
    """Sends tasks to other agents."""

    def send_task(self, agent_url, action, input_data, context=None, from_agent="orchestrator"):
        task_id = str(uuid.uuid4())[:8]
        payload = json.dumps({
            "task_id": task_id, "from_agent": from_agent,
            "action":  action,  "input": input_data,
            "context": context or {}
        }).encode()
        req = urllib.request.Request(
            f"{agent_url.rstrip('/')}/a2a/task",
            data=payload, headers={"Content-Type":"application/json"}, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read())
        except Exception as e:
            return {"status":"failed","error":str(e),"task_id":task_id,"output":{},"artifacts":[]}

    def is_available(self, agent_url):
        try:
            with urllib.request.urlopen(f"{agent_url.rstrip('/')}/health", timeout=3) as r:
                return r.status == 200
        except:
            return False


class MCPClient:
    """Calls tools on an MCP server."""

    def __init__(self, base_url, name="mcp"):
        self.base_url = base_url.rstrip("/")
        self.name     = name

    def call(self, tool_name, arguments=None):
        payload = json.dumps({"name":tool_name,"arguments":arguments or {}}).encode()
        req = urllib.request.Request(
            f"{self.base_url}/mcp/call",
            data=payload, headers={"Content-Type":"application/json"}, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.loads(r.read())
                content = data.get("content",[])
                return content[0]["text"] if content else ""
        except Exception as e:
            return f"[MCP error: {self.name}/{tool_name} — {e}]"

    def call_json(self, tool_name, arguments=None):
        raw = self.call(tool_name, arguments)
        try:    return json.loads(raw)
        except: return {"raw": raw}

    def is_available(self):
        try:
            with urllib.request.urlopen(f"{self.base_url}/health", timeout=3) as r:
                return r.status == 200
        except:
            return False


class A2AAgentServer:
    """Base HTTP server for an A2A agent."""

    def __init__(self, name, port):
        self.name = name
        self.port = port
        self._server = None

    def handle_task(self, action, input_data, context):
        raise NotImplementedError

    def start(self):
        agent = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self,*a): pass
            def send_json(self,d,s=200):
                b=json.dumps(d).encode()
                self.send_response(s); self.send_header("Content-Type","application/json")
                self.send_header("Content-Length",len(b)); self.end_headers(); self.wfile.write(b)
            def do_GET(self):
                if self.path=="/health": self.send_json({"status":"ok","agent":agent.name})
                else: self.send_json({"error":"not found"},404)
            def do_POST(self):
                if self.path=="/a2a/task":
                    n=int(self.headers.get("Content-Length",0))
                    body=json.loads(self.rfile.read(n))
                    try:
                        result=agent.handle_task(body.get("action",""),body.get("input",{}),body.get("context",{}))
                        self.send_json({"task_id":body.get("task_id","?"),"agent":agent.name,
                                        "status":"completed","output":result.get("output",{}),"artifacts":result.get("artifacts",[])})
                    except Exception as e:
                        self.send_json({"task_id":body.get("task_id","?"),"agent":agent.name,
                                        "status":"failed","error":str(e),"output":{},"artifacts":[]})
                else: self.send_json({"error":"not found"},404)

        self._server = http.server.HTTPServer(("", self.port), Handler)
        t = threading.Thread(target=self._server.serve_forever, daemon=True)
        t.start()
        print(f"  [A2A] {self.name} agent on port {self.port}")

    def stop(self):
        if self._server: self._server.shutdown()
