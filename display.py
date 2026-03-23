"""
Display - Colored terminal output for agent steps
"""


class Display:
    COLORS = {
        "Reviewer":   "\033[94m",   # blue
        "Planner":    "\033[95m",   # magenta
        "Writer":     "\033[92m",   # green
        "Gatekeeper": "\033[93m",   # yellow
        "Tool":       "\033[96m",   # cyan
        "Error":      "\033[91m",   # red
        "Reset":      "\033[0m",
        "Bold":       "\033[1m",
    }

    def step(self, agent: str, message: str):
        color = self.COLORS.get(agent, "")
        reset = self.COLORS["Reset"]
        bold = self.COLORS["Bold"]
        print(f"{bold}{color}[{agent}]{reset} {message}")

    def result(self, agent: str, message: str):
        color = self.COLORS.get(agent, "")
        reset = self.COLORS["Reset"]
        bold = self.COLORS["Bold"]
        print(f"{bold}{color}[{agent}]{reset} {message}")

    def header(self, title: str):
        bold = self.COLORS["Bold"]
        reset = self.COLORS["Reset"]
        print(f"\n{bold}{'='*60}{reset}")
        print(f"{bold}🤖 {title}{reset}")
        print(f"{bold}{'='*60}{reset}\n")

    def error(self, message: str):
        red = self.COLORS["Error"]
        reset = self.COLORS["Reset"]
        print(f"{red}[Error] {message}{reset}")

    def info(self, message: str):
        cyan = self.COLORS["Tool"]
        reset = self.COLORS["Reset"]
        print(f"{cyan}[Info] {message}{reset}")
