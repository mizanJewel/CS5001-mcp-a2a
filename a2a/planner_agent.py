#!/usr/bin/env python3
"""Planner A2A Agent (port 8202)"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from a2a.protocol import A2AAgentServer
from ollama_client import OllamaClient

class PlannerAgent(A2AAgentServer):
    def __init__(self):
        super().__init__("planner", 8202)
        self.llm = OllamaClient()

    def handle_task(self, action, input_data, context):
        if action == "decide_action": return self._decide(input_data)
        if action == "plan_draft":    return self._plan(input_data)
        raise ValueError(f"Unknown action: {action}")

    def _decide(self, inp):
        review = inp.get("review",{}); issues = review.get("issues",[]); risk = review.get("risk","medium")
        action = review.get("recommended_action","no_action"); just = review.get("action_justification","")
        if risk=="high" and action=="no_action":
            action="create_issue"; just=f"High risk: {'; '.join(issues[:2])}"
        elif not issues and action!="create_pr":
            action="no_action"; just="No significant issues found"
        d={"action":action,"justification":just,"risk":risk,"issue_count":len(issues)}
        return {"output":d,"artifacts":[{"type":"decision","data":d}]}

    def _plan(self, inp):
        dt = inp.get("draft_type","issue"); inst = inp.get("instruction","")
        review = inp.get("review",{}); diff = inp.get("diff","")[:2000]; files = inp.get("changed_files",[])
        prompt = (f"Plan a GitHub {dt}.\nInstruction: {inst}\nFiles: {', '.join(files)}\nDiff: {diff}\n"
                  if inst else
                  f"Plan a GitHub {dt} from review.\nSummary: {review.get('summary','')}\nIssues: {json.dumps(review.get('issues',[]))}\n")
        prompt += f"""Respond ONLY valid JSON:
{{"key_points":["p1"],"affected_areas":["a1"],"risk_assessment":"medium","evidence":["e1"],"test_suggestions":["t1"]}}"""
        raw = self.llm.chat(prompt, system="Technical planner. Valid JSON only.")
        plan = self._parse(raw, {"key_points":["Address missing validation","Add error handling","Add unit tests"],
            "affected_areas":["RAG pipeline"],"risk_assessment":"medium",
            "evidence":["Diff shows no validation logic"],"test_suggestions":["Test empty query","Integration test"]})
        return {"output":plan,"artifacts":[{"type":"plan","data":plan}]}

    def _parse(self, raw, defaults):
        try:
            c = raw.strip().strip("```json").strip("```").strip()
            s,e = c.find("{"), c.rfind("}")+1
            if s>=0 and e>s: return {**defaults, **json.loads(c[s:e])}
        except: pass
        return defaults

if __name__=="__main__":
    import time
    a = PlannerAgent(); a.start()
    print("[A2A] Planner ready on port 8202")
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt: a.stop()
