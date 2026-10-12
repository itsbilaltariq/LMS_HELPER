"""Groq Cloud LLM client with timeout, retry backoff, and per-job token budgets."""

import asyncio

from groq import APIError, AsyncGroq, RateLimitError

from app.config import Settings, get_settings
from app.logging import setup_logging

logger = setup_logging()


class GroqBudgetExceededError(Exception):
    """Raised when a job exceeds its allocated token limit."""

    pass


class GroqAgentClient:
    """Async Groq client configured for fast code generation, hints, and explanations."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.client = AsyncGroq(api_key=self.settings.GROQ_API_KEY or "dummy_key")
        self.model = self.settings.GROQ_MODEL
        self.parser_model = self.settings.GROQ_PARSER_MODEL
        self.max_tokens = self.settings.GROQ_MAX_TOKENS_PER_JOB

    async def complete_with_budget(
        self,
        messages: list[dict[str, str]],
        tokens_used_so_far: int,
        model: str | None = None,
        temperature: float = 0.2,
        max_retries: int = 3,
    ) -> tuple[str, int]:
        """
        Execute chat completion on Groq with retry logic and token budgeting.
        Returns: (response_text, new_tokens_used)
        """
        if tokens_used_so_far >= self.max_tokens:
            raise GroqBudgetExceededError(
                f"Token budget of {self.max_tokens} exceeded (consumed: {tokens_used_so_far})"
            )

        chosen_model = model or self.model
        attempt = 0
        backoff = 1.0

        while attempt < max_retries:
            try:
                response = await self.client.chat.completions.create(
                    model=chosen_model,
                    messages=messages,  # type: ignore
                    temperature=temperature,
                )
                content = response.choices[0].message.content or ""
                used = response.usage.total_tokens if response.usage else 0
                return content, used

            except RateLimitError as e:
                attempt += 1
                if attempt >= max_retries:
                    logger.error(f"Groq RateLimitError after {max_retries} attempts: {e}")
                    raise
                logger.warning(f"Groq Rate limit hit. Backing off {backoff}s...")
                await asyncio.sleep(backoff)
                backoff *= 2.0

            except APIError as e:
                attempt += 1
                if attempt >= max_retries:
                    logger.error(f"Groq APIError: {e}")
                    raise
                await asyncio.sleep(backoff)
                backoff *= 1.5

        raise RuntimeError("Failed to complete Groq API call after retries")

    async def generate_explanation_and_viva(
        self,
        lab_title: str,
        solution_code: str,
        tokens_used: int = 0,
    ) -> tuple[str, list[str], int]:
        """
        Generate pedagogical walkthrough and viva exam questions for NUST lab defense.
        """
        system_prompt = (
            "You are a computer science lab tutor at NUST (SEECS). "
            "Explain the student's solution thoroughly and generate 5 likely viva / oral "
            "examination questions with concise answers to prepare the student."
        )
        user_prompt = (
            f"Lab Title: {lab_title}\n\n"
            f"Solution Code:\n```\n{solution_code}\n```\n\n"
            "Format your response with: \n"
            "1. Comprehensive walkthrough of how each part works and design decisions\n"
            "2. 'VIVA QUESTIONS:' followed by numbered questions and answer keys."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        text, used = await self.complete_with_budget(messages, tokens_used)

        # Parse out viva questions
        viva_questions: list[str] = []
        if "VIVA QUESTIONS:" in text:
            parts = text.split("VIVA QUESTIONS:", 1)[1]
            lines = [
                line.strip()
                for line in parts.split("\n")
                if line.strip() and line.strip()[0].isdigit()
            ]
            viva_questions = lines[:5]

        return text, viva_questions, used

    async def generate_hint(
        self,
        task_description: str,
        current_code: str,
        error_output: str,
        tokens_used: int = 0,
    ) -> tuple[str, int]:
        """
        Produce pedagogical hint without revealing the entire answer.
        """
        system_prompt = (
            "You are a NUST lab assistant in Hint Mode. "
            "Never give full code solution. Point out logical flaws, explain the concept, "
            "and suggest what specific function or line the student should check."
        )
        user_prompt = (
            f"Task: {task_description}\n\n"
            f"Current Code:\n```\n{current_code}\n```\n\n"
            f"Error / Test Failure:\n{error_output}\n\n"
            "Provide a focused hint to guide the student forward."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        return await self.complete_with_budget(messages, tokens_used)
