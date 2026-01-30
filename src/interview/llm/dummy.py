from __future__ import annotations
from .base import BaseLLM

class DummyLLM(BaseLLM):

    def generate(self, system: str, user: str, temperature: float = 0.3) -> str:
        # Возвращаем JSON-ответы для Observer и генератора вопросов
        u = (user or "").lower()

        if '"kind"' in u and "верни только валидный json" in (system or "").lower():
            return (
                '{'
                '"kind":"NORMAL",'
                '"reason":"dummy",'
                '"instruction":"Продолжай интервью, держи тему.",'
                '"difficulty_action":"SAME",'
                '"topic_hint":null,'
                '"need_followup":false,'
                '"followup_question":null,'
                '"fact_check_notes":null,'
                '"return_to_topic_text":null,'
                '"expected_answer_short":null'
                '}'
            )

        if '"questions"' in u and "сгенерируй 3–5 вопросов" in u:
            return '{"questions":["Чем отличается GET от POST?","Что такое индекс в БД?","Что такое транзакция?"]}'

        return "OK"
