"""
A2A Orchestrator — starts MCP servers and A2A agents in background,
then routes CLI commands through the A2A protocol.

Port map:
  8101  git-tools MCP
  8102  github-tools MCP
  8201  Reviewer A2A
  8202  Planner  A2A
  8203  Writer   A2A
  8204  Gatekeeper A2A
"""

import sys, json, time, subprocess
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parent.parent
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

from a2a.protocol import A2AClient, MCPClient
from display import Display

URLS = {
    "git_mcp":    "http://localhost:8101",
    "github_mcp": "http://localhost:8102",
    "reviewer":   "http://localhost:8201",
    "planner":    "http://localhost:8202",
    "writer":     "http://localhost:8203",
    "gatekeeper": "http://localhost:8204",
}
a2a     = A2AClient()
display = Display()


def _start_servers():
    servers = [
        [sys.executable, str(AGENT_DIR/"mcp_servers/git_mcp.py"),    "8101"],
        [sys.executable, str(AGENT_DIR/"mcp_servers/github_mcp.py"), "8102"],
        [sys.executable, str(AGENT_DIR/"a2a/reviewer_agent.py")],
        [sys.executable, str(AGENT_DIR/"a2a/planner_agent.py")],
        [sys.executable, str(AGENT_DIR/"a2a/writer_agent.py")],
        [sys.executable, str(AGENT_DIR/"a2a/gatekeeper_agent.py")],
    ]
    procs = [subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
             for cmd in servers]

    display.step("Orchestrator", "Starting MCP servers + A2A agents...")
    for url_key, url in URLS.items():
        client = MCPClient(url) if "mcp" in url_key else None
        checker = client.is_available if client else lambda: a2a.is_available(url)
        for _ in range(20):
            if checker(): break
            time.sleep(0.4)
    display.step("Orchestrator", "All services ready.")
    return procs


def _print_draft(draft, draft_type):
    print(f"Title  : {draft.get('title','N/A')}")
    if draft_type == "issue":
        print(f"\nProblem:\n{draft.get('problem','')}")
        print(f"\nEvidence:\n{draft.get('evidence','')}")
        print(f"\nAcceptance Criteria:\n{draft.get('acceptance_criteria','')}")
        print(f"\nRisk Level: {draft.get('risk','medium')}")
    else:
        print(f"\nSummary:\n{draft.get('summary','')}")
        print(f"\nFiles Affected: {', '.join(draft.get('files_affected',[]))}")
        print(f"\nBehavior Change:\n{draft.get('behavior_change','')}")
        print(f"\nTest Plan:\n{draft.get('test_plan','')}")
        print(f"\nRisk Level: {draft.get('risk','medium')}")


def _run_review(args, state):
    display.header("GitHub Repository Agent — Review (MCP + A2A)")
    inp = {"base": args.base or "main"}
    if args.range: inp["range"] = args.range

    display.step("Orchestrator→Reviewer", "Sending analyze_diff via A2A...")
    resp = a2a.send_task(URLS["reviewer"], "analyze_diff", inp)
    if resp["status"] == "failed":
        display.error(f"Reviewer failed: {resp.get('error')}"); return

    review = resp["output"]
    display.result("Reviewer", review.get("summary",""))
    print("\n" + "="*60 + "\n📋 REVIEW ANALYSIS\n" + "="*60)
    print(f"Category     : {review.get('category','?')}")
    print(f"Risk Level   : {review.get('risk','?')}")
    print(f"Issues Found : {len(review.get('issues',[]))}")
    for i in review.get("issues",[]): print(f"  • {i}")

    display.step("Orchestrator→Planner", "Sending decide_action via A2A...")
    resp2 = a2a.send_task(URLS["planner"], "decide_action", {"review": review})
    decision = resp2["output"]
    display.result("Planner", f"Recommended action: {decision.get('action')}")
    print(f"\n🎯 PLANNER DECISION: {decision.get('action')}")
    print(f"   Justification: {decision.get('justification')}")

    saved = state.load()
    state.save({**saved, "last_review": review, "last_plan": decision,
                "last_diff": review.get("diff",""), "changed_files": review.get("changed_files",[])})
    print("\n✅ Review complete. Use 'agent draft' to create an Issue or PR.")


def _run_draft(args, state):
    draft_type = args.type
    display.header(f"GitHub Repository Agent — Draft {draft_type.upper()} (MCP + A2A)")

    saved       = state.load()
    instruction = getattr(args, "instruction", None)
    review      = saved.get("last_review", {})
    diff        = saved.get("last_diff", "")
    files       = saved.get("changed_files", [])

    display.step("Orchestrator→Planner", "Sending plan_draft via A2A...")
    plan_resp = a2a.send_task(URLS["planner"], "plan_draft", {
        "draft_type": draft_type, "instruction": instruction or "",
        "review": review, "diff": diff, "changed_files": files
    })
    if plan_resp["status"] == "failed":
        display.error(f"Planner failed: {plan_resp.get('error')}"); return
    plan = plan_resp["output"]
    display.result("Planner", "Scope validated.")

    display.step("Orchestrator→Writer", "Sending write_draft via A2A...")
    write_resp = a2a.send_task(URLS["writer"], "write_draft", {
        "draft_type": draft_type, "plan": plan, "diff": diff,
        "changed_files": files, "instruction": instruction or "", "review": review
    })
    if write_resp["status"] == "failed":
        display.error(f"Writer failed: {write_resp.get('error')}"); return
    draft = write_resp["output"]
    display.result("Writer", f"Draft {draft_type.upper()} created.")

    display.step("Orchestrator→Gatekeeper", "Sending reflect via A2A...")
    ref_resp   = a2a.send_task(URLS["gatekeeper"], "reflect", {"draft_type": draft_type, "draft": draft})
    reflection = ref_resp["output"]

    print("\n" + "="*60 + f"\n📝 DRAFT {draft_type.upper()}\n" + "="*60)
    _print_draft(draft, draft_type)
    print("\n" + "="*60 + "\n🔍 REFLECTION REPORT\n" + "="*60)
    print(f"Verdict : {reflection['verdict']}")
    for check, res in reflection["checks"].items():
        print(f"  {'✅' if res['pass'] else '❌'} {check}: {res['note']}")

    if reflection["verdict"] == "FAIL":
        display.result("Gatekeeper", f"Reflection verdict: FAIL – {reflection['fail_reason']}. Revision required.")
        display.step("Orchestrator→Writer", "Sending revise_draft via A2A...")
        rev = a2a.send_task(URLS["writer"], "revise_draft",
                            {"draft_type": draft_type, "draft": draft, "reflection": reflection})
        draft      = rev["output"]
        reflection = a2a.send_task(URLS["gatekeeper"], "reflect",
                                   {"draft_type": draft_type, "draft": draft})["output"]
        print(f"\n📝 REVISED — Re-reflection: {reflection['verdict']}")
        _print_draft(draft, draft_type)
    else:
        display.result("Gatekeeper", "Reflection verdict: PASS.")

    state.save({**saved, "pending_draft": draft, "pending_type": draft_type})
    print("\n💡 Run 'agent approve --yes' to create or '--no' to reject.")


def _run_approve(args, state):
    display.header("GitHub Repository Agent — Approval Gate (MCP + A2A)")
    saved      = state.load()
    draft      = saved.get("pending_draft")
    draft_type = saved.get("pending_type")
    if not draft:
        display.error("No pending draft. Run 'agent draft' first."); return

    if args.yes:
        display.step("Orchestrator→Gatekeeper", "Sending create_item via A2A...")
        resp   = a2a.send_task(URLS["gatekeeper"], "create_item", {"draft_type": draft_type, "draft": draft})
        result = resp["output"]
        if result.get("success"):
            display.result("Tool", "GitHub API call successful.")
            demo = " (DEMO MODE)" if result.get("demo") else ""
            print(f"\n✅ {draft_type.upper()} created{demo}!")
            print(f"   URL   : {result.get('url')}")
            print(f"   Number: #{result.get('number')}")
            state.save({k:v for k,v in saved.items() if k not in ["pending_draft","pending_type"]})
        else:
            display.error(f"Creation failed: {result.get('error')}")
    else:
        display.result("Gatekeeper", "Draft rejected. No changes made.")
        print("\n🚫 Aborted safely. Nothing was created on GitHub.")
        state.save({k:v for k,v in saved.items() if k not in ["pending_draft","pending_type"]})


def _run_improve(args, state):
    item_type = args.type
    number    = args.number
    display.header(f"GitHub Repository Agent — Improve {item_type.upper()} #{number} (MCP + A2A)")

    github = MCPClient(URLS["github_mcp"], "github-tools")
    display.step("Orchestrator→MCP", f"Fetching {item_type} #{number}...")
    tool = "github_get_issue" if item_type == "issue" else "github_get_pr"
    item = github.call_json(tool, {"number": number})
    display.result("Tool", f"Fetched: '{item.get('title','')}'")

    display.step("Orchestrator→Reviewer", "Sending critique_item via A2A...")
    crit    = a2a.send_task(URLS["reviewer"], "critique_item", {"type": item_type, "item": item})["output"]
    display.result("Reviewer", f"Found {len(crit.get('findings',[]))} issues.")

    print("\n" + "="*60 + f"\n🔎 CRITIQUE OF {item_type.upper()} #{number}\n" + "="*60)
    print(f"Title  : {item.get('title','')}")
    for f in crit.get("findings",[]): print(f"  ⚠️  {f}")

    display.step("Orchestrator→Writer", "Sending write_improvement via A2A...")
    improved   = a2a.send_task(URLS["writer"], "write_improvement",
                               {"type": item_type, "item": item, "critique": crit})["output"]
    display.result("Writer", "Proposed improved structured version.")

    display.step("Orchestrator→Gatekeeper", "Sending reflect via A2A...")
    reflection = a2a.send_task(URLS["gatekeeper"], "reflect",
                                {"draft_type": item_type, "draft": improved})["output"]

    print("\n" + "="*60 + f"\n✨ PROPOSED IMPROVED {item_type.upper()}\n" + "="*60)
    _print_draft(improved, item_type)
    print("\n" + "="*60 + "\n🔍 REFLECTION REPORT\n" + "="*60)
    for check, res in reflection["checks"].items():
        print(f"  {'✅' if res['pass'] else '❌'} {check}: {res['note']}")
    display.result("Gatekeeper", f"Reflection verdict: {reflection['verdict']}.")
    print("\n💡 Suggestion only — apply via GitHub web UI.")


def run(args):
    """Entry point called from agent.py --mode mcp-a2a"""
    from state import AgentState
    state = AgentState(AGENT_DIR / ".agent_state.json")
    procs = _start_servers()
    try:
        if args.command == "review":    _run_review(args, state)
        elif args.command == "draft":   _run_draft(args, state)
        elif args.command == "approve": _run_approve(args, state)
        elif args.command == "improve": _run_improve(args, state)
    finally:
        for p in procs: p.terminate()
