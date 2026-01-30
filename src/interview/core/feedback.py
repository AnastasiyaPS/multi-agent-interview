from __future__ import annotations

from typing import List, Dict, Any, Tuple
from collections import defaultdict
import re


def _short(text: str, limit: int = 180) -> str:
    t = re.sub(r"\s+", " ", (text or "").strip())
    return (t[:limit] + "…") if len(t) > limit else t


def _decision_from_counts(counts: Dict[str, int], grade_hint: str) -> Tuple[str, str, int]:
    strong = counts.get("STRONG", 0)
    weak = counts.get("WEAK", 0)
    hall = counts.get("HALLUCINATION", 0)
    off = counts.get("OFFTOPIC", 0)
    refus = counts.get("REFUSAL", 0)

    bad = weak + hall
    focus_risk = off + refus

    grade = (grade_hint or "junior").capitalize()

    if refus >= 2:
        return grade, "No Hire", 30
    if bad >= 4:
        return grade, "No Hire", 55
    if bad >= 2 or focus_risk >= 3:
        return grade, "Hire", 70
    if strong >= 4 and bad == 0 and focus_risk == 0:
        return grade, "Strong Hire", 85
    return grade, "Hire", 75


def build_feedback(turns: List[Dict[str, Any]], grade_hint: str) -> str:
    counts = defaultdict(int)

    topics = defaultdict(lambda: {
        "confirmed": 0,
        "gaps": 0,
        "examples": [],       # (question_answered, answer)
        "gaps_items": [],     # (question_answered, answer, expected)
        "offtopic_items": [], # (question_answered, answer)
    })

    off_topic_events = 0
    clarity_good = 0
    clarity_bad = 0

    for t in turns:
        meta = t.get("meta") or {}
        kind = (meta.get("kind") or "").upper()
        topic = meta.get("topic") or "generic"

        counts[kind] += 1

        q_answered = meta.get("question_answered") or ""
        a = t.get("user_message", "")

        # clarity proxy
        if len(_short(a)) >= 40 and any(x in a.lower() for x in ["это", "потому", "например", "отличается", "затем", "в итоге"]):
            clarity_good += 1
        elif len(_short(a)) < 10:
            clarity_bad += 1

        if kind == "STRONG":
            topics[topic]["confirmed"] += 1
            if q_answered and a:
                topics[topic]["examples"].append((q_answered, a))

        elif kind in {"WEAK", "HALLUCINATION"}:
            topics[topic]["gaps"] += 1
            expected = meta.get("expected_answer_short") or ""
            topics[topic]["gaps_items"].append((q_answered, a, expected))

        elif kind == "OFFTOPIC":
            off_topic_events += 1
            topics[topic]["offtopic_items"].append((q_answered, a))

    grade, rec, conf = _decision_from_counts(counts, grade_hint)

    lines = []
    lines.append("## A) Decision")
    lines.append(f"- Grade: **{grade}**")
    lines.append(f"- Hiring Recommendation: **{rec}**")
    lines.append(f"- Confidence Score: **{conf}%**")
    lines.append("")

    lines.append("## B) Hard Skills (Technical Review)")
    if not topics:
        lines.append("- Недостаточно данных.")
    else:
        for topic, st in topics.items():
            lines.append(f"- **{topic}**")

            if st["confirmed"]:
                lines.append(f"  - ✅ Confirmed Skills: {st['confirmed']}")
                q, a = st["examples"][0]
                lines.append(f"    - Пример: Q: {_short(q)} | A: {_short(a)}")

            if st["gaps"]:
                lines.append(f"  - ❌ Knowledge Gaps: {st['gaps']}")
                for q, a, expected in st["gaps_items"][:2]:
                    if q:
                        lines.append(f"    - Вопрос: {_short(q)}")
                    if a:
                        lines.append(f"      Ответ: {_short(a)}")
                    if expected:
                        lines.append(f"      Правильно: {_short(expected)}")

            if st["offtopic_items"]:
                lines.append(f"  - ⚠️ Off-topic/уход от вопроса: {len(st['offtopic_items'])}")
                q, a = st["offtopic_items"][0]
                lines.append(f"    - Пример: Q: {_short(q)} | A: {_short(a)}")

    lines.append("")
    lines.append("## C) Soft Skills & Communication")
    clarity = "в целом хорошо: ответы чаще структурные" if clarity_good >= clarity_bad else "есть проблемы: ответы часто короткие/обрывочные"
    lines.append(f"- Clarity: {clarity} (good={clarity_good}, weak={clarity_bad}).")
    lines.append("- Honesty: честное «не знаю» — нормально; плохо, когда вместо ответа идёт уход в сторону.")
    asked_by_candidate = sum(1 for t in turns if "?" in (t.get("user_message") or ""))
    lines.append(f"- Engagement: встречные вопросы от кандидата: {asked_by_candidate}.")
    if off_topic_events:
        lines.append(f"- Focus: были попытки сменить тему/оффтопик: {off_topic_events} (снижает оценку коммуникации).")
    else:
        lines.append("- Focus: оффтопика почти не было — плюс.")

    lines.append("")
    lines.append("## D) Next Steps (Roadmap)")
    gap_topics = [tp for tp, st in topics.items() if st["gaps"] > 0]
    if gap_topics:
        lines.append("- Темы для подтягивания по результатам интервью:")
        for tp in gap_topics:
            lines.append(f"  - {tp}: закрыть пробелы по вопросам из раздела Hard Skills (5–10 практических задач).")
    else:
        lines.append("- Явных технических провалов по заданным вопросам не видно. Следующий шаг — расширить покрытие тем и усложнить кейсы.")

    if off_topic_events:
        lines.append("- Отдельно: тренировать дисциплину ответа (сначала по вопросу, потом уточнения/контекст).")

    return "\n".join(lines)
