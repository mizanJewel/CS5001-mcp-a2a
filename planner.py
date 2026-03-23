"""
Planner Agent - Decides action and plans draft structure
Pattern: Planning
"""

import json
from ollama_client import OllamaClient


class PlannerAgent:
    def __init__(self):
        self.llm = OllamaClient()
        self.role = "Planner"

    def decide(self, review_result: dict) -> dict:
        """Decide what action to take based on review."""
        issues = review_result.get("issues", [])
        risk = review_result.get("risk", "medium")
        action = review_result.get("recommended_action", "no_action")
        justification = review_result.get("action_justification", "")

        # Override logic based on risk
        if risk == "high" and action == "no_action":
            action = "create_issue"
            justification = f"High risk changes detected: {'; '.join(issues[:2])}"
        elif not issues and action != "create_pr":
            action = "no_action"
            justification = "No significant issues found in the diff"

        return {
            "action": action,
            "justification": justification,
            "risk": risk,
            "issue_count": len(issues)
        }

    def plan_draft(self, draft_type: str, context: dict) -> dict:
        """Plan the structure and key points of a draft."""
        source = context.get("source", "explicit")

        if source == "explicit":
            instruction = context.get("instruction", "")
            diff_snippet = context.get("diff", "")[:2000]
            changed = context.get("changed_files", [])

            prompt = f"""You are planning a GitHub {draft_type}.

Instruction: {instruction}
Changed Files: {', '.join(changed) if changed else 'not specified'}
Diff snippet:
{diff_snippet}

Plan the key points for a {draft_type}. Respond ONLY with valid JSON:
{{
  "key_points": ["point 1", "point 2"],
  "affected_areas": ["area 1"],
  "risk_assessment": "low|medium|high",
  "evidence": ["evidence from diff or context"],
  "test_suggestions": ["test 1", "test 2"]
}}"""
        else:
            review = context.get("review", {})
            prompt = f"""You are planning a GitHub {draft_type} based on a code review.

Review Summary: {review.get('summary', '')}
Issues: {json.dumps(review.get('issues', []))}
Risk: {review.get('risk', 'medium')}
Category: {review.get('category', 'feature')}

Plan the {draft_type}. Respond ONLY with valid JSON:
{{
  "key_points": ["point 1", "point 2"],
  "affected_areas": ["area 1"],
  "risk_assessment": "low|medium|high",
  "evidence": ["evidence 1"],
  "test_suggestions": ["test 1"]
}}"""

        response = self.llm.chat(prompt, system="You are a technical planner. Respond with valid JSON only.")
        return self._parse_plan(response)

    def _parse_plan(self, raw: str) -> dict:
        defaults = {
            "key_points": ["Implementation needed"],
            "affected_areas": ["codebase"],
            "risk_assessment": "medium",
            "evidence": [],
            "test_suggestions": ["Add unit tests", "Add integration tests"]
        }
        try:
            clean = raw.strip().strip("```json").strip("```").strip()
            start = clean.find("{")
            end = clean.rfind("}") + 1
            if start >= 0 and end > start:
                return {**defaults, **json.loads(clean[start:end])}
        except:
            pass
        return defaults
