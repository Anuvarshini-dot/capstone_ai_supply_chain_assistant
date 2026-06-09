import time
import httpx
from openai import OpenAI, APITimeoutError, APIConnectionError, InternalServerError
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL, OPENAI_EMBEDDING_MODEL

client = OpenAI(
    api_key=OPENAI_API_KEY,
    base_url=OPENAI_BASE_URL,
    http_client=httpx.Client(verify=False, timeout=30.0),
)

MODEL = OPENAI_MODEL
EMBEDDING_MODEL = OPENAI_EMBEDDING_MODEL

_RETRYABLE = (APITimeoutError, APIConnectionError, InternalServerError)


def _retry(fn, retries: int = 2, delay: float = 1.5):
    for attempt in range(retries + 1):
        try:
            return fn()
        except _RETRYABLE:
            if attempt == retries:
                raise
            time.sleep(delay * (attempt + 1))


def chat(messages: list, temperature: float = 0.3, max_tokens: int = 500, **kwargs) -> str:
    def _call():
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        return response.choices[0].message.content
    return _retry(_call)


def chat_with_tools(messages: list, tools: list, tool_choice="auto", temperature: float = 0.1):
    """Returns the full message object so callers can inspect tool_calls."""
    def _call():
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
            temperature=temperature,
        )
        return response.choices[0].message
    return _retry(_call)


def embed(texts: list) -> list:
    def _call():
        response = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
        return [item.embedding for item in response.data]
    return _retry(_call)
