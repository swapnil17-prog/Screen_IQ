"""
LLM gateway. Every model call in the app goes through `get_llm().generate(...)`.

- AnthropicLLM: Claude via the official async SDK, using structured outputs
  (`messages.parse` + a Pydantic schema), adaptive thinking with a per-task
  effort level, and server-side refusal fallbacks.
- MockLLM (app.llm.mock): deterministic heuristics for offline demos and tests.

Callers pass the structured `context` their prompt was rendered from; the real
provider ignores it, the mock provider computes its answer from it.
"""

import logging
import time
from functools import lru_cache
from typing import Any, Literal, Protocol, TypeVar

import anthropic
from pydantic import BaseModel, ValidationError

from app.core.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)
Effort = Literal["low", "medium", "high"]

FALLBACK_BETA = "server-side-fallback-2026-07-01"


class LLMError(Exception):
    """Base error; `message` is safe to show to end users."""

    def __init__(self, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.message = message
        self.retryable = retryable


class LLMUnavailableError(LLMError):
    pass


class LLMRefusalError(LLMError):
    pass


class LLMClient(Protocol):
    provider: str
    model: str

    async def generate(
        self,
        *,
        task: str,
        system: str,
        prompt: str,
        schema: type[T],
        effort: Effort = "medium",
        max_tokens: int = 16000,
        context: dict[str, Any] | None = None,
    ) -> T: ...


class AnthropicLLM:
    provider = "anthropic"

    def __init__(self, api_key: str | None, model: str):
        if not api_key:
            raise LLMUnavailableError(
                "ANTHROPIC_API_KEY is not configured. Set it, or use LLM_PROVIDER=mock for a local demo."
            )
        self.model = model
        self._client = anthropic.AsyncAnthropic(
            api_key=api_key,
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,  # SDK retries 408/409/429/5xx with backoff
        )

    async def generate(
        self,
        *,
        task: str,
        system: str,
        prompt: str,
        schema: type[T],
        effort: Effort = "medium",
        max_tokens: int = 16000,
        context: dict[str, Any] | None = None,
    ) -> T:
        extra: dict[str, Any] = {}
        betas: list[str] = []
        if settings.llm_enable_fallbacks:
            betas.append(FALLBACK_BETA)
            # "default" routes a declined request to Anthropic's recommended model for
            # that refusal category. Sent raw: this SDK version only types the list form.
            extra["extra_body"] = {"fallbacks": "default"}

        last_validation_error: ValidationError | None = None
        for attempt in (1, 2):
            started = time.perf_counter()
            try:
                response = await self._client.beta.messages.parse(
                    model=self.model,
                    max_tokens=max_tokens,
                    system=system,
                    messages=[{"role": "user", "content": prompt}],
                    output_format=schema,
                    thinking={"type": "adaptive"},
                    output_config={"effort": effort},
                    betas=betas or anthropic.omit,
                    **extra,
                )
            except ValidationError as e:
                # Schema-valid JSON that failed a client-side constraint — retry once.
                last_validation_error = e
                logger.warning("LLM task=%s output failed validation (attempt %d): %s", task, attempt, e)
                continue
            except anthropic.AuthenticationError as e:
                raise LLMUnavailableError("The AI provider rejected the API key. Check ANTHROPIC_API_KEY.") from e
            except anthropic.PermissionDeniedError as e:
                raise LLMUnavailableError("The API key is not permitted to use the configured model.") from e
            except anthropic.NotFoundError as e:
                raise LLMUnavailableError(f"Model '{self.model}' was not found. Check LLM_MODEL.") from e
            except anthropic.RateLimitError as e:
                raise LLMUnavailableError(
                    "The AI provider is rate limiting requests. Please retry in a minute.", retryable=True
                ) from e
            except anthropic.BadRequestError as e:
                logger.error("LLM task=%s bad request: %s", task, e.message)
                raise LLMError(f"The AI request was rejected: {e.message}") from e
            except anthropic.APIStatusError as e:
                logger.error("LLM task=%s status=%s: %s", task, e.status_code, e.message)
                raise LLMUnavailableError(
                    "The AI provider is temporarily unavailable. Please retry.", retryable=True
                ) from e
            except anthropic.APIConnectionError as e:
                raise LLMUnavailableError("Could not reach the AI provider. Please retry.", retryable=True) from e

            elapsed = time.perf_counter() - started
            logger.info(
                "LLM task=%s model=%s stop=%s in=%s out=%s %.1fs request_id=%s",
                task,
                response.model,
                response.stop_reason,
                response.usage.input_tokens,
                response.usage.output_tokens,
                elapsed,
                getattr(response, "_request_id", None),
            )

            if response.stop_reason == "refusal":
                category = getattr(response.stop_details, "category", None) if response.stop_details else None
                raise LLMRefusalError(
                    f"The AI model declined this request{f' ({category})' if category else ''}."
                )
            if response.stop_reason == "max_tokens":
                max_tokens = min(max_tokens * 2, 64000)
                logger.warning("LLM task=%s hit max_tokens; retrying with %d", task, max_tokens)
                continue
            if response.parsed_output is None:
                logger.warning("LLM task=%s returned no parsed output (attempt %d)", task, attempt)
                continue
            return response.parsed_output

        if last_validation_error is not None:
            raise LLMError("The AI returned output that did not match the expected format.") from last_validation_error
        raise LLMError("The AI did not return a usable response. Please retry.", retryable=True)


@lru_cache(maxsize=1)
def get_llm() -> LLMClient:
    if settings.llm_provider == "mock":
        from app.llm.mock import MockLLM

        return MockLLM()
    return AnthropicLLM(api_key=settings.anthropic_api_key, model=settings.llm_model)
