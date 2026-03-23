#!/usr/bin/env python3
"""
GitHub Repository Agent — CLI Entry Point
Model: gpt-oss:120b-cloud (via Ollama)
Repo:  mizanJewel/CS5001-Prompting-With-RAG

Modes:
  --mode standard   Original direct-import architecture (default)
  --mode mcp-a2a    MCP tooling + A2A agent communication

Usage (run from INSIDE your repo):
  python3 ../agent.py review --base main
  python3 ../agent.py --mode mcp-a2a review --base main
"""

import argparse
import sys
import json
from pathlib import Path

# Always resolve imports relative to agent.py's own folder,
# so `python3 ../agent.py` works from inside any repo.
AGENT_DIR = Path(__file__).resolve().parent
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))


# -----------------------------------------------------------------
# LAZY LOADER
# Standard-mode modules (reviewer, planner etc.) are only imported
# when actually needed — so --mode mcp-a2a never tries to load them.
# -----------------------------------------------------------------

def _load_standard_modules():
    try:
        from reviewer   import ReviewerAgent
        from planner    import PlannerAgent
        from writer     import WriterAgent
        from gatekeeper import GatekeeperAgent
        from git_tools  import GitTools
        from github_tools import GitHubTools
        from display    import Display
        return ReviewerAgent, PlannerAgent, WriterAgent, GatekeeperAgent, GitTools, GitHubTools, Display
    except ModuleNotFoundError as e:
        print(f"\n[Error] Standard-mode module missing: {e}")
        print("  Make sure agent.py is in the same folder as reviewer.py, planner.py etc.")
        print("  Or run with: python3 agent.py --mode mcp-a2a <command>")
        sys.exit(1)


def _load_state():
    from state import AgentState
    return AgentState(AGENT_DIR / ".agent_state.json")


# -----------------------------------------------------------------
# STANDARD MODE
# -----------------------------------------------------------------

def cmd_review(args):
    ReviewerAgent, PlannerAgent, _, _, GitTools, _, Display = _load_standard_modules()
    state   = _load_state()
    display = Display()
    display.header("GitHub Repository Agent — Review Mode")
    display.step("Tool", "Model: gpt-oss:120b-cloud | Repo: mizanJewel/CS5001-Prompting-With-RAG")

    git      = GitTools()
    reviewer = ReviewerAgent()
    planner  = PlannerAgent()

    display.step("Tool", "Fetching git diff...")
    if args.range:
        diff    = git.get_diff_range(args.range)
        context = f"Commit range: {args.range}"
    else:
        base    = args.base or "main"
        diff    = git.get_diff_base(base)
        context = f"Changes vs base: {base}"

    if not diff.strip():
        display.info("No changes detected.")
        return

    display.step("Tool", f"Diff retrieved ({len(diff)} chars, {context})")
    changed_files = git.get_changed_files(args.base or "main", args.range)
    display.step("Tool", f"Changed files: {', '.join(changed_files) if changed_files else 'none'}")

    display.step("Reviewer", "Analyzing code changes...")
    review_result = reviewer.analyze(diff, changed_files, context)
    display.result("Reviewer", review_result["summary"])

    print("\n" + "="*60)
    print("REVIEW ANALYSIS")
    print("="*60)
    print(f"Category     : {review_result['category']}")
    print(f"Risk Level   : {review_result['risk']}")
    print(f"Issues Found : {len(review_result['issues'])}")
    for issue in review_result["issues"]:
        print(f"  * {issue}")

    display.step("Planner", "Deciding recommended action...")
    plan = planner.decide(review_result)
    display.result("Planner", f"Recommended action: {plan['action']}")
    print(f"\nPLANNER DECISION: {plan['action']}")
    print(f"   Justification: {plan['justification']}")

    state.save({"last_review": review_result, "last_plan": plan,
                "last_diff": diff, "changed_files": changed_files})
    print("\nReview complete. Use 'agent draft' to create an Issue or PR.")


def cmd_draft(args):
    ReviewerAgent, PlannerAgent, WriterAgent, GatekeeperAgent, GitTools, _, Display = _load_standard_modules()
    state      = _load_state()
    display    = Display()
    draft_type = args.type
    display.header(f"GitHub Repository Agent — Draft {draft_type.upper()} Mode")

    git        = GitTools()
    planner    = PlannerAgent()
    writer     = WriterAgent()
    gatekeeper = GatekeeperAgent()
    saved      = state.load()
    instruction = getattr(args, "instruction", None)

    if instruction:
        display.step("Planner", f"Explicit instruction received: '{instruction}'")
        diff           = git.get_diff_base("main")
        changed_files  = git.get_changed_files("main")
        review_context = {"instruction": instruction, "diff": diff,
                          "changed_files": changed_files, "source": "explicit"}
    elif saved.get("last_review"):
        display.step("Planner", "Using previous review results as context...")
        review_context = {"review": saved["last_review"], "diff": saved.get("last_diff", ""),
                          "changed_files": saved.get("changed_files", []), "source": "review"}
    else:
        display.error("No instruction provided and no prior review found.")
        print("  Run: agent review, or use --instruction flag")
        return

    display.step("Planner", f"Planning {draft_type} structure...")
    plan = planner.plan_draft(draft_type, review_context)
    display.result("Planner", "Scope validated.")

    display.step("Writer", f"Drafting {draft_type}...")
    draft = writer.write(draft_type, plan, review_context)
    display.result("Writer", f"Draft {draft_type.upper()} created.")

    display.step("Gatekeeper", "Running reflection check...")
    reflection = gatekeeper.reflect(draft_type, draft)

    print("\n" + "="*60)
    print(f"DRAFT {draft_type.upper()}")
    print("="*60)
    _print_draft(draft, draft_type)

    print("\n" + "="*60)
    print("REFLECTION REPORT")
    print("="*60)
    print(f"Verdict : {reflection['verdict']}")
    for check, result in reflection["checks"].items():
        icon = "PASS" if result["pass"] else "FAIL"
        print(f"  [{icon}] {check}: {result['note']}")

    if reflection["verdict"] == "FAIL":
        display.result("Gatekeeper", f"Reflection verdict: FAIL - {reflection['fail_reason']}. Revision required.")
        display.step("Writer", "Revising draft (1 retry max)...")
        draft      = writer.revise(draft_type, draft, reflection)
        display.result("Writer", "Draft revised.")
        reflection = gatekeeper.reflect(draft_type, draft)
        print("\n" + "="*60)
        print(f"REVISED DRAFT {draft_type.upper()}")
        print("="*60)
        _print_draft(draft, draft_type)
        print(f"\nRe-reflection: {reflection['verdict']}")
        if reflection["verdict"] == "FAIL":
            display.result("Gatekeeper", f"Still failing: {reflection['fail_reason']}. Manual review needed.")
    else:
        display.result("Gatekeeper", "Reflection verdict: PASS.")

    state.save({**saved, "pending_draft": draft, "pending_type": draft_type})
    print("\nRun 'agent approve --yes' to create or '--no' to reject.")


def cmd_approve(args):
    _, _, _, GatekeeperAgent, _, GitHubTools, Display = _load_standard_modules()
    state      = _load_state()
    display    = Display()
    display.header("GitHub Repository Agent — Approval Gate")

    saved      = state.load()
    draft      = saved.get("pending_draft")
    draft_type = saved.get("pending_type")

    if not draft:
        display.error("No pending draft found. Run 'agent draft' first.")
        return

    github     = GitHubTools()
    gatekeeper = GatekeeperAgent()

    if args.yes:
        display.step("Gatekeeper", f"Creating {draft_type.upper()} on GitHub...")
        result = gatekeeper.create(draft_type, draft, github)
        if result["success"]:
            display.result("Tool", "GitHub API call successful.")
            print(f"\n{draft_type.upper()} created!")
            print(f"   URL   : {result['url']}")
            print(f"   Number: #{result['number']}")
            _log_creation(draft_type, draft, result)
            state.save({k: v for k, v in saved.items()
                        if k not in ["pending_draft", "pending_type"]})
        else:
            display.error(f"GitHub API failed: {result['error']}")
    else:
        display.result("Gatekeeper", "Draft rejected. No changes made.")
        print("\nAborted safely. Nothing was created on GitHub.")
        state.save({k: v for k, v in saved.items()
                    if k not in ["pending_draft", "pending_type"]})


def cmd_improve(args):
    ReviewerAgent, _, WriterAgent, GatekeeperAgent, _, GitHubTools, Display = _load_standard_modules()
    state     = _load_state()
    display   = Display()
    item_type = args.type
    number    = args.number
    display.header(f"GitHub Repository Agent — Improve {item_type.upper()} #{number}")

    github     = GitHubTools()
    reviewer   = ReviewerAgent()
    writer     = WriterAgent()
    gatekeeper = GatekeeperAgent()

    display.step("Tool", f"Fetching {item_type} #{number} from GitHub...")
    item = github.get_item(item_type, number)
    if not item:
        display.error(f"Could not fetch {item_type} #{number}.")
        return
    display.result("Tool", f"Fetched: '{item['title']}'")

    display.step("Reviewer", f"Critiquing {item_type}...")
    critique = reviewer.critique(item_type, item)
    print("\n" + "="*60)
    print(f"CRITIQUE OF {item_type.upper()} #{number}")
    print("="*60)
    print(f"Title  : {item['title']}\n\nCritique:")
    for finding in critique["findings"]:
        print(f"  * {finding}")
    display.result("Reviewer", f"Found {len(critique['findings'])} issues.")

    display.step("Writer", "Drafting improved version...")
    improved = writer.improve(item_type, item, critique)
    display.result("Writer", "Proposed improved structured version.")

    display.step("Gatekeeper", "Running reflection on improved version...")
    reflection = gatekeeper.reflect(item_type, improved)

    print("\n" + "="*60)
    print(f"PROPOSED IMPROVED {item_type.upper()}")
    print("="*60)
    _print_draft(improved, item_type)

    print("\n" + "="*60)
    print("REFLECTION REPORT")
    print("="*60)
    print(f"Verdict: {reflection['verdict']}")
    for check, result in reflection["checks"].items():
        icon = "PASS" if result["pass"] else "FAIL"
        print(f"  [{icon}] {check}: {result['note']}")
    display.result("Gatekeeper", f"Reflection verdict: {reflection['verdict']}.")
    print(f"\nThis is a suggestion only. Apply via the GitHub web UI.")


# -----------------------------------------------------------------
# MCP + A2A MODE
# -----------------------------------------------------------------

def run_mcp_a2a(args):
    try:
        from a2a.orchestrator import run as a2a_run
        a2a_run(args)
    except ImportError as e:
        print(f"\n[Error] MCP+A2A mode unavailable: {e}")
        print("  Make sure the a2a/ folder is next to agent.py")
        sys.exit(1)


# -----------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------

def _print_draft(draft, draft_type):
    print(f"Title  : {draft.get('title', 'N/A')}")
    if draft_type == "issue":
        print(f"\nProblem:\n{draft.get('problem', '')}")
        print(f"\nEvidence:\n{draft.get('evidence', '')}")
        print(f"\nAcceptance Criteria:\n{draft.get('acceptance_criteria', '')}")
        print(f"\nRisk Level: {draft.get('risk', 'medium')}")
    else:
        print(f"\nSummary:\n{draft.get('summary', '')}")
        print(f"\nFiles Affected: {', '.join(draft.get('files_affected', []))}")
        print(f"\nBehavior Change:\n{draft.get('behavior_change', '')}")
        print(f"\nTest Plan:\n{draft.get('test_plan', '')}")
        print(f"\nRisk Level: {draft.get('risk', 'medium')}")


def _log_creation(draft_type, draft, result):
    log_file = AGENT_DIR / ".agent_log.json"
    logs = []
    if log_file.exists():
        try:
            logs = json.loads(log_file.read_text())
        except:
            pass
    logs.append({"type": draft_type, "number": result.get("number"),
                 "url": result.get("url"), "title": draft.get("title")})
    log_file.write_text(json.dumps(logs, indent=2))


# -----------------------------------------------------------------
# CLI
# -----------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        prog="agent",
        description="GitHub Repository Agent | Model: gpt-oss:120b-cloud"
    )
    parser.add_argument(
        "--mode", choices=["standard", "mcp-a2a"], default="standard",
        help="standard = direct imports (default) | mcp-a2a = MCP tools + A2A agents"
    )
    sub = parser.add_subparsers(dest="command")

    r = sub.add_parser("review")
    r.add_argument("--base", default="main")
    r.add_argument("--range")

    d = sub.add_parser("draft")
    d.add_argument("type", choices=["issue", "pr"])
    d.add_argument("--instruction", "-i")

    ap = sub.add_parser("approve")
    g  = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--yes", action="store_true")
    g.add_argument("--no",  action="store_true")

    im = sub.add_parser("improve")
    im.add_argument("type", choices=["issue", "pr"])
    im.add_argument("--number", "-n", type=int, required=True)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    # MCP+A2A mode — no standard modules needed at all
    if args.mode == "mcp-a2a":
        run_mcp_a2a(args)
        return

    # Standard mode — modules loaded lazily inside each cmd_ function
    if args.command == "review":    cmd_review(args)
    elif args.command == "draft":   cmd_draft(args)
    elif args.command == "approve": cmd_approve(args)
    elif args.command == "improve": cmd_improve(args)


if __name__ == "__main__":
    main()
