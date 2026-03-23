"""
Gatekeeper Agent - Reflects on drafts, enforces human approval, creates on GitHub
Pattern: Reflection + Safety Gate
"""

import json
from ollama_client import OllamaClient


class GatekeeperAgent:
    def __init__(self):
        self.llm = OllamaClient()
        self.role = "Gatekeeper"

    def reflect(self, draft_type: str, draft: dict) -> dict:
        """Reflection step: check draft quality and safety."""
        checks = {}

        if draft_type == "issue":
            checks["has_title"] = {
                "pass": bool(draft.get("title") and draft["title"] != "Untitled Issue"),
                "note": draft.get("title", "missing")[:60]
            }
            checks["has_problem"] = {
                "pass": bool(draft.get("problem") and len(draft.get("problem", "")) > 20),
                "note": "Problem description present" if draft.get("problem") else "Missing problem description"
            }
            checks["has_evidence"] = {
                "pass": bool(draft.get("evidence") and "No evidence" not in draft.get("evidence", "")),
                "note": "Evidence provided" if draft.get("evidence") else "Missing evidence"
            }
            checks["has_acceptance_criteria"] = {
                "pass": bool(draft.get("acceptance_criteria") and "[ ]" in draft.get("acceptance_criteria", "")),
                "note": "Criteria present" if "[ ]" in draft.get("acceptance_criteria", "") else "Missing acceptance criteria"
            }
            checks["has_risk"] = {
                "pass": draft.get("risk") in ["low", "medium", "high"],
                "note": f"Risk: {draft.get('risk', 'not set')}"
            }
        else:
            checks["has_title"] = {
                "pass": bool(draft.get("title") and draft["title"] != "Untitled PR"),
                "note": draft.get("title", "missing")[:60]
            }
            checks["has_summary"] = {
                "pass": bool(draft.get("summary") and len(draft.get("summary", "")) > 20),
                "note": "Summary present" if draft.get("summary") else "Missing summary"
            }
            checks["has_files_affected"] = {
                "pass": bool(draft.get("files_affected") and len(draft.get("files_affected", [])) > 0),
                "note": f"{len(draft.get('files_affected', []))} files listed"
            }
            checks["has_test_plan"] = {
                "pass": bool(draft.get("test_plan") and "[ ]" in draft.get("test_plan", "")),
                "note": "Test plan present" if "[ ]" in draft.get("test_plan", "") else "Missing test plan"
            }
            checks["has_behavior_change"] = {
                "pass": bool(draft.get("behavior_change") and len(draft.get("behavior_change", "")) > 10),
                "note": "Behavior change described" if draft.get("behavior_change") else "Missing behavior change"
            }
            checks["has_risk"] = {
                "pass": draft.get("risk") in ["low", "medium", "high"],
                "note": f"Risk: {draft.get('risk', 'not set')}"
            }

        failed = [k for k, v in checks.items() if not v["pass"]]
        passed = len(checks) - len(failed)

        if failed:
            fail_reason = failed[0].replace("_", " ").replace("has ", "missing ")
            verdict = "FAIL"
        else:
            fail_reason = ""
            verdict = "PASS"

        return {
            "verdict": verdict,
            "checks": checks,
            "fail_reason": fail_reason,
            "passed": passed,
            "total": len(checks)
        }

    def create(self, draft_type: str, draft: dict, github_tools) -> dict:
        """Create the Issue or PR on GitHub after human approval."""
        if draft_type == "issue":
            body = self._format_issue_body(draft)
            return github_tools.create_issue(
                title=draft.get("title", "Untitled"),
                body=body,
                labels=draft.get("labels", [])
            )
        else:
            body = self._format_pr_body(draft)
            return github_tools.create_pr(
                title=draft.get("title", "Untitled"),
                body=body
            )

    def _format_issue_body(self, draft: dict) -> str:
        return f"""## Problem Description

{draft.get('problem', '')}

## Evidence

{draft.get('evidence', '')}

## Acceptance Criteria

{draft.get('acceptance_criteria', '')}

## Risk Level

**{draft.get('risk', 'medium').upper()}**

---
*Created by GitHub Repository Agent*"""

    def _format_pr_body(self, draft: dict) -> str:
        files = '\n'.join(f"- `{f}`" for f in draft.get("files_affected", []))
        linked = '\n'.join(f"- #{n}" for n in draft.get("linked_issues", []))
        
        return f"""## Summary

{draft.get('summary', '')}

## Files Affected

{files or '_None listed_'}

## Behavior Change

{draft.get('behavior_change', '')}

## Test Plan

{draft.get('test_plan', '')}

## Risk Level

**{draft.get('risk', 'medium').upper()}**

{f'## Linked Issues{chr(10)}{linked}' if linked else ''}

---
*Created by GitHub Repository Agent*"""
