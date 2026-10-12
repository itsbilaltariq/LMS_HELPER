"""Agent solve loop with strict tool allowlist, TDD iteration, and rubric self-critique."""

import json
from pathlib import Path
from typing import Any, Callable

from agent.groq_client import GroqAgentClient
from agent.parser import ParsedLab
from app.logging import setup_logging

logger = setup_logging()


class ToolSecurityError(Exception):
    """Raised when an agent attempts unauthorized file or execution operations."""

    pass


class AgentWorkspace:
    """Restricted file access environment for a specific lab job."""

    def __init__(self, workspace_dir: str | Path) -> None:
        self.workspace_dir = Path(workspace_dir).resolve()
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_safe(self, rel_path: str) -> Path:
        """Resolve path and prevent directory traversal outside workspace."""
        clean = Path(rel_path)
        if clean.is_absolute():
            # If absolute, verify it is still inside workspace
            resolved = clean.resolve()
        else:
            resolved = (self.workspace_dir / clean).resolve()

        if not str(resolved).startswith(str(self.workspace_dir)):
            raise ToolSecurityError(f"Access denied: path '{rel_path}' escapes workspace boundary")
        return resolved

    def write_file(self, rel_path: str, content: str) -> str:
        """Allowlisted tool: write code or data file."""
        target = self._resolve_safe(rel_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Successfully wrote {len(content)} bytes to {rel_path}"

    def read_file(self, rel_path: str) -> str:
        """Allowlisted tool: read file within workspace."""
        target = self._resolve_safe(rel_path)
        if not target.exists():
            return f"Error: File '{rel_path}' does not exist"
        return target.read_text(encoding="utf-8")


class LabAgentSolver:
    """Autonomous TDD solve loop powered by Groq."""

    def __init__(
        self,
        workspace: AgentWorkspace,
        groq_client: GroqAgentClient | None = None,
        max_iterations: int = 5,
    ) -> None:
        self.workspace = workspace
        self.groq_client = groq_client or GroqAgentClient()
        self.max_iterations = max_iterations
        self.trajectory: list[dict[str, Any]] = []

    def _record(self, step_type: str, data: dict[str, Any]) -> None:
        """Append step to trajectory log."""
        self.trajectory.append({"step": step_type, "data": data})

    async def create_plan(self, parsed_lab: ParsedLab) -> list[str]:
        """Map each task and rubric item into an implementation plan."""
        system_prompt = (
            "You are a computer science planning agent. Break down the lab tasks into a "
            "numbered list of sequential steps with test checkpoints."
        )
        user_prompt = (
            f"Lab: {parsed_lab.lab_title}\n"
            f"Tasks: {[t.model_dump() for t in parsed_lab.tasks]}\n"
            f"Rubric: {[r.model_dump() for r in parsed_lab.rubric]}\n"
            f"Constraints: {parsed_lab.constraints}\n\n"
            "Produce a numbered step-by-step implementation plan."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        plan_text, used = await self.groq_client.complete_with_budget(messages, 0)
        self._record("plan_created", {"plan": plan_text, "tokens": used})
        return [
            line.strip()
            for line in plan_text.split("\n")
            if line.strip() and line.strip()[0].isdigit()
        ]

    async def solve_task(
        self,
        task_description: str,
        target_file: str,
        test_runner: Callable[[], tuple[bool, str]],
    ) -> tuple[bool, str]:
        """
        Solve loop: generate code -> write_file -> test_runner -> iterate on error.
        Returns: (success: bool, final_code: str)
        """
        iteration = 0
        error_feedback = ""
        current_code = ""

        while iteration < self.max_iterations:
            iteration += 1
            logger.info(f"Solve iteration {iteration}/{self.max_iterations} for {target_file}")

            system_prompt = (
                "You are an expert programmer solving a NUST lab task. "
                "Output ONLY the complete source code, without markdown fences or commentary."
            )
            user_prompt = f"Task: {task_description}\nTarget file: {target_file}\n"
            if error_feedback:
                user_prompt += (
                    f"\nPrevious Attempt Code:\n```\n{current_code}\n```\n"
                    f"\nTest Execution Failure Output:\n{error_feedback}\n"
                    "Analyze the error, correct the logic, and produce the revised code."
                )

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            raw_code, tokens = await self.groq_client.complete_with_budget(messages, 0)
            # Clean markdown if present
            cleaned_code = raw_code.strip()
            if cleaned_code.startswith("```"):
                cleaned_code = "\n".join(
                    [
                        line
                        for line in cleaned_code.split("\n")
                        if not line.strip().startswith("```")
                    ]
                )

            current_code = cleaned_code
            self.workspace.write_file(target_file, current_code)

            # Run test callback
            passed, output = test_runner()
            self._record(
                "iteration",
                {
                    "iteration": iteration,
                    "file": target_file,
                    "passed": passed,
                    "output": output,
                    "tokens": tokens,
                },
            )

            if passed:
                logger.info(f"Task solved successfully on iteration {iteration}!")
                return True, current_code

            error_feedback = output

        logger.warning(f"Exceeded max iterations ({self.max_iterations}) for {target_file}")
        return False, current_code

    async def self_critique(self, code: str, parsed_lab: ParsedLab) -> tuple[bool, str]:
        """Critique solution against lab rubric and constraints."""
        system_prompt = (
            "You are a strict code grader. Review the solution against rubric and constraints. "
            "Reply with 'PASS' if all constraints are met, followed by brief feedback."
        )
        user_prompt = (
            f"Code:\n```\n{code}\n```\n\n"
            f"Rubric: {[r.model_dump() for r in parsed_lab.rubric]}\n"
            f"Constraints: {parsed_lab.constraints}"
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        critique, _ = await self.groq_client.complete_with_budget(messages, 0)
        passed = "PASS" in critique.upper()
        self._record("self_critique", {"passed": passed, "critique": critique})
        return passed, critique

    def save_trajectory(self, output_path: str | Path) -> None:
        """Persist debugging trajectory log without secrets."""
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(self.trajectory, f, indent=2)
