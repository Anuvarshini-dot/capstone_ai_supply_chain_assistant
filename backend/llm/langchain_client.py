"""
LangChain-compatible LLM that routes through the project's custom gateway.
Used by the NL-to-SQL agent and any other LangChain tools.
"""
import httpx
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from langchain_openai import ChatOpenAI
from config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL


def get_langchain_llm(temperature: float = 0.0) -> ChatOpenAI:
    return ChatOpenAI(
        model=OPENAI_MODEL,
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL,
        http_client=httpx.Client(verify=False),
        temperature=temperature,
    )
