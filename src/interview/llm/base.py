from __future__ import annotations
from abc import ABC, abstractmethod

class BaseLLM(ABC):
    @abstractmethod
    def generate(self, system: str, user: str, temperature: float = 0.3) -> str:
        raise NotImplementedError
