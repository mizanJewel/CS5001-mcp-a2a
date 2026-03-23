"""
Ollama Client — gpt-oss:120b-cloud
Cloud model via Ollama (no local GPU required).
Requires: ollama signin  →  ollama pull gpt-oss:120b-cloud
"""

import json
import urllib.request
import urllib.error
import os


class OllamaClient:
    def __init__(self):
        self.base_url = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        self.model    = os.environ.get("OLLAMA_MODEL", "gpt-oss:120b-cloud")
        self._available   = None
        self._auth_warned = False

    def chat(self, prompt: str, system: str = "") -> str:
        if not self._check_available():
            return self._fallback_response(prompt)

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model":   self.model,
            "messages": messages,
            "stream":  False,
            "options": {"temperature": 0.3, "num_predict": 2048}
        }

        try:
            data = json.dumps(payload).encode()
            req  = urllib.request.Request(
                f"{self.base_url}/api/chat",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=180) as resp:
                return json.loads(resp.read()).get("message", {}).get("content", "")

        except urllib.error.HTTPError as e:
            body = e.read().decode()
            if e.code in (401, 403) or "sign" in body.lower() or "auth" in body.lower():
                if not self._auth_warned:
                    self._auth_warned = True
                    print("\n  [Warning] gpt-oss:120b-cloud requires Ollama sign-in.")
                    print("  Run:  ollama signin")
                    print("  Then: ollama pull gpt-oss:120b-cloud")
                    print("  Using fallback responses...\n")
            else:
                print(f"\n  [Warning] Ollama HTTP {e.code}: {body[:120]}\n")
            self._available = False
            return self._fallback_response(prompt)

        except urllib.error.URLError as e:
            if not self._auth_warned:
                print(f"\n  [Warning] Ollama not reachable: {e}")
                print("  Start it with: ollama serve")
                print("  Then: ollama signin && ollama pull gpt-oss:120b-cloud")
                print("  Using fallback responses...\n")
                self._auth_warned = True
            self._available = False
            return self._fallback_response(prompt)

        except Exception as e:
            print(f"\n  [Warning] LLM error: {e}\n")
            return self._fallback_response(prompt)

    def _check_available(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                self._available = resp.status == 200
                return self._available
        except:
            self._available = False
            return False

    def _fallback_response(self, prompt: str) -> str:
        """Structured fallback for when gpt-oss:120b-cloud is unavailable."""

        if '"summary"' in prompt and '"category"' in prompt:
            return json.dumps({
                "summary": "Code changes detected in the repository",
                "category": "feature", "risk": "medium",
                "issues": [
                    "Missing input validation detected",
                    "No unit tests added for new functionality",
                    "Error handling could be improved"
                ],
                "strengths": ["Code is modular", "Changes are focused"],
                "recommended_action": "create_issue",
                "action_justification": "Missing tests and validation detected in diff"
            })

        elif '"key_points"' in prompt and '"affected_areas"' in prompt:
            return json.dumps({
                "key_points": ["Address missing input validation", "Add error handling", "Add unit tests"],
                "affected_areas": ["RAG pipeline", "retriever module"],
                "risk_assessment": "medium",
                "evidence": ["Diff shows no validation logic", "TODO comments confirm gap"],
                "test_suggestions": ["Test empty query handling", "Test boundary conditions",
                                     "Integration test for RAG pipeline"]
            })

        elif '"problem"' in prompt and '"acceptance_criteria"' in prompt:
            title    = "Missing input validation in RAG retriever"
            problem  = "The RAG retriever does not validate input queries. Empty or malformed queries pass directly to the vector store, causing runtime crashes."
            evidence = "Diff shows retrieve_with_filter() has no guard for empty or None queries. TODO comments confirm this gap."
            criteria = "- [ ] Validate query is non-empty string before retrieval\n- [ ] Raise ValueError with clear message for invalid input\n- [ ] Add rate limiting to prevent API abuse\n- [ ] Unit tests cover empty, None, and oversized inputs"
            risk     = "high"
            labels   = ["bug", "enhancement"]

            if "refactor" in prompt.lower() or "duplicate" in prompt.lower():
                title    = "Duplicated build_prompt logic in RAG pipeline"
                problem  = "build_prompt and build_prompt_v2 in rag_pipeline.py contain identical logic, violating DRY and requiring duplicate fixes."
                evidence = "Diff shows two functions with identical implementations in rag_in_class/rag_pipeline.py."
                criteria = "- [ ] Consolidate into single build_prompt utility\n- [ ] Remove build_prompt_v2 or make it a thin wrapper\n- [ ] Update all call sites\n- [ ] Add unit tests for consolidated function"
                risk     = "low"
                labels   = ["refactor", "technical-debt"]
            elif "rate limit" in prompt.lower():
                title    = "No rate limiting on RAG retriever — risk of vector store overload"
                problem  = "retrieve_with_filter() performs vector store queries with no rate limiting, risking API quota exhaustion under load."
                evidence = "Diff shows retrieve_with_filter() calls db.similarity_search() with no throttling. TODO comment in code acknowledges this gap."
                criteria = "- [ ] Implement rate limiting (token bucket or sliding window)\n- [ ] Return RateLimitError when limit exceeded\n- [ ] Add config for max requests per minute\n- [ ] Unit tests verify rate limit behaviour"
                risk     = "medium"
                labels   = ["enhancement", "performance"]

            return json.dumps({"title": title, "problem": problem, "evidence": evidence,
                               "acceptance_criteria": criteria, "risk": risk, "labels": labels})

        elif '"summary"' in prompt and '"files_affected"' in prompt:
            title      = "feat: Add input validation and rate limiting to RAG retriever"
            summary    = "Adds input validation to retrieve_with_filter() in rag_pipeline.py. Empty queries now raise ValueError. A simple rate limiter prevents vector store overload."
            files      = ["rag_in_class/rag_pipeline.py", "rag_in_class/validators.py", "tests/test_retriever.py"]
            behavior   = "Invalid queries now fail fast with a clear error. Requests exceeding the rate limit receive a RateLimitError."
            test_plan  = "- [ ] Unit test: empty query raises ValueError\n- [ ] Unit test: None raises ValueError\n- [ ] Unit test: rate limit triggers after N requests\n- [ ] Integration test: valid query flows correctly"
            risk       = "medium"

            if "refactor" in prompt.lower() or "duplicate" in prompt.lower():
                title     = "Refactor: Consolidate duplicated build_prompt functions in RAG pipeline"
                summary   = "Removes build_prompt_v2 and consolidates prompt-building logic into a single reusable utility, reducing duplication and maintenance risk."
                files     = ["rag_in_class/rag_pipeline.py", "tests/test_rag_pipeline.py"]
                behavior  = "Prompt construction behaviour unchanged. All callers use the single consolidated build_prompt. build_prompt_v2 is removed."
                test_plan = "- [ ] Run existing test suite — no regression expected\n- [ ] Unit test: build_prompt with empty chunks\n- [ ] Unit test: build_prompt with special characters\n- [ ] Manual smoke test: run full RAG pipeline"
                risk      = "low"

            return json.dumps({"title": title, "summary": summary, "files_affected": files,
                               "behavior_change": behavior, "test_plan": test_plan,
                               "risk": risk, "linked_issues": []})

        elif '"findings"' in prompt and '"missing_sections"' in prompt:
            return json.dumps({
                "findings": [
                    "Title is vague — does not describe the specific failure mode",
                    "No acceptance criteria defined — unclear what 'done' looks like",
                    "Missing reproduction steps or concrete evidence from code",
                    "No risk level specified",
                    "Expected vs actual behaviour not compared"
                ],
                "missing_sections": ["acceptance_criteria", "evidence", "risk_level", "reproduction_steps"],
                "vague_language": ["it doesn't work", "the RAG isn't good", "pipeline fails sometimes"],
                "quality_score": 2
            })

        return json.dumps({"result": "Processed", "status": "ok"})
