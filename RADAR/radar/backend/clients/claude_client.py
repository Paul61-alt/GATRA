import json
import logging
import os
from typing import Any, Optional, Type, TypeVar

import anthropic
from braintrust import traced
from pydantic import BaseModel

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-20250514"

T = TypeVar("T", bound=BaseModel)


class ClaudeClient:
    def __init__(self, api_key: Optional[str] = None) -> None:
        self._client = anthropic.Anthropic(api_key=api_key or os.environ["ANTHROPIC_API_KEY"])

    @traced
    def extract_json(self, system: str, user: str, max_tokens: int = 4096) -> dict:
        """Call Claude and parse JSON from the response."""
        message = self._client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = message.content[0].text

        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end == 0:
            logger.error("claude no JSON in response text=%s", text[:200])
            raise ValueError("No JSON found in Claude response")
        return json.loads(text[start:end])

    @traced
    def extract_model(self, model_cls: Type[T], system: str, user: str, max_tokens: int = 4096) -> T:
        data = self.extract_json(system, user, max_tokens)
        return model_cls.model_validate(data)

    @traced
    def complete(self, system: str, user: str, max_tokens: int = 2000) -> str:
        message = self._client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return message.content[0].text
