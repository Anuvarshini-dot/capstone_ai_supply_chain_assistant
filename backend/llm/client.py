import httpx
from openai import OpenAI
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL, OPENAI_EMBEDDING_MODEL

client = OpenAI(
    api_key=OPENAI_API_KEY,
    base_url=OPENAI_BASE_URL,
    http_client=httpx.Client(verify=False)
)

MODEL = OPENAI_MODEL
EMBEDDING_MODEL = OPENAI_EMBEDDING_MODEL


def chat(messages: list, temperature: float = 0.3, **kwargs) -> str:
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=temperature,
        **kwargs
    )
    return response.choices[0].message.content


def chat_with_tools(messages: list, tools: list, tool_choice="auto", temperature: float = 0.1):
    """Returns the full message object so callers can inspect tool_calls."""
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=tools,
        tool_choice=tool_choice,
        temperature=temperature,
    )
    return response.choices[0].message


def embed(texts: list) -> list:
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts
    )
    return [item.embedding for item in response.data]
