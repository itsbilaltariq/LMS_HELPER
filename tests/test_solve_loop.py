"""Unit tests for Phase 6 Agent solve loop, sandbox workspace, and TDD iterations."""

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from agent.groq_client import GroqAgentClient
from agent.parser import LabTask, ParsedLab, RubricItem
from agent.solve_loop import AgentWorkspace, LabAgentSolver, ToolSecurityError
from app.config import Settings


def test_agent_workspace_boundary_protection(tmp_path: Path):
    """Verify AgentWorkspace blocks directory traversal attacks."""
    ws = AgentWorkspace(tmp_path)

    # Allowed local write
    msg = ws.write_file("main.py", "print('hello')")
    assert "Successfully wrote" in msg
    assert (tmp_path / "main.py").exists()

    # Blocked traversal write
    with pytest.raises(ToolSecurityError):
        ws.write_file("../malicious.sh", "rm -rf /")

    # Blocked traversal read
    with pytest.raises(ToolSecurityError):
        ws.read_file("../../etc/passwd")


@pytest.mark.asyncio
async def test_agent_solve_loop_tdd_iteration(tmp_path: Path):
    """Verify solve loop receives error feedback and iterates to success."""
    ws = AgentWorkspace(tmp_path)
    settings = Settings(APP_ENV="testing", GROQ_API_KEY="gsk_test")
    groq_client = GroqAgentClient(settings)

    # Responses: 1st iteration generates buggy code, 2nd iteration fixes it
    attempt_count = 0

    async def mock_complete(*args, **kwargs):
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count == 1:
            return "def add(a, b): return a - b", 50
        else:
            return "def add(a, b): return a + b", 50

    groq_client.complete_with_budget = AsyncMock(side_effect=mock_complete)

    solver = LabAgentSolver(workspace=ws, groq_client=groq_client, max_iterations=3)

    # Simulated test runner
    def test_runner():
        code = ws.read_file("solution.py")
        if "a + b" in code:
            return True, "All tests passed"
        return False, "AssertionError: add(1, 2) expected 3, got -1"

    success, final_code = await solver.solve_task(
        task_description="Implement addition function",
        target_file="solution.py",
        test_runner=test_runner,
    )

    assert success is True
    assert "return a + b" in final_code
    assert attempt_count == 2
    assert len(solver.trajectory) == 2

    # Verify trajectory saved
    traj_path = tmp_path / "trajectory.json"
    solver.save_trajectory(traj_path)
    assert traj_path.exists()
    traj_data = json.loads(traj_path.read_text(encoding="utf-8"))
    assert len(traj_data) == 2


@pytest.mark.asyncio
async def test_agent_self_critique(tmp_path: Path):
    """Verify self-critique evaluates against rubric criteria."""
    ws = AgentWorkspace(tmp_path)
    groq_client = GroqAgentClient(Settings(APP_ENV="testing"))
    groq_client.complete_with_budget = AsyncMock(
        return_value=("PASS: All functions adhere to O(1) space complexity.", 60)
    )

    solver = LabAgentSolver(workspace=ws, groq_client=groq_client)
    parsed_lab = ParsedLab(
        lab_title="Lab 1 Math",
        tasks=[LabTask(task_id="T1", title="Add", description="Sum")],
        rubric=[RubricItem(criterion="Efficiency", description="O(1) space")],
        constraints=["No imports"],
    )

    passed, feedback = await solver.self_critique("def add(a, b): return a + b", parsed_lab)
    assert passed is True
    assert "O(1) space" in feedback
