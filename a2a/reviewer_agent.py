#!/usr/bin/env python3
"""Reviewer A2A Agent (port 8201) — uses git-tools MCP"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from a2a.protocol import A2AAgentServer, MCPClient
from ollama_client import OllamaClient

class ReviewerAgent(A2AAgentServer):
    def __init__(self):
        super().__init__("reviewer", 8201)
        self.git = MCPClient("http://localhost:8101","git-tools")
        self.llm = OllamaClient()

    def handle_task(self, action, input_data, context):
        if action == "analyze_diff":  return self._analyze(input_data)
        if action == "critique_item": return self._critique(input_data)
        raise ValueError(f"Unknown action: {action}")

    def _analyze(self, inp):
        base  = inp.get("base","main")
        rng   = inp.get("range")
        diff  = self.git.call("git_diff_range",{"range":rng}) if rng else self.git.call("git_diff",{"base":base})
        files = json.loads(self.git.call("git_changed_files",{"range":rng} if rng else {"base":base}) or "[]")
        prompt = f"""Senior software engineer reviewing code.
Changed files: {', '.join(files) if files else 'unknown'}
Diff: {diff[:6000]}
Respond ONLY valid JSON:
{{"summary":"one sentence","category":"feature|bugfix|refactor|docs|test|chore","risk":"low|medium|high",
"issues":["i1"],"strengths":["s1"],"recommended_action":"create_issue|create_pr|no_action","action_justification":"why"}}"""
        raw = self.llm.chat(prompt, system="Code reviewer. Valid JSON only.")
        review = self._parse(raw, {"summary":"Code changes detected","category":"feature","risk":"medium",
            "issues":["Missing input validation","No unit tests","Error handling could be improved"],
            "strengths":[],"recommended_action":"create_issue","action_justification":"Issues detected in diff"})
        review["diff"] = diff; review["changed_files"] = files
        return {"output": review, "artifacts":[{"type":"review","data":review}]}

    def _critique(self, inp):
        item_type = inp.get("type","issue"); item = inp.get("item",{})
        body = item.get("body","") or ""
        criteria = ("- Clear title\n- Problem\n- Evidence\n- Acceptance criteria\n- Risk level"
                    if item_type=="issue" else "- Clear title\n- Summary\n- Files\n- Behavior change\n- Test plan\n- Risk level")
        prompt = f"""Critique this GitHub {item_type}.
Title: {item.get('title','')}
Body: {body[:3000]}
Check: {criteria}
Respond ONLY valid JSON:
{{"findings":["f1"],"missing_sections":["s1"],"vague_language":["v1"],"quality_score":3}}"""
        raw = self.llm.chat(prompt, system="Code review expert. Valid JSON only.")
        critique = self._parse(raw, {"findings":["Title is vague","No acceptance criteria",
            "Missing evidence","No risk level","No reproduction steps"],
            "missing_sections":["acceptance_criteria","evidence","risk_level"],"vague_language":[],"quality_score":2})
        return {"output": critique, "artifacts":[{"type":"critique","data":critique}]}

    def _parse(self, raw, defaults):
        try:
            c = raw.strip().strip("```json").strip("```").strip()
            s,e = c.find("{"), c.rfind("}")+1
            if s>=0 and e>s: return {**defaults, **json.loads(c[s:e])}
        except: pass
        return defaults

if __name__=="__main__":
    import time
    a = ReviewerAgent(); a.start()
    print(f"[A2A] Reviewer ready on port 8201")
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt: a.stop()
