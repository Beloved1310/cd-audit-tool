"""Shared Groq chat model — no Anthropic."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()


def chat_groq() -> ChatGroq:
    """Llama 3.3 on Groq, temperature 0. ``GROQ_API_KEY`` from the environment (dotenv)."""
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0,
        groq_api_key=os.environ.get("GROQ_API_KEY"),
    )
