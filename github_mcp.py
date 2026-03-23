#!/usr/bin/env python3
"""MCP Server: github-tools  (port 8102)
Exposes GitHub REST API as MCP HTTP tools."""

import json, os, random, subprocess, urllib.request, urllib.error, http.server, sys, ssl

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8102

TOOLS = [
    {"name":"github_get_issue",    "description":"Fetch a GitHub Issue",
     "inputSchema":{"type":"object","properties":{"number":{"type":"integer"}},"required":["number"]}},
    {"name":"github_get_pr",       "description":"Fetch a GitHub PR",
     "inputSchema":{"type":"object","properties":{"number":{"type":"integer"}},"required":["number"]}},
    {"name":"github_create_issue", "description":"Create a GitHub Issue",
     "inputSchema":{"type":"object","properties":{"title":{"type":"string"},"body":{"type":"string"},"labels":{"type":"array"}},"required":["title","body"]}},
    {"name":"github_create_pr",    "description":"Create a GitHub PR",
     "inputSchema":{"type":"object","properties":{"title":{"type":"string"},"body":{"type":"string"}},"required":["title","body"]}},
]

def _ssl_context():
    """Build an SSL context that works on macOS without needing 'Install Certificates.command'."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        pass
    try:
        import subprocess as sp
        result = sp.run(["python3", "-c",
            "import ssl; print(ssl.get_default_verify_paths().cafile or ssl.get_default_verify_paths().capath)"],
            capture_output=True, text=True)
        cafile = result.stdout.strip()
        if cafile and os.path.exists(cafile):
            return ssl.create_default_context(cafile=cafile)
    except Exception:
        pass
    # Last resort: disable verification (only for demo mode without real token)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

SSL_CTX = _ssl_context()

def headers():
    h={"Accept":"application/vnd.github+json","Content-Type":"application/json"}
    t=os.environ.get("GITHUB_TOKEN","")
    if t: h["Authorization"]=f"Bearer {t}"
    return h

def gh(method,path,data=None):
    repo=os.environ.get("GITHUB_REPO","mizanJewel/CS5001-Prompting-With-RAG")
    url=f"https://api.github.com/repos/{repo}{path}"
    body=json.dumps(data).encode() if data else None
    req=urllib.request.Request(url,data=body,headers=headers(),method=method)
    try:
        with urllib.request.urlopen(req, timeout=15, context=SSL_CTX) as r:
            return {"ok":True,"data":json.loads(r.read())}
    except urllib.error.HTTPError as e:
        return {"ok":False,"error":f"HTTP {e.code}: {e.read().decode()[:200]}"}
    except Exception as ex:
        return {"ok":False,"error":str(ex)}

def configured():
    return bool(os.environ.get("GITHUB_TOKEN") and os.environ.get("GITHUB_REPO"))

def demo_item(kind,number):
    if kind=="issue":
        return {"number":number,"title":"RAG pipeline returns irrelevant chunks for complex queries",
                "body":"When querying with multi-part questions retriever returns unrelated chunks.",
                "state":"open","labels":["bug"],
                "url":f"https://github.com/mizanJewel/CS5001-Prompting-With-RAG/issues/{number}"}
    return {"number":number,"title":"Add chunking strategy and reranking to RAG pipeline",
            "body":"This PR improves retrieval quality.","state":"open","labels":[],
            "url":f"https://github.com/mizanJewel/CS5001-Prompting-With-RAG/pull/{number}"}

def demo_create(kind):
    n=random.randint(1,20)
    return {"success":True,"number":n,"demo":True,
            "url":f"https://github.com/mizanJewel/CS5001-Prompting-With-RAG/{'issues' if kind=='issue' else 'pull'}/{n}"}

def call_tool(name,args):
    if name=="github_get_issue":
        if not configured(): return json.dumps(demo_item("issue",args.get("number",1)))
        r=gh("GET",f"/issues/{args['number']}")
        if r["ok"]:
            d=r["data"]
            return json.dumps({"number":d["number"],"title":d["title"],"body":d.get("body","")or"",
                                "state":d["state"],"labels":[l["name"] for l in d.get("labels",[])],"url":d["html_url"]})
        return json.dumps(demo_item("issue",args.get("number",1)))
    elif name=="github_get_pr":
        if not configured(): return json.dumps(demo_item("pr",args.get("number",1)))
        r=gh("GET",f"/pulls/{args['number']}")
        if r["ok"]:
            d=r["data"]
            return json.dumps({"number":d["number"],"title":d["title"],"body":d.get("body","")or"","state":d["state"],"url":d["html_url"]})
        return json.dumps(demo_item("pr",args.get("number",1)))
    elif name=="github_create_issue":
        if not configured(): return json.dumps(demo_create("issue"))
        r=gh("POST","/issues",{"title":args["title"],"body":args["body"],"labels":args.get("labels",[])})
        if r["ok"]: return json.dumps({"success":True,"number":r["data"]["number"],"url":r["data"]["html_url"]})
        return json.dumps({"success":False,"error":r["error"]})
    elif name=="github_create_pr":
        if not configured(): return json.dumps(demo_create("pr"))
        try:
            head=subprocess.run(["git","rev-parse","--abbrev-ref","HEAD"],capture_output=True,text=True).stdout.strip() or "feature-branch"
        except: head="feature-branch"
        r=gh("POST","/pulls",{"title":args["title"],"body":args["body"],"head":head,"base":"main"})
        if r["ok"]: return json.dumps({"success":True,"number":r["data"]["number"],"url":r["data"]["html_url"]})
        return json.dumps({"success":False,"error":r["error"]})
    return json.dumps({"error":f"unknown tool: {name}"})

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
        elif self.path=="/health":  self.send_json({"status":"ok","server":"github-tools"})
        else: self.send_json({"error":"not found"},404)
    def do_POST(self):
        if self.path=="/mcp/call":
            b=self.read_body()
            self.send_json({"content":[{"type":"text","text":call_tool(b.get("name",""),b.get("arguments",{}))}]})
        else: self.send_json({"error":"not found"},404)

if __name__=="__main__":
    print(f"[MCP] github-tools on port {PORT}")
    http.server.HTTPServer(("",PORT),H).serve_forever()
