from __future__ import annotations
from .base import BaseLLM

class MistralLLM(BaseLLM):
    def __init__(self, api_key: str, model: str):
        from mistralai import Mistral
        self.client = Mistral(api_key=api_key)
        self.model = model

    def generate(self, system: str, user: str, temperature: float = 0.3) -> str:
        resp = self.client.chat.complete(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
        )
        return resp.choices[0].message.content.strip()
