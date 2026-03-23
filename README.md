# GitHub Repository Agent

A personalized AI agent that reviews code, drafts GitHub Issues and Pull Requests, and improves existing ones — powered by **gpt-oss:120b-cloud** via Ollama.

Built for **CS5001: AI-Assisted Software Engineering** | Spring 2026  
Repository: `mizanJewel/CS5001-Prompting-With-RAG`

---

## What It Does

| Task | Command | Description |
|------|---------|-------------|
| **Review** | `agent review` | Analyzes git diff, identifies issues, recommends action |
| **Draft** | `agent draft issue/pr` | Drafts a GitHub Issue or PR with human approval |
| **Approve** | `agent approve --yes/--no` | Creates on GitHub or aborts safely |
| **Improve** | `agent improve issue/pr` | Critiques and rewrites an existing Issue or PR |

---

## Architecture

The agent supports **two modes** selectable with `--mode`:

```
┌─────────────────────────────────────────────────────────────────┐
│                        agent.py (CLI)                           │
│                   --mode standard | mcp-a2a                     │
└───────────────┬─────────────────────────────────┬───────────────┘
                │                                 │
     ┌──────────▼──────────┐          ┌───────────▼──────────────┐
     │   STANDARD MODE     │          │     MCP + A2A MODE       │
     │  Direct Python      │          │  Agents as HTTP servers  │
     │  imports            │          │  Tools via MCP protocol  │
     └──────────┬──────────┘          └───────────┬──────────────┘
                │                                 │
     ┌──────────▼──────────┐       ┌──────────────▼─────────────┐
     │  reviewer.py        │       │  A2A Agents (HTTP)         │
     │  planner.py         │       │  Reviewer  :8201           │
     │  writer.py          │       │  Planner   :8202           │
     │  gatekeeper.py      │       │  Writer    :8203           │
     │  git_tools.py       │       │  Gatekeeper:8204           │
     │  github_tools.py    │       └──────────────┬─────────────┘
     └─────────────────────┘                      │
                                   ┌──────────────▼─────────────┐
                                   │  MCP Servers (HTTP)        │
                                   │  git-tools    :8101        │
                                   │  github-tools :8102        │
                                   └────────────────────────────┘
```

### Multi-Agent Roles

| Agent | Role | Pattern |
|-------|------|---------|
| **Reviewer** | Analyzes git diffs, critiques Issues/PRs | Tool Use |
| **Planner** | Decides action, structures draft scope | Planning |
| **Writer** | Drafts Issues, PRs, and improved versions | Tool Use |
| **Gatekeeper** | Reflects on quality, enforces human approval, creates on GitHub | Reflection + Safety |

---

## Project Structure

```
Week_5_6/
│
├── agent.py               # CLI entry point — supports --mode standard | mcp-a2a
├── reviewer.py            # Reviewer Agent (standard mode)
├── planner.py             # Planner Agent (standard mode)
├── writer.py              # Writer Agent (standard mode)
├── gatekeeper.py          # Gatekeeper Agent (standard mode)
├── git_tools.py           # Git subprocess tools (git diff, changed files, log)
├── github_tools.py        # GitHub REST API client (Issues, PRs)
├── ollama_client.py       # Ollama LLM client — gpt-oss:120b-cloud
├── state.py               # JSON state persistence between CLI commands
├── display.py             # Colored terminal output
│
├── mcp_servers/
│   ├── git_mcp.py         # MCP server: git tools over HTTP (port 8101)
│   └── github_mcp.py      # MCP server: GitHub API over HTTP (port 8102)
│
└── a2a/
    ├── protocol.py        # A2AClient, MCPClient, A2AAgentServer base classes
    ├── orchestrator.py    # Starts all servers, routes CLI commands via A2A
    ├── reviewer_agent.py  # Reviewer as A2A HTTP server (port 8201)
    ├── planner_agent.py   # Planner as A2A HTTP server (port 8202)
    ├── writer_agent.py    # Writer as A2A HTTP server (port 8203)
    └── gatekeeper_agent.py # Gatekeeper as A2A HTTP server (port 8204)
```

---

## Setup

### 1. Install Ollama

```bash
# macOS / Linux
curl -fsSL https://ollama.com/install.sh | sh
```

### 2. Start Ollama and pull the model

```bash
# Terminal 1 — keep this running
ollama serve

# Sign in (free account at ollama.com — required for cloud model)
ollama signin

# Pull gpt-oss:120b-cloud (runs on ollama.com servers, no local GPU needed)
ollama pull gpt-oss:120b-cloud
```

### 3. Fix SSL certificates on macOS (one-time)

```bash
pip install --upgrade certifi
```

Or run Python's certificate installer:
```bash
open /Applications/Python\ 3.*/Install\ Certificates.command
```

### 4. Set environment variables

```bash
# Required for real GitHub Issue/PR creation
export GITHUB_TOKEN=ghp_your_personal_access_token
export GITHUB_REPO=mizanJewel/CS5001-Prompting-With-RAG

# Optional overrides
export OLLAMA_HOST=http://localhost:11434   # default
export OLLAMA_MODEL=gpt-oss:120b-cloud     # default
```

> **Demo mode:** Without `GITHUB_TOKEN`, all commands still work fully — GitHub creation is simulated. All analysis, drafting, and reflection run normally.

### 5. Create a GitHub Personal Access Token

1. Go to **GitHub → Settings → Developer Settings → Personal Access Tokens → Tokens (classic)**
2. Click **Generate new token**
3. Select the `repo` scope
4. Copy the token and set it: `export GITHUB_TOKEN=ghp_...`

---

## How to Run

All commands are run from **inside your repo** (`CS5001-Prompting-With-RAG/`), calling `agent.py` from the parent folder.

### Standard Mode (default)

```bash
cd CS5001-Prompting-With-RAG

# Task 1 — Review changes
python3 ../agent.py review --base main
python3 ../agent.py review --range HEAD~3..HEAD

# Task 2 — Draft an Issue or PR
python3 ../agent.py draft issue --instruction "Add input validation to RAG retriever"
python3 ../agent.py draft pr    --instruction "Refactor duplicated build_prompt logic"

# Draft from a prior review (run review first, then draft without --instruction)
python3 ../agent.py draft issue

# Approve or reject
python3 ../agent.py approve --yes    # creates on GitHub
python3 ../agent.py approve --no     # aborts safely, nothing created

# Task 3 — Improve an existing Issue or PR
python3 ../agent.py improve issue --number 42
python3 ../agent.py improve pr    --number 17
```

### MCP + A2A Mode

Add `--mode mcp-a2a` before the command. All 6 background servers start automatically and shut down when the command finishes.

```bash
cd CS5001-Prompting-With-RAG

python3 ../agent.py --mode mcp-a2a review --base main
python3 ../agent.py --mode mcp-a2a draft issue --instruction "Add rate limiting"
python3 ../agent.py --mode mcp-a2a approve --yes
python3 ../agent.py --mode mcp-a2a approve --no
python3 ../agent.py --mode mcp-a2a improve issue --number 1
```

---

## Example Output

### Task 1 — Review

```
[Tool]     Fetching git diff...
[Tool]     Diff retrieved (672 chars, Changes vs base: main)
[Reviewer] Analyzing code changes...

REVIEW ANALYSIS
──────────────────────────────────────────
Category     : feature
Risk Level   : high
Issues Found : 3
  * Missing input validation in retrieve_with_filter()
  * No unit tests added for new functionality
  * TODO comments confirm known gaps

[Planner] Deciding recommended action...

PLANNER DECISION: create_issue
   Justification: High risk changes — missing validation detected in diff
```

### Task 2 — Draft Issue + Reflection

```
[Planner]    Scope validated.
[Writer]     Draft ISSUE created.
[Gatekeeper] Running reflection check...

REFLECTION REPORT
──────────────────────────────────────────
Verdict : PASS
  [PASS] has_title: Missing input validation in RAG retriever
  [PASS] has_problem: Present
  [PASS] has_evidence: Present
  [PASS] has_acceptance_criteria: Criteria present
  [PASS] has_risk: Risk: high

[Gatekeeper] Reflection verdict: PASS.

Run 'agent approve --yes' to create or '--no' to reject.
```

### Task 2 — Approve

```
[Gatekeeper] Creating ISSUE on GitHub...
[Tool]       GitHub API call successful.

ISSUE created!
   URL   : https://github.com/mizanJewel/CS5001-Prompting-With-RAG/issues/5
   Number: #5
```

### Task 3 — Improve

```
[Reviewer] Found 5 issues.

CRITIQUE OF ISSUE #42
  * Title is vague — does not describe the specific failure mode
  * No acceptance criteria defined
  * Missing evidence from code
  * No risk level specified

[Writer]     Proposed improved structured version.
[Gatekeeper] Reflection verdict: PASS.
```

---

## Required Patterns

| Pattern | Implementation |
|---------|---------------|
| **Planning** | `PlannerAgent.plan_draft()` runs a structured planning step before every draft, outputting `key_points`, `evidence`, and `test_suggestions` |
| **Tool Use** | `GitTools` calls real `git diff`, `git log` via subprocess; `GitHubTools` calls the GitHub REST API; MCP servers expose these as HTTP tools |
| **Reflection** | `GatekeeperAgent.reflect()` produces a pass/fail artifact checking every required field; failed drafts trigger one revision cycle |
| **Multi-Agent** | Four distinct agents with separate responsibilities: Reviewer, Planner, Writer, Gatekeeper |

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| `ModuleNotFoundError: No module named 'planner'` | Use `--mode mcp-a2a`, or make sure agent.py is in the same folder as planner.py |
| `SSL: CERTIFICATE_VERIFY_FAILED` | Run `pip install --upgrade certifi` |
| `Connection refused` on Ollama | Run `ollama serve` in a separate terminal |
| `401 / auth error` on gpt-oss | Run `ollama signin` |
| `gpt-oss model not found` | Run `ollama pull gpt-oss:120b-cloud` after signing in |
| `GitHub 401` | Check `GITHUB_TOKEN` is valid and has `repo` scope |
| `GitHub 422` on PR creation | Make sure your current branch differs from `main` |
| No diff detected | Make sure you have staged changes or commits ahead of base |

### Change the model

```bash
export OLLAMA_MODEL=gpt-oss:20b-cloud    # faster, smaller
export OLLAMA_MODEL=llama3.2             # local, no sign-in needed
```

---

## How MCP + A2A Works

**MCP (Model Context Protocol)** — Instead of calling `subprocess` or `urllib` directly inside agent code, tools are exposed as HTTP endpoints. Any agent calls `MCPClient.call("git_diff", {...})` and gets the result back as text. This decouples tool implementations from agent logic.

```
Agent → POST /mcp/call {"name": "git_diff", "arguments": {"base": "main"}}
      ← {"content": [{"type": "text", "text": "diff --git a/..."}]}
```

**A2A (Agent-to-Agent)** — Each agent runs as its own HTTP server. The Orchestrator sends structured task messages instead of calling Python functions directly. Agents are fully decoupled — Reviewer has no Python import of Planner.

```
Orchestrator → POST /a2a/task {"action": "analyze_diff", "input": {...}}
Reviewer     ← {"status": "completed", "output": {...}, "artifacts": [...]}
```

---

*GitHub Repository Agent · CS5001 Spring 2026 · Mizanur Rahman*