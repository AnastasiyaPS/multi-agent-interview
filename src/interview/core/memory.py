from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

def normalize_grade(raw: str) -> str:
    g = (raw or "").strip().lower()
    if "sen" in g or "сень" in g:
        return "senior"
    if "mid" in g or "мид" in g:
        return "middle"
    return "junior"

def difficulty_from_grade(g: str) -> str:
    if g == "senior":
        return "hard"
    if g == "middle":
        return "medium"
    return "easy"

@dataclass
class Memory:
    candidate_name: str
    position: str
    grade: str
    experience: str
    tech_stack: List[str] = field(default_factory=list)

    difficulty: str = "easy"
    last_question: Optional[str] = None
    last_topic: Optional[str] = None

    last_user_messages: List[str] = field(default_factory=list)
    asked_questions: List[str] = field(default_factory=list)

    followup_streak: int = 0

    # не скакать по теме:
    topic_weak_streak: Dict[str, int] = field(default_factory=dict)
    topic_strong_streak: Dict[str, int] = field(default_factory=dict)

    llm: Optional[Any] = None

    def apply_defaults(self):
        self.grade = normalize_grade(self.grade)
        self.difficulty = difficulty_from_grade(self.grade)

    def bump_up(self):
        if self.difficulty == "easy":
            self.difficulty = "medium"
        elif self.difficulty == "medium":
            self.difficulty = "hard"

    def bump_down(self):
        if self.difficulty == "hard":
            self.difficulty = "medium"
        elif self.difficulty == "medium":
            self.difficulty = "easy"

    def remember_user(self, msg: str):
        self.last_user_messages.append(msg)
        self.last_user_messages = self.last_user_messages[-6:]

    def remember_question(self, q: str, topic: Optional[str]):
        self.last_question = q
        self.last_topic = topic
        self.asked_questions.append(q)
        self.asked_questions = self.asked_questions[-60:]

    def mark_topic(self, topic: Optional[str], kind: str):
        if not topic:
            return
        k = (kind or "").upper()
        if k == "STRONG":
            self.topic_strong_streak[topic] = self.topic_strong_streak.get(topic, 0) + 1
            self.topic_weak_streak[topic] = 0
        elif k in {"WEAK", "HALLUCINATION"}:
            self.topic_weak_streak[topic] = self.topic_weak_streak.get(topic, 0) + 1
            self.topic_strong_streak[topic] = 0
        else:
            self.topic_weak_streak[topic] = 0
            self.topic_strong_streak[topic] = 0
