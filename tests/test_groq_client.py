"""Unit tests for GroqAgentClient with mocked API responses."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from agent.groq_client import GroqAgentClient, GroqBudgetExceededError
from app.config import Settings


@pytest.mark.asyncio
async def test_groq_budget_exceeded():
    """Verify GroqBudgetExceededError is raised when token budget is exhausted."""
    settings = Settings(
        APP_ENV="testing",
        GROQ_API_KEY="gsk_test123",
        GROQ_MAX_TOKENS_PER_JOB=1000,
    )
    client = GroqAgentClient(settings)

    with pytest.raises(GroqBudgetExceededError):
        await client.complete_with_budget(
            messages=[{"role": "user", "content": "hello"}],
            tokens_used_so_far=1001,
        )


@pytest.mark.asyncio
async def test_groq_explanation_and_viva_generation():
    """Verify GroqAgentClient formats explanation and viva questions correctly."""
    settings = Settings(
        APP_ENV="testing",
        GROQ_API_KEY="gsk_test123",
    )
    client = GroqAgentClient(settings)

    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content=(
                    "Here is the detailed solution explanation.\n\n"
                    "VIVA QUESTIONS:\n"
                    "1. What is the time complexity of your sorting routine?\n"
                    "2. How does the recursion stack handle edge cases?\n"
                )
            )
        )
    ]
    mock_response.usage = MagicMock(total_tokens=150)

    client.client.chat.completions.create = AsyncMock(return_value=mock_response)

    text, viva, used = await client.generate_explanation_and_viva(
        lab_title="Lab 3 Sorting",
        solution_code="def bubble_sort(arr): ...",
    )

    assert "Here is the detailed solution explanation" in text
    assert len(viva) == 2
    assert "time complexity" in viva[0]
    assert used == 150
