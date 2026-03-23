#!/usr/bin/env python3
"""Gatekeeper A2A Agent (port 8204) — uses github-tools MCP"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from a2a.protocol import A2AAgentServer, MCPClient

class GatekeeperAgent(A2AAgentServer):
    def __init__(self):
        super().__init__("gatekeeper", 8204)
        self.github = MCPClient("http://localhost:8102","github-tools")

    def handle_task(self, action, inp, context):
        if action=="reflect":     return self._reflect(inp)
        if action=="create_item": return self._create(inp)
        raise ValueError(f"Unknown action: {action}")

    def _reflect(self, inp):
        dt    = inp.get("draft_type","issue"); draft=inp.get("draft",{})
        checks={}
        if dt=="issue":
            checks["has_title"]               = {"pass": bool(draft.get("title") and "Untitled" not in draft.get("title","")), "note": (draft.get("title","") or "missing")[:60]}
            checks["has_problem"]             = {"pass": len(draft.get("problem",""))>20, "note":"Present" if draft.get("problem") else "Missing"}
            checks["has_evidence"]            = {"pass": bool(draft.get("evidence") and "No evidence" not in draft.get("evidence","")), "note":"Present" if draft.get("evidence") else "Missing"}
            checks["has_acceptance_criteria"] = {"pass": "[ ]" in draft.get("acceptance_criteria",""), "note":"Present" if "[ ]" in draft.get("acceptance_criteria","") else "Missing"}
            checks["has_risk"]                = {"pass": draft.get("risk") in ["low","medium","high"], "note":f"Risk: {draft.get('risk','not set')}"}
        else:
            checks["has_title"]          = {"pass": bool(draft.get("title") and "Untitled" not in draft.get("title","")), "note": (draft.get("title","") or "missing")[:60]}
            checks["has_summary"]        = {"pass": len(draft.get("summary",""))>20, "note":"Present" if draft.get("summary") else "Missing"}
            checks["has_files_affected"] = {"pass": len(draft.get("files_affected",[]))>0, "note":f"{len(draft.get('files_affected',[]))} files"}
            checks["has_test_plan"]      = {"pass": "[ ]" in draft.get("test_plan",""), "note":"Present" if "[ ]" in draft.get("test_plan","") else "Missing"}
            checks["has_behavior_change"]= {"pass": len(draft.get("behavior_change",""))>10, "note":"Present" if draft.get("behavior_change") else "Missing"}
            checks["has_risk"]           = {"pass": draft.get("risk") in ["low","medium","high"], "note":f"Risk: {draft.get('risk','not set')}"}
        failed      = [k for k,v in checks.items() if not v["pass"]]
        verdict     = "FAIL" if failed else "PASS"
        fail_reason = failed[0].replace("_"," ").replace("has ","missing ") if failed else ""
        r={"verdict":verdict,"checks":checks,"fail_reason":fail_reason,"passed":len(checks)-len(failed),"total":len(checks)}
        return {"output":r,"artifacts":[{"type":"reflection","data":r}]}

    def _create(self, inp):
        dt    = inp.get("draft_type","issue"); draft=inp.get("draft",{})
        if dt=="issue":
            body = f"## Problem Description\n\n{draft.get('problem','')}\n\n## Evidence\n\n{draft.get('evidence','')}\n\n## Acceptance Criteria\n\n{draft.get('acceptance_criteria','')}\n\n## Risk Level\n\n**{draft.get('risk','medium').upper()}**\n\n---\n*Created by GitHub Repository Agent (MCP+A2A)*"
            raw  = self.github.call("github_create_issue",{"title":draft.get("title","Untitled"),"body":body,"labels":draft.get("labels",[])})
        else:
            files = '\n'.join(f"- `{f}`" for f in draft.get("files_affected",[]))
            body  = f"## Summary\n\n{draft.get('summary','')}\n\n## Files Affected\n\n{files or '_None_'}\n\n## Behavior Change\n\n{draft.get('behavior_change','')}\n\n## Test Plan\n\n{draft.get('test_plan','')}\n\n## Risk Level\n\n**{draft.get('risk','medium').upper()}**\n\n---\n*Created by GitHub Repository Agent (MCP+A2A)*"
            raw   = self.github.call("github_create_pr",{"title":draft.get("title","Untitled"),"body":body})
        try:    result=json.loads(raw)
        except: result={"success":False,"error":raw}
        return {"output":result,"artifacts":[{"type":"creation_result","data":result}]}

if __name__=="__main__":
    import time
    a = GatekeeperAgent(); a.start()
    print("[A2A] Gatekeeper ready on port 8204")
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt: a.stop()
