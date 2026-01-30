from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union


def _format_internal_thoughts(thoughts: Union[str, List[Dict[str, str]], None]) -> str:

    if thoughts is None:
        return ""
    if isinstance(thoughts, str):
        # ensure trailing newline formatting is consistent
        t = thoughts.replace("\r\n", "\n")
        if t and not t.endswith("\n"):
            t += "\n"
        return t

    # list[{"role": "...", "content": "..."}]
    lines: List[str] = []
    for item in thoughts:
        role = str(item.get("role", "Agent"))
        content = str(item.get("content", "")).replace("\r\n", "\n").strip()
        lines.append(f"[{role}]: {content}\n")
    return "".join(lines)


@dataclass
class TurnLog:
    turn_id: int
    agent_visible_message: str
    user_message: str
    internal_thoughts: Union[str, List[Dict[str, str]], None] = None
    meta: Optional[Dict[str, Any]] = None  # можно хранить для себя, но НЕ пишем в итоговый JSON

    def to_public_dict(self) -> Dict[str, Any]:
        # Строгая структура под финальный тест
        return {
            "turn_id": self.turn_id,
            "agent_visible_message": self.agent_visible_message,
            "user_message": self.user_message,
            "internal_thoughts": _format_internal_thoughts(self.internal_thoughts),
        }


@dataclass
class InterviewLog:
    participant_name: str
    turns: List[TurnLog] = field(default_factory=list)

    # можно держать служебное, но НЕ выводить в итоговый файл
    session_meta: Optional[Dict[str, Any]] = None
    final_feedback: Optional[str] = None

    def add_turn(self, turn: TurnLog) -> None:
        self.turns.append(turn)

    def to_public_dict(self) -> Dict[str, Any]:
        return {
            "participant_name": self.participant_name,
            "turns": [t.to_public_dict() for t in self.turns],
            "final_feedback": self.final_feedback or "",
        }

    def save(self, path: str) -> None:
        data = self.to_public_dict()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
