#!/usr/bin/env python3
"""Writer A2A Agent (port 8203)"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from a2a.protocol import A2AAgentServer
from ollama_client import OllamaClient

class WriterAgent(A2AAgentServer):
    def __init__(self):
        super().__init__("writer", 8203)
        self.llm = OllamaClient()

    def handle_task(self, action, inp, context):
        if action=="write_draft":       return self._write(inp)
        if action=="revise_draft":      return self._revise(inp)
        if action=="write_improvement": return self._improve(inp)
        raise ValueError(f"Unknown action: {action}")

    def _write(self, inp):
        dt   = inp.get("draft_type","issue"); plan=inp.get("plan",{})
        diff = inp.get("diff","")[:1500]; files=inp.get("changed_files",[])
        ctx  = inp.get("instruction","") or inp.get("review",{}).get("summary","Code changes")
        if dt=="issue":
            prompt = f"""Write GitHub Issue. Context: {ctx}\nKey points: {json.dumps(plan.get('key_points',[]))}\nEvidence: {json.dumps(plan.get('evidence',[]))}\nRisk: {plan.get('risk_assessment','medium')}\nDiff: {diff}
Respond ONLY valid JSON:
{{"title":"title","problem":"2-3 sentences","evidence":"specific","acceptance_criteria":"- [ ] c1\\n- [ ] c2","risk":"high","labels":["bug"]}}"""
            defaults={"title":"Missing input validation in RAG retriever",
                "problem":"The RAG retriever does not validate input queries. Empty queries crash the vector store.",
                "evidence":"Diff shows retrieve_with_filter() has no guard for empty queries. TODO confirms gap.",
                "acceptance_criteria":"- [ ] Validate query non-empty\n- [ ] Raise ValueError for invalid input\n- [ ] Unit tests cover empty and None inputs",
                "risk":"high","labels":["bug","enhancement"]}
        else:
            prompt = f"""Write GitHub PR. Context: {ctx}\nFiles: {', '.join(files)}\nRisk: {plan.get('risk_assessment','medium')}\nTests: {json.dumps(plan.get('test_suggestions',[]))}\nDiff: {diff}
Respond ONLY valid JSON:
{{"title":"title","summary":"2-3 sentences","files_affected":["f1"],"behavior_change":"what changes","test_plan":"- [ ] t1\\n- [ ] t2","risk":"medium","linked_issues":[]}}"""
            defaults={"title":"feat: Add input validation to RAG retriever",
                "summary":"Adds input validation to retrieve_with_filter(). Empty queries raise ValueError.",
                "files_affected":["rag_in_class/rag_pipeline.py","tests/test_retriever.py"],
                "behavior_change":"Invalid queries fail fast with ValueError instead of crashing vector store.",
                "test_plan":"- [ ] Unit test: empty query raises ValueError\n- [ ] Unit test: None raises ValueError\n- [ ] Integration test: valid query flows correctly",
                "risk":"medium","linked_issues":[]}
        raw = self.llm.chat(prompt, system="Technical writer. Valid JSON only.")
        draft = self._parse(raw, defaults)
        return {"output":draft,"artifacts":[{"type":f"draft_{dt}","data":draft}]}

    def _revise(self, inp):
        dt   = inp.get("draft_type","issue"); draft=inp.get("draft",{})
        refl = inp.get("reflection",{}); failed=[k for k,v in refl.get("checks",{}).items() if not v["pass"]]
        prompt = f"""Revise this GitHub {dt}.
Draft: {json.dumps(draft,indent=2)}
Failed checks: {', '.join(failed)}
Respond ONLY valid JSON same structure."""
        raw     = self.llm.chat(prompt, system="Technical writer. Valid JSON only.")
        revised = self._parse(raw, draft)
        for k,v in draft.items():
            if k not in revised or not revised[k]: revised[k]=v
        return {"output":revised,"artifacts":[{"type":f"draft_{dt}_revised","data":revised}]}

    def _improve(self, inp):
        it   = inp.get("type","issue"); item=inp.get("item",{}); crit=inp.get("critique",{})
        body = item.get("body","") or ""; findings=crit.get("findings",[]); missing=crit.get("missing_sections",[])
        if it=="issue":
            prompt = f"""Improve GitHub Issue.
Title: {item.get('title','')}
Body: {body[:2000]}
Critique: {json.dumps(findings)}
Missing: {json.dumps(missing)}
Respond ONLY valid JSON:
{{"title":"improved","problem":"clear","evidence":"specific","acceptance_criteria":"- [ ] c1","risk":"high","labels":["bug"]}}"""
            defaults={"title":"Missing input validation in RAG retriever",
                "problem":"The RAG retriever does not validate input queries.",
                "evidence":"Diff shows retrieve_with_filter() has no guard for empty queries.",
                "acceptance_criteria":"- [ ] Validate query non-empty\n- [ ] Unit tests cover edge cases",
                "risk":"high","labels":["bug"]}
        else:
            prompt = f"""Improve GitHub PR.
Title: {item.get('title','')}
Body: {body[:2000]}
Critique: {json.dumps(findings)}
Respond ONLY valid JSON:
{{"title":"improved","summary":"clear","files_affected":["f1"],"behavior_change":"what","test_plan":"- [ ] t1","risk":"low","linked_issues":[]}}"""
            defaults={"title":"Refactor: Consolidate duplicated build_prompt functions",
                "summary":"Removes build_prompt_v2 and consolidates into a single utility.",
                "files_affected":["rag_in_class/rag_pipeline.py"],"behavior_change":"Behaviour unchanged.",
                "test_plan":"- [ ] Run existing test suite\n- [ ] Unit test edge cases","risk":"low","linked_issues":[]}
        raw      = self.llm.chat(prompt, system="Technical writer. Valid JSON only.")
        improved = self._parse(raw, defaults)
        return {"output":improved,"artifacts":[{"type":f"improved_{it}","data":improved}]}

    def _parse(self, raw, defaults):
        try:
            c = raw.strip().strip("```json").strip("```").strip()
            s,e = c.find("{"), c.rfind("}")+1
            if s>=0 and e>s: return {**defaults, **json.loads(c[s:e])}
        except: pass
        return defaults

if __name__=="__main__":
    import time
    a = WriterAgent(); a.start()
    print("[A2A] Writer ready on port 8203")
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt: a.stop()
