"""
Git Tools - Real git operations using subprocess
Pattern: Tool Use
"""

import subprocess
import os


class GitTools:
    def get_diff_base(self, base: str = "main") -> str:
        """Get diff between current branch and base branch."""
        try:
            # Try merge-base diff first (cleanest)
            result = subprocess.run(
                ["git", "diff", f"{base}...HEAD"],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout

            # Fallback: staged + unstaged
            staged = subprocess.run(
                ["git", "diff", "--cached"],
                capture_output=True, text=True, timeout=30
            )
            unstaged = subprocess.run(
                ["git", "diff"],
                capture_output=True, text=True, timeout=30
            )
            return (staged.stdout or "") + (unstaged.stdout or "")
        except Exception as e:
            return f"[git diff error: {e}]"

    def get_diff_range(self, commit_range: str) -> str:
        """Get diff for a commit range like HEAD~3..HEAD."""
        try:
            result = subprocess.run(
                ["git", "diff", commit_range],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                return result.stdout
            return f"[git diff range error: {result.stderr}]"
        except Exception as e:
            return f"[git diff range error: {e}]"

    def get_changed_files(self, base: str = "main", commit_range: str = None) -> list:
        """Get list of changed files."""
        try:
            if commit_range:
                result = subprocess.run(
                    ["git", "diff", "--name-only", commit_range],
                    capture_output=True, text=True, timeout=30
                )
            else:
                result = subprocess.run(
                    ["git", "diff", "--name-only", f"{base}...HEAD"],
                    capture_output=True, text=True, timeout=30
                )
            if result.returncode == 0:
                files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
                if not files:
                    # Try staged files
                    r2 = subprocess.run(
                        ["git", "diff", "--name-only", "--cached"],
                        capture_output=True, text=True, timeout=30
                    )
                    files = [f.strip() for f in r2.stdout.strip().split("\n") if f.strip()]
                return files
        except Exception:
            pass
        return []

    def get_current_branch(self) -> str:
        """Get current branch name."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True, text=True, timeout=10
            )
            return result.stdout.strip() if result.returncode == 0 else "unknown"
        except:
            return "unknown"

    def read_file(self, filepath: str) -> str:
        """Read a file from the repo."""
        try:
            with open(filepath, "r") as f:
                return f.read()
        except Exception as e:
            return f"[could not read {filepath}: {e}]"

    def get_commit_log(self, n: int = 5) -> str:
        """Get recent commit log."""
        try:
            result = subprocess.run(
                ["git", "log", f"-{n}", "--oneline"],
                capture_output=True, text=True, timeout=10
            )
            return result.stdout if result.returncode == 0 else ""
        except:
            return ""
