"""
In-memory conversation store (swap for Redis in production — see README
limitations). Implements the context-engineering requirements:

- Session memory: full turn history per session_id.
- Conversation summary: once history exceeds a turn threshold, older turns
  get compressed into a running summary via LLM, keeping only the most
  recent N raw turns verbatim. This bounds token growth for long sessions.
- Strict separation from retrieved knowledge: this store NEVER holds
  document chunks — only user/assistant chat turns. Agents combine the two
  only at prompt-construction time, and system prompts always instruct the
  LLM that retrieved knowledge outranks conversation memory on conflict.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.application.agents.state import ConversationTurn
from app.core.config import get_settings
from app.infrastructure.ai.llm_gateway import LLMGateway

_SUMMARIZE_SCHEMA = {
    "type": "object",
    "properties": {"summary": {"type": "string"}},
    "required": ["summary"],
    "additionalProperties": False,
}

_SUMMARIZE_PROMPT = """Compress the following conversation turns into a concise running summary
(3-5 sentences) capturing what documents/topics were discussed and any
conclusions reached. This will be used as background context in future
turns, not shown to the user."""


@dataclass
class _Session:
    turns: list[ConversationTurn] = field(default_factory=list)
    summary: str = ""


class ConversationMemoryStore:
    def __init__(self, llm: LLMGateway):
        self._llm = llm
        self._settings = get_settings()
        self._sessions: dict[str, _Session] = {}

    def get(self, session_id: str) -> _Session:
        return self._sessions.setdefault(session_id, _Session())

    async def add_turn(self, session_id: str, role: str, content: str) -> None:
        session = self.get(session_id)
        session.turns.append({"role": role, "content": content})  # type: ignore[typeddict-item]

        trigger = self._settings.conversation_summary_trigger_turns
        if len(session.turns) > trigger:
            overflow = session.turns[: len(session.turns) - trigger // 2]
            session.turns = session.turns[len(session.turns) - trigger // 2 :]
            await self._compress(session, overflow)

    async def _compress(self, session: _Session, overflow_turns: list[ConversationTurn]) -> None:
        text = "\n".join(f"{t['role']}: {t['content']}" for t in overflow_turns)
        prior = f"Previous summary: {session.summary}\n\n" if session.summary else ""
        result = await self._llm.chat_json(
            system_prompt=_SUMMARIZE_PROMPT,
            user_prompt=f"{prior}New turns to fold in:\n{text}",
            json_schema=_SUMMARIZE_SCHEMA,
            schema_name="conversation_summary",
            model_tier="fast",
        )
        session.summary = result["summary"]

    def get_context(self, session_id: str) -> tuple[str, list[ConversationTurn]]:
        session = self.get(session_id)
        return session.summary, session.turns
