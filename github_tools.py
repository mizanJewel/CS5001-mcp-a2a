"""
GitHub Tools — Real GitHub API operations
Pre-configured for: mizanJewel/CS5001-Prompting-With-RAG
"""

import os, json, random, subprocess, ssl
import urllib.request, urllib.error


def _ssl_context():
    """SSL context that works on macOS without running 'Install Certificates.command'."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        pass
    try:
        import subprocess as sp
        r = sp.run(["python3", "-c",
            "import ssl; print(ssl.get_default_verify_paths().cafile or ssl.get_default_verify_paths().capath)"],
            capture_output=True, text=True)
        cafile = r.stdout.strip()
        if cafile and os.path.exists(cafile):
            return ssl.create_default_context(cafile=cafile)
    except Exception:
        pass
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


class GitHubTools:
    def __init__(self):
        self.token       = os.environ.get("GITHUB_TOKEN", "")
        self.repo        = os.environ.get("GITHUB_REPO", "mizanJewel/CS5001-Prompting-With-RAG")
        self.base_url    = "https://api.github.com"
        self.base_branch = os.environ.get("GITHUB_BASE_BRANCH", "main")
        self._ssl        = _ssl_context()

    def _headers(self):
        h = {"Accept": "application/vnd.github+json", "Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def _request(self, method, path, data=None):
        url  = f"{self.base_url}{path}"
        body = json.dumps(data).encode() if data else None
        req  = urllib.request.Request(url, data=body, headers=self._headers(), method=method)
        try:
            with urllib.request.urlopen(req, timeout=15, context=self._ssl) as resp:
                return {"ok": True, "data": json.loads(resp.read())}
        except urllib.error.HTTPError as e:
            return {"ok": False, "error": f"HTTP {e.code}: {e.read().decode()[:200]}"}
        except Exception as ex:
            return {"ok": False, "error": str(ex)}

    def get_item(self, item_type, number):
        if not self._is_configured():
            return self._demo_item(item_type, number)
        result = self._request("GET", f"/repos/{self.repo}/issues/{number}")
        if result["ok"]:
            d = result["data"]
            return {"number": d.get("number"), "title": d.get("title", ""),
                    "body": d.get("body", "") or "", "state": d.get("state", "open"),
                    "labels": [l["name"] for l in d.get("labels", [])], "url": d.get("html_url", "")}
        print(f"  [Warning] GitHub fetch failed: {result['error']}")
        return self._demo_item(item_type, number)

    def create_issue(self, title, body, labels=None):
        if not self._is_configured():
            return self._demo_create("issue", title)
        payload = {"title": title, "body": body}
        if labels:
            payload["labels"] = labels
        result = self._request("POST", f"/repos/{self.repo}/issues", payload)
        if result["ok"]:
            return {"success": True, "number": result["data"]["number"], "url": result["data"]["html_url"]}
        return {"success": False, "error": result["error"]}

    def create_pr(self, title, body, head=None, base=None):
        if not self._is_configured():
            return self._demo_create("pr", title)
        if not head:
            try:
                r    = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True)
                head = r.stdout.strip() if r.returncode == 0 else "feature-branch"
            except:
                head = "feature-branch"
        result = self._request("POST", f"/repos/{self.repo}/pulls",
                               {"title": title, "body": body, "head": head, "base": base or self.base_branch})
        if result["ok"]:
            return {"success": True, "number": result["data"]["number"], "url": result["data"]["html_url"]}
        return {"success": False, "error": result["error"]}

    def _is_configured(self):
        return bool(self.token and self.repo and "/" in self.repo)

    def _demo_item(self, item_type, number):
        if item_type == "issue":
            return {"number": number, "title": "RAG pipeline returns irrelevant chunks for complex queries",
                    "body": "When querying with multi-part questions retriever returns unrelated chunks.",
                    "state": "open", "labels": ["bug"],
                    "url": f"https://github.com/mizanJewel/CS5001-Prompting-With-RAG/issues/{number}"}
        return {"number": number, "title": "Add chunking strategy and reranking to RAG pipeline",
                "body": "This PR improves retrieval quality.", "state": "open", "labels": [],
                "url": f"https://github.com/mizanJewel/CS5001-Prompting-With-RAG/pull/{number}"}

    def _demo_create(self, item_type, title):
        num = random.randint(1, 20)
        url = f"https://github.com/mizanJewel/CS5001-Prompting-With-RAG/{'issues' if item_type == 'issue' else 'pull'}/{num}"
        print("\n  [DEMO MODE] GITHUB_TOKEN not set — simulating creation.")
        print("  Set it with: export GITHUB_TOKEN=ghp_yourtoken")
        return {"success": True, "number": num, "url": url}
