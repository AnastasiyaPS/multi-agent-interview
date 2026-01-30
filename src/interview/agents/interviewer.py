from __future__ import annotations
import re
from typing import Optional

from ..core.utils import one_sentence, one_question

class InterviewerAgent:
    """
    Видимый агент. НЕ проверяет факты, НЕ классифицирует — только задаёт один вопрос.
    """

    def respond(
        self,
        question_to_ask: str,
        return_to_topic_text: Optional[str],
        fact_check_notes: Optional[str],
    ) -> str:
        bridge = one_sentence(return_to_topic_text)
        fact = one_sentence(fact_check_notes)
        q = one_question(question_to_ask) or "Можешь рассказать подробнее?"

        parts = []
        if bridge:
            parts.append(bridge)
        if fact:
            parts.append(fact)
        parts.append(q)

        # ровно 1 вопрос
        out = []
        question_count = 0
        for line in parts:
            line = re.sub(r"\s+", " ", line).strip()
            if line.endswith("?"):
                if question_count == 0:
                    out.append(line)
                    question_count += 1
            else:
                out.append(line)

        if question_count == 0:
            out.append("Расскажи подробнее?")

        return "\n".join(out[:3])
