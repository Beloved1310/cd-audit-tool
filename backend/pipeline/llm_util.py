"""Groq chat model and helpers for structured generation."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq
from pydantic import BaseModel
from typing import TypeVar

from backend.pipeline.groq_llm import chat_groq as _core_chat_groq, invoke_groq

TModel = TypeVar("TModel", bound=BaseModel)

load_dotenv()

_PROMPTS_ROOT = Path(__file__).resolve().parent.parent / "prompts"


def load_prompt(name: str) -> str:
    return (_PROMPTS_ROOT / name).read_text(encoding="utf-8")


def chat_groq() -> ChatGroq:
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise RuntimeError("GROQ_API_KEY is not set")
    return _core_chat_groq()


def invoke_structured(
    model_cls: type[TModel],
    system_hint: str,
    user_content: str,
) -> TModel:
    """Run structured output; Groq + Llama 3.3 supports tool-style structured output via LangChain."""
    llm = chat_groq().with_structured_output(model_cls)
    msg = HumanMessage(
        content=f"{system_hint}\n\n---\n\n{user_content}" if system_hint else user_content
    )
    out = invoke_groq(llm, [msg])
    if isinstance(out, model_cls):
        return out
    if isinstance(out, dict):
        return model_cls.model_validate(out)
    raise TypeError(f"Unexpected structured output type: {type(out)}")
