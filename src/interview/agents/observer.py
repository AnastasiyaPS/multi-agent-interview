from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Literal, Any, List

from ..core.prompts import OBSERVER_SYSTEM, OBSERVER_USER_TEMPLATE
from ..core.utils import safe_json, one_sentence, one_question
from ..core.prompts import OBSERVER_SYSTEM, OBSERVER_USER_TEMPLATE, VERIFIER_SYSTEM, VERIFIER_USER_TEMPLATE

Kind = Literal[
    "STRONG", "NORMAL", "WEAK",
    "OFFTOPIC", "HALLUCINATION", "ROLE_REVERSAL",
    "NO_STACK", "REFUSAL"
]


@dataclass
class ObserverResult:
    kind: Kind
    reason: str
    instruction: str
    difficulty_action: str  # UP|DOWN|SAME
    topic_hint: Optional[str]
    need_followup: bool
    followup_question: Optional[str]
    fact_check_notes: Optional[str]
    return_to_topic_text: Optional[str]
    expected_answer_short: Optional[str]




_STOP_WORDS = {
    "и", "в", "на", "что", "это", "как", "чем", "когда", "где", "почему",
    "the", "a", "an", "to", "in", "on", "and", "or", "of", "for",
}

def _normalize(text: str) -> str:
    t = (text or "").lower().strip()
    t = re.sub(r"\s+", " ", t)
    return t

def _tokens(text: str) -> List[str]:
    t = _normalize(text)
    t = re.sub(r"[^a-zа-я0-9_+\s-]", " ", t)
    parts = []
    for p in t.split():
        p = p.strip("-_+")
        if len(p) >= 3 and p not in _STOP_WORDS:
            parts.append(p)
    return parts

def _keywords(text: str) -> set[str]:
    return set(_tokens(text))


def _looks_like_gibberish(text: str) -> bool:
    s = (text or "").strip()
    if not s:
        return True
    if len(s) <= 2:
        return True
    alpha = sum(ch.isalpha() for ch in s)
    if alpha == 0:
        return True
    if alpha / max(1, len(s)) < 0.30:
        return True
    if s.startswith("/") and not re.match(r"^/(stop|help)\b", s.lower()):
        return True
    return False

def _looks_relevant(answer: str, last_question: str) -> bool:

    if not answer or not last_question:
        return False
    a = _keywords(answer)
    q = _keywords(last_question)
    if not a or not q:
        return False
    return len(a.intersection(q)) >= 1

def _bridge_back(last_question: Optional[str]) -> str:
    if last_question:
        return f"Понял(а), давай вернёмся к интервью: {last_question}"
    return "Понял(а), давай вернёмся к интервью и продолжим."

def _contains_word(text: str, word: str) -> bool:
    """
    Match by word boundary (RU+EN). Avoid substring false positives.
    """
    return re.search(rf"(^|[^a-zа-я0-9_]){re.escape(word)}([^a-zа-я0-9_]|$)", text) is not None


class ObserverAgent:
    #  явные смены темы
    OFFTOPIC_WORDS = [
        "погода", "кот", "коты", "котик", "собака", "собаки",
        "анекдот", "фильм", "сериал", "музыка", "гороскоп",
    ]

    ROLE_REVERSAL_WORDS = [
        "зарплата", "оффер", "компания", "условия", "отпуск", "бенефиты",
        "что за проект", "какая команда", "сколько платите",
    ]

    REFUSAL_WORDS = [
        "не хочу", "не буду", "отстань", "не надо", "не интересно",
    ]

    WEAK_WORDS = [
        "не знаю", "не уверен", "затрудняюсь", "не помню", "сложно сказать",
    ]

    def __init__(self, llm: Any):
        self.llm = llm
    def _verify_with_llm(self, text: str, mem) -> Optional[dict]:
        if not self.llm:
            return None

        user = VERIFIER_USER_TEMPLATE.format(
            position=mem.position,
            grade=mem.grade,
            experience=mem.experience,
            tech_stack=", ".join(mem.tech_stack) or "-",
            last_question=mem.last_question or "-",
            user_message=text,
            recent_questions="\n".join(mem.asked_questions[-12:]) or "-",
        )
        raw = self.llm.generate(VERIFIER_SYSTEM, user, temperature=0.0)
        return safe_json(raw) or None

    def analyze(self, user_message: str, mem) -> ObserverResult:
        text = user_message or ""
        low = _normalize(text)

        if _looks_like_gibberish(text):
            return ObserverResult(
                kind="OFFTOPIC",
                reason="empty/gibberish input",
                instruction="Мягко верни к последнему вопросу и попроси ответ по сути.",
                difficulty_action="SAME",
                topic_hint=mem.last_topic,
                need_followup=True,
                followup_question=mem.last_question or "Ответь, пожалуйста, на последний вопрос?",
                fact_check_notes=None,
                return_to_topic_text=one_sentence(_bridge_back(mem.last_question)),
                expected_answer_short=None,
            )

        for ph in self.REFUSAL_WORDS:
            if ph in low:
                return ObserverResult(
                    kind="REFUSAL",
                    reason="candidate refusal",
                    instruction="Предложи /stop или вернуться к интервью по стеку.",
                    difficulty_action="SAME",
                    topic_hint=mem.last_topic,
                    need_followup=True,
                    followup_question="Хочешь завершить интервью командой /stop или продолжим?",
                    fact_check_notes=None,
                    return_to_topic_text="Ок, понимаю.",
                    expected_answer_short=None,
                )

        for ph in self.ROLE_REVERSAL_WORDS:
            if ph in low:
                return ObserverResult(
                    kind="ROLE_REVERSAL",
                    reason="role reversal",
                    instruction="Коротко ответь 1 предложением и верни к интервью.",
                    difficulty_action="SAME",
                    topic_hint=mem.last_topic,
                    need_followup=True,
                    followup_question=mem.last_question or "Вернёмся к интервью: ответь на последний вопрос?",
                    fact_check_notes=None,
                    return_to_topic_text="Коротко: это тренажёр, без реального оффера — давай продолжим интервью.",
                    expected_answer_short=None,
                )

        # Это правило ставим ДО off-topic слов.
        if mem.last_question and _looks_relevant(text, mem.last_question):
            # если есть маркеры "не знаю"  WEAK, иначе STRONG/NORMAL
            for ph in self.WEAK_WORDS:
                if ph in low:
                    return ObserverResult(
                        kind="WEAK",
                        reason="relevant but uncertain",
                        instruction="Упрости вопрос и уточни в этой же теме.",
                        difficulty_action="DOWN",
                        topic_hint=mem.last_topic,
                        need_followup=True,
                        followup_question=mem.last_question,
                        fact_check_notes=None,
                        return_to_topic_text=None,
                        expected_answer_short="Схема ответа: определение → 2–3 ключевых пункта → короткий пример.",
                    )
            return ObserverResult(
                kind="STRONG",
                reason="relevant answer (guardrail)",
                instruction="Ответ релевантный: можно усложнить или перейти к следующей подтеме в этом же топике.",
                difficulty_action="UP",
                topic_hint=mem.last_topic,
                need_followup=False,
                followup_question=None,
                fact_check_notes=None,
                return_to_topic_text=None,
                expected_answer_short=None,
            )
        # Mistral
        verdict = self._verify_with_llm(user_message, mem)
        if verdict:
            kind = str(verdict.get("kind", "")).upper()
            confidence = int(verdict.get("confidence", 0) or 0)

            if confidence >= 70 and kind in {
                "STRONG", "NORMAL", "WEAK",
                "OFFTOPIC", "HALLUCINATION",
                "ROLE_REVERSAL", "REFUSAL",
            }:
                need_followup = bool(verdict.get("need_followup", False))
                followup = (
                    one_question(verdict.get("followup_question"))
                    if need_followup else None
                )

                fact = one_sentence(verdict.get("fact_check_notes"))
                bridge = one_sentence(verdict.get("return_to_topic_text"))

                if kind in {"OFFTOPIC", "HALLUCINATION"} and not bridge:
                    bridge = one_sentence(_bridge_back(mem.last_question))

                if kind == "STRONG":
                    diff = "UP"
                elif kind in {"WEAK", "OFFTOPIC", "HALLUCINATION", "REFUSAL"}:
                    diff = "DOWN"
                else:
                    diff = "SAME"

                return ObserverResult(
                    kind=kind,
                    reason=f"verifier(conf={confidence})",
                    instruction="Следовать вердикту verifier.",
                    difficulty_action=diff,
                    topic_hint=mem.last_topic,
                    need_followup=need_followup,
                    followup_question=followup,
                    fact_check_notes=fact,
                    return_to_topic_text=bridge,
                    expected_answer_short=None,
                )


        # 4) строго по словам
        for w in self.OFFTOPIC_WORDS:
            if _contains_word(low, w):
                return ObserverResult(
                    kind="OFFTOPIC",
                    reason="off-topic keyword",
                    instruction="Мягко верни к последнему вопросу.",
                    difficulty_action="SAME",
                    topic_hint=mem.last_topic,
                    need_followup=True,
                    followup_question=mem.last_question or "Ответь, пожалуйста, по теме интервью?",
                    fact_check_notes=None,
                    return_to_topic_text=one_sentence(_bridge_back(mem.last_question)),
                    expected_answer_short=None,
                )

        # 5) weak (но уже не релевантный) — всё равно уточняем
        for ph in self.WEAK_WORDS:
            if ph in low:
                return ObserverResult(
                    kind="WEAK",
                    reason="candidate unsure",
                    instruction="Упрости вопрос/задай уточнение в той же теме.",
                    difficulty_action="DOWN",
                    topic_hint=mem.last_topic,
                    need_followup=True,
                    followup_question=mem.last_question or "Можешь объяснить проще, своими словами?",
                    fact_check_notes=None,
                    return_to_topic_text=None,
                    expected_answer_short="Схема ответа: определение → 2–3 пункта → пример.",
                )

        if self.llm:
            user = OBSERVER_USER_TEMPLATE.format(
                name=mem.candidate_name,
                position=mem.position,
                grade=mem.grade,
                experience=mem.experience,
                tech_stack=", ".join(mem.tech_stack) or "-",
                last_question=mem.last_question or "-",
                recent_user_messages="\n".join(mem.last_user_messages[-6:]) or "-",
                recent_questions="\n".join(mem.asked_questions[-20:]) or "-",
                user_message=text,
            )
            raw = self.llm.generate(OBSERVER_SYSTEM, user, temperature=0.2)
            data = safe_json(raw) or {}

            kind = (data.get("kind") or "NORMAL").upper()
            if kind not in {"STRONG","NORMAL","WEAK","OFFTOPIC","HALLUCINATION","ROLE_REVERSAL","NO_STACK","REFUSAL"}:
                kind = "NORMAL"

            if kind == "OFFTOPIC" and mem.last_question and _looks_relevant(text, mem.last_question):
                kind = "NORMAL"

            difficulty_action = (str(data.get("difficulty_action") or "SAME").upper())
            if difficulty_action not in {"UP","DOWN","SAME"}:
                difficulty_action = "SAME"

            need_followup = bool(data.get("need_followup", False))
            followup = one_question(data.get("followup_question")) if need_followup else None

            fact = one_sentence(data.get("fact_check_notes"))
            bridge = one_sentence(data.get("return_to_topic_text"))
            expected = data.get("expected_answer_short")
            expected = expected.strip() if isinstance(expected, str) and expected.strip() else None

            if kind in {"OFFTOPIC", "HALLUCINATION"} and not bridge:
                bridge = one_sentence(_bridge_back(mem.last_question))

            topic_hint = data.get("topic_hint")
            topic_hint = topic_hint.strip() if isinstance(topic_hint, str) and topic_hint.strip() else None

            return ObserverResult(
                kind=kind,
                reason=str(data.get("reason") or "llm"),
                instruction=str(data.get("instruction") or "Продолжай интервью."),
                difficulty_action=difficulty_action,
                topic_hint=topic_hint,
                need_followup=need_followup,
                followup_question=followup,
                fact_check_notes=fact,
                return_to_topic_text=bridge,
                expected_answer_short=expected,
            )

        return ObserverResult(
            kind="NORMAL",
            reason="fallback",
            instruction="Продолжай интервью по текущей теме.",
            difficulty_action="SAME",
            topic_hint=mem.last_topic,
            need_followup=False,
            followup_question=None,
            fact_check_notes=None,
            return_to_topic_text=None,
            expected_answer_short=None,
        )
