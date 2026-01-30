from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from .config import settings
from .llm.dummy import DummyLLM
from .llm.mistral_llm import MistralLLM

from .core.memory import Memory
from .core.topics import extract_tech_stack, pick_next_question
from .core.feedback import build_feedback
from .core.logging import InterviewLog, TurnLog
from .core.utils import one_question

from .agents.observer import ObserverAgent
from .agents.interviewer import InterviewerAgent

STOP_RE = re.compile(r"(^/stop\b|\bстоп интервью\b|\bстоп\b)", re.I)


def make_llm():
    if settings.use_mistral and settings.mistral_api_key:
        return MistralLLM(settings.mistral_api_key, settings.mistral_model), "mistral"
    return DummyLLM(), "dummy"


class InterviewSession:


    def __init__(self, position: str, grade: str, experience: str, candidate_name: str, scenario_id: int):
        tech = extract_tech_stack(f"{position} {grade} {experience}")
        self.mem = Memory(
            candidate_name=candidate_name,
            position=position,
            grade=grade,
            experience=experience,
            tech_stack=tech,
        )
        self.mem.apply_defaults()

        llm, llm_name = make_llm()
        self.llm_name = llm_name
        self.mem.llm = llm

        self.observer = ObserverAgent(llm=llm)
        self.interviewer = InterviewerAgent()

        self.turn_id = 0
        self.scenario_id = scenario_id

        # Для правильной траектории финального теста:
        self.first_question_asked = False  # вопрос показали пользователю
        self.awaiting_first_answer = True  # ждём ответ на первый вопрос

        self.log = InterviewLog(
            participant_name=candidate_name,
            session_meta={
                "llm_provider": llm_name,
                "llm_model": settings.mistral_model if llm_name == "mistral" else None,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "position": position,
                "grade": grade,
                "experience": experience,
                "scenario_id": scenario_id,
            },
        )

    def _apply_difficulty(self, action: str):
        if action == "UP":
            self.mem.bump_up()
        elif action == "DOWN":
            self.mem.bump_down()

    def _choose_question(self, topic_hint: Optional[str] = None, force_difficulty: Optional[str] = None):
        q, topic, source = pick_next_question(self.mem, topic_hint=topic_hint, force_difficulty=force_difficulty)
        self.mem.remember_question(q, topic)  # sets last_question/last_topic
        return q, (topic or "generic"), source

    def first_message(self) -> str:

        stack = ", ".join(self.mem.tech_stack) if self.mem.tech_stack else "пока не распознан (скажи 2–3 технологии)"
        greeting = (
            f"Привет, {self.mem.candidate_name}! Я тренажёр тех-интервью (LLM: {self.llm_name.upper()}). "
            f"По вводным вижу стек: {stack}. Коротко расскажи про опыт и основной стек."
        )

        # Генерируем первый вопрос прямо здесь (не логируем), чтобы turn_id=1 начался с вопроса.
        primary_hint = self.mem.tech_stack[0] if self.mem.tech_stack else None
        first_q, topic, source = self._choose_question(topic_hint=primary_hint)
        self.first_question_asked = True

        # Показываем приветствие + первый вопрос
        return f"{greeting}\n\n{first_q}"

    def step(self, user_message: str) -> str:
        # /stop завершает и возвращает final_feedback
        if STOP_RE.search(user_message or ""):
            self.finish()
            return self.log.final_feedback or "Интервью завершено."

        # Первый вопрос уже был показан в first_message() тут пришёл ответ на него.
        if self.awaiting_first_answer:
            self.awaiting_first_answer = False
            self.turn_id = 1
            question_answered = self.mem.last_question
            topic_answered = self.mem.last_topic

            self.mem.remember_user(user_message)
            extra = extract_tech_stack(user_message)
            if extra:
                self.mem.tech_stack = list(dict.fromkeys(self.mem.tech_stack + extra))

            obs = self.observer.analyze(user_message, self.mem)
            self._apply_difficulty(obs.difficulty_action)
            self.mem.mark_topic(self.mem.last_topic, obs.kind)

            # выбираем следующий вопрос
            sticky_hint = obs.topic_hint or topic_answered
            can_followup = (self.mem.followup_streak < 2)

            if can_followup and obs.need_followup and obs.followup_question:
                next_q = one_question(obs.followup_question) or (question_answered or "Ответь на последний вопрос.")
                self.mem.remember_question(next_q, self.mem.last_topic)
                self.mem.followup_streak += 1
                source = "followup"
            else:
                force_diff = "easy" if obs.kind == "HALLUCINATION" else None
                next_q, _, source = self._choose_question(topic_hint=sticky_hint, force_difficulty=force_diff)
                self.mem.followup_streak = 0

            reply = self.interviewer.respond(
                question_to_ask=next_q,
                return_to_topic_text=obs.return_to_topic_text,
                fact_check_notes=obs.fact_check_notes,
            )

            self.log.add_turn(TurnLog(
                turn_id=self.turn_id,
                agent_visible_message=question_answered or "",
                user_message=user_message,
                internal_thoughts=[
                    {"role": "Observer", "content": f"kind={obs.kind} diff={obs.difficulty_action} reason={obs.reason}"},
                    {"role": "Interviewer", "content": "Сформулировать краткий вывод и задать следующий вопрос по теме."},
                ],
                meta={
                    "kind": obs.kind,
                    "topic": topic_answered or "generic",
                    "source": source,
                    "question_answered": question_answered,
                    "question_asked": next_q,
                    "expected_answer_short": obs.expected_answer_short,
                }
            ))

            return reply

        # Обычные ходы после первого
        self.turn_id += 1
        self.mem.remember_user(user_message)

        extra = extract_tech_stack(user_message)
        if extra:
            self.mem.tech_stack = list(dict.fromkeys(self.mem.tech_stack + extra))

        question_answered = self.mem.last_question
        topic_answered = self.mem.last_topic

        obs = self.observer.analyze(user_message, self.mem)
        self._apply_difficulty(obs.difficulty_action)
        self.mem.mark_topic(self.mem.last_topic, obs.kind)

        sticky_hint = obs.topic_hint or self.mem.last_topic
        if obs.kind in {"WEAK", "OFFTOPIC", "HALLUCINATION", "REFUSAL"} and self.mem.last_topic:
            sticky_hint = self.mem.last_topic

        can_followup = (self.mem.followup_streak < 2)

        if can_followup and obs.need_followup and obs.followup_question:
            next_q = one_question(obs.followup_question) or (question_answered or "Ответь на последний вопрос.")
            # ВАЖНО: follow-up возвращает к тому же вопросу
            self.mem.remember_question(next_q, self.mem.last_topic)
            self.mem.followup_streak += 1
            source = "followup"
        else:
            force_diff = "easy" if obs.kind == "HALLUCINATION" else None
            next_q, _, source = self._choose_question(topic_hint=sticky_hint, force_difficulty=force_diff)
            self.mem.followup_streak = 0

        reply = self.interviewer.respond(
            question_to_ask=next_q,
            return_to_topic_text=obs.return_to_topic_text,
            fact_check_notes=obs.fact_check_notes,
        )

        self.log.add_turn(TurnLog(
            turn_id=self.turn_id,
            agent_visible_message=question_answered or "",
            user_message=user_message,
            internal_thoughts=[
                {"role": "Observer", "content": f"kind={obs.kind} diff={obs.difficulty_action} reason={obs.reason}"},
                {"role": "Interviewer", "content": "Сформулировать краткий вывод и задать следующий вопрос по теме."},
            ],
            meta={
                "kind": obs.kind,
                "topic": topic_answered or "generic",
                "source": source,
                "question_answered": question_answered,
                "question_asked": next_q,
                "expected_answer_short": obs.expected_answer_short,
            }
        ))

        return reply

    def finish(self):
        # финальный фидбек
        turns = [t.__dict__ for t in self.log.turns]
        self.log.final_feedback = build_feedback(turns, self.mem.grade)

        filename = f"interview_log_{self.scenario_id}.json"
        self.log.save(filename)
