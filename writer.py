"""
Writer Agent - Drafts Issues and PRs, improves existing ones
Pattern: Tool Use
"""

import json
from ollama_client import OllamaClient


class WriterAgent:
    def __init__(self):
        self.llm = OllamaClient()
        self.role = "Writer"

    def write(self, draft_type: str, plan: dict, context: dict) -> dict:
        """Write a full Issue or PR draft."""
        instruction = context.get("instruction", "")
        review = context.get("review", {})
        diff_snippet = context.get("diff", "")[:1500]
        changed_files = context.get("changed_files", [])

        base_context = instruction or review.get("summary", "Code changes detected")

        if draft_type == "issue":
            return self._write_issue(base_context, plan, diff_snippet, changed_files)
        else:
            return self._write_pr(base_context, plan, diff_snippet, changed_files)

    def _write_issue(self, context: str, plan: dict, diff: str, files: list) -> dict:
        prompt = f"""Write a GitHub Issue based on:

Context: {context}
Key Points: {json.dumps(plan.get('key_points', []))}
Evidence: {json.dumps(plan.get('evidence', []))}
Risk: {plan.get('risk_assessment', 'medium')}
Diff snippet:
{diff}

Respond ONLY with valid JSON:
{{
  "title": "concise issue title",
  "problem": "clear problem description (2-3 sentences)",
  "evidence": "specific evidence from code or context",
  "acceptance_criteria": "- [ ] criterion 1\\n- [ ] criterion 2\\n- [ ] criterion 3",
  "risk": "low|medium|high",
  "labels": ["bug", "enhancement"]
}}"""

        response = self.llm.chat(prompt, system="You are a technical writer creating GitHub issues. Respond with valid JSON only.")
        return self._parse_draft(response, "issue")

    def _write_pr(self, context: str, plan: dict, diff: str, files: list) -> dict:
        files_str = ', '.join(files) if files else 'various files'
        prompt = f"""Write a GitHub Pull Request description based on:

Context: {context}
Key Points: {json.dumps(plan.get('key_points', []))}
Files: {files_str}
Risk: {plan.get('risk_assessment', 'medium')}
Test suggestions: {json.dumps(plan.get('test_suggestions', []))}
Diff snippet:
{diff}

Respond ONLY with valid JSON:
{{
  "title": "concise PR title",
  "summary": "what this PR does and why (2-3 sentences)",
  "files_affected": ["file1.py", "file2.js"],
  "behavior_change": "describe what changes in behavior",
  "test_plan": "- [ ] test 1\\n- [ ] test 2\\n- [ ] test 3",
  "risk": "low|medium|high",
  "linked_issues": []
}}"""

        response = self.llm.chat(prompt, system="You are a technical writer creating GitHub PRs. Respond with valid JSON only.")
        return self._parse_draft(response, "pr")

    def revise(self, draft_type: str, draft: dict, reflection: dict) -> dict:
        """Revise a draft based on reflection feedback."""
        fail_reason = reflection.get("fail_reason", "")
        failed_checks = [k for k, v in reflection.get("checks", {}).items() if not v["pass"]]

        prompt = f"""Revise this GitHub {draft_type} draft.

Current draft:
{json.dumps(draft, indent=2)}

Reflection failures: {fail_reason}
Failed checks: {', '.join(failed_checks)}

Fix all issues and respond ONLY with valid JSON in the same structure."""

        response = self.llm.chat(prompt, system="You are a technical writer. Respond with valid JSON only.")
        revised = self._parse_draft(response, draft_type)
        # Keep original fields if revision fails
        for k, v in draft.items():
            if k not in revised or not revised[k]:
                revised[k] = v
        return revised

    def improve(self, item_type: str, item: dict, critique: dict) -> dict:
        """Propose an improved version of an existing Issue or PR."""
        body = item.get("body", "") or ""
        findings = critique.get("findings", [])
        missing = critique.get("missing_sections", [])

        if item_type == "issue":
            prompt = f"""Improve this GitHub Issue.

Original Title: {item.get('title', '')}
Original Body:
{body[:2000]}

Critique findings: {json.dumps(findings)}
Missing sections: {json.dumps(missing)}

Write an improved version. Respond ONLY with valid JSON:
{{
  "title": "improved title",
  "problem": "clear problem description",
  "evidence": "specific evidence",
  "acceptance_criteria": "- [ ] criterion 1\\n- [ ] criterion 2",
  "risk": "low|medium|high",
  "labels": ["bug"]
}}"""
        else:
            prompt = f"""Improve this GitHub Pull Request.

Original Title: {item.get('title', '')}
Original Body:
{body[:2000]}

Critique findings: {json.dumps(findings)}
Missing sections: {json.dumps(missing)}

Write an improved version. Respond ONLY with valid JSON:
{{
  "title": "improved title",
  "summary": "clear summary",
  "files_affected": ["file1"],
  "behavior_change": "what changes",
  "test_plan": "- [ ] test 1",
  "risk": "low|medium|high",
  "linked_issues": []
}}"""

        response = self.llm.chat(prompt, system="You are a technical writer improving GitHub items. Respond with valid JSON only.")
        return self._parse_draft(response, item_type)

    def _parse_draft(self, raw: str, draft_type: str) -> dict:
        if draft_type == "issue":
            defaults = {
                "title": "Untitled Issue",
                "problem": "Problem description needed",
                "evidence": "No evidence provided",
                "acceptance_criteria": "- [ ] Define acceptance criteria",
                "risk": "medium",
                "labels": []
            }
        else:
            defaults = {
                "title": "Untitled PR",
                "summary": "Summary needed",
                "files_affected": [],
                "behavior_change": "Behavior change not described",
                "test_plan": "- [ ] Add tests",
                "risk": "medium",
                "linked_issues": []
            }
        try:
            clean = raw.strip().strip("```json").strip("```").strip()
            start = clean.find("{")
            end = clean.rfind("}") + 1
            if start >= 0 and end > start:
                parsed = json.loads(clean[start:end])
                return {**defaults, **parsed}
        except:
            pass
        return defaults
