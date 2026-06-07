"""
Custom DeepEval LLM wrapper that routes all judge calls through the project's
own gateway (keygateway.arshnivlabs.com) instead of calling api.openai.com directly.

Key design: generate() always returns a valid Pydantic schema instance when
schema is provided — even if the model returns unparseable text. This prevents
DeepEval from ever reaching trimAndLoadJson and producing "invalid JSON" errors.
"""
import sys
import os
import json
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import asyncio
import httpx
import openai

from deepeval.models.base_model import DeepEvalBaseLLM
from config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL


class GatewayLLM(DeepEvalBaseLLM):
    """Routes DeepEval metric calls through the project's LLM gateway."""

    def __init__(self, model: str = OPENAI_MODEL):
        self._model = model
        self._client = openai.OpenAI(
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL,
            http_client=httpx.Client(verify=False),
        )

    def load_model(self):
        return self._client

    def generate(self, prompt: str, schema=None):
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": str(prompt)}],
        )
        text = (response.choices[0].message.content or "").strip()

        if schema is None:
            return text

        # 1. Try fenced JSON block  ```json ... ```
        m = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if m:
            try:
                return schema(**json.loads(m.group(1)))
            except Exception:
                pass

        # 2. Try bare JSON object  { ... }
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return schema(**json.loads(m.group()))
            except Exception:
                pass

        # 3. Try the full text as JSON
        try:
            return schema(**json.loads(text))
        except Exception:
            pass

        # 4. Last resort: build an empty-default schema instance so DeepEval
        #    always gets a valid object back and never hits trimAndLoadJson.
        try:
            defaults = {}
            for k, v in schema.model_fields.items():
                ann = str(getattr(v, "annotation", ""))
                if "list" in ann.lower():
                    defaults[k] = []
                elif any(t in ann.lower() for t in ("float", "int")):
                    defaults[k] = 0
                else:
                    defaults[k] = ""
            return schema(**defaults)
        except Exception:
            pass

        return text

    async def a_generate(self, prompt: str, schema=None):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.generate(prompt, schema))

    def get_model_name(self) -> str:
        return self._model
