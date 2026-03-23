"""
Reviewer Agent — Analyzes code changes and existing Issues/PRs
Patterns: Tool Use + Reflection
"""

import json
from ollama_client import OllamaClient


class ReviewerAgent:
    def __init__(self):
        self.llm  = OllamaClient()
        self.role = "Reviewer"

    def analyze(self, diff: str, changed_files: list, context: str) -> dict:
        """Analyze a git diff and return structured review."""
        prompt = f"""You are a senior software engineer reviewing code changes.

Context: {context}
Changed Files: {', '.join(changed_files) if changed_files else 'unknown'}

Git Diff:
{diff[:6000]}

Analyze this diff and respond ONLY with valid JSON (no markdown, no explanation):
{{
  "summary": "one sentence summary of changes",
  "category": "feature|bugfix|refactor|docs|test|chore",
  "risk": "low|medium|high",
  "issues": ["issue 1", "issue 2"],
  "strengths": ["strength 1"],
  "recommended_action": "create_issue|create_pr|no_action",
  "action_justification": "why this action is recommended based on evidence from the diff"
}}"""

        response = self.llm.chat(prompt, system="You are a code reviewer. Always respond with valid JSON only.")
        return self._parse_review(response)

    def critique(self, item_type: str, item: dict) -> dict:
        """Critique an existing Issue or PR for missing/unclear content."""
        body = item.get("body", "") or ""

        if item_type == "issue":
            criteria = """
- Clear problem description
- Evidence or reproduction steps
- Acceptance criteria
- Risk level mentioned
- Labels/assignees assigned
- Clear title (not vague)"""
        else:
            criteria = """
- Summary of changes
- Files affected listed
- Behavior change described
- Test plan provided
- Risk level mentioned
- Linked issues
- Clear title"""

        prompt = f"""You are critiquing a GitHub {item_type}.

Title: {item.get('title', '')}
Body:
{body[:3000]}

Check for these quality criteria:{criteria}

Respond ONLY with valid JSON:
{{
  "findings": ["finding 1", "finding 2"],
  "missing_sections": ["section1", "section2"],
  "vague_language": ["example of vague text"],
  "quality_score": 3
}}"""

        response = self.llm.chat(prompt, system="You are a code review expert. Respond with valid JSON only.")
        return self._parse_critique(response)

    def _parse_review(self, raw: str) -> dict:
        defaults = {
            "summary": "Code changes detected", "category": "feature",
            "risk": "medium", "issues": [], "strengths": [],
            "recommended_action": "no_action",
            "action_justification": "Unable to parse review"
        }
        try:
            clean = raw.strip().strip("```json").strip("```").strip()
            s, e  = clean.find("{"), clean.rfind("}") + 1
            if s >= 0 and e > s:
                return {**defaults, **json.loads(clean[s:e])}
        except:
            pass
        return defaults

    def _parse_critique(self, raw: str) -> dict:
        defaults = {
            "findings": ["Could not parse critique"],
            "missing_sections": [], "vague_language": [], "quality_score": 3
        }
        try:
            clean = raw.strip().strip("```json").strip("```").strip()
            s, e  = clean.find("{"), clean.rfind("}") + 1
            if s >= 0 and e > s:
                return {**defaults, **json.loads(clean[s:e])}
        except:
            pass
        return defaults
