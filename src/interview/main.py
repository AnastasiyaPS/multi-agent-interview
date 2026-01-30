from __future__ import annotations

import argparse

from .session import InterviewSession


def _norm_grade(s: str) -> str:
    t = (s or "").strip().lower()
    if t in {"junior", "джун", "j"}:
        return "Junior"
    if t in {"middle", "мидл", "m"}:
        return "Middle"
    if t in {"senior", "сеньор", "s"}:
        return "Senior"
    # fallback
    return "Junior"


def run_cli():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", type=int, default=None, help="Номер сценария 1..5")
    args = parser.parse_args()

    scenario = args.scenario
    if scenario is None:
        try:
            scenario = int(input("Номер сценария (1..5): ").strip())
        except Exception:
            scenario = 1
    if scenario not in {1, 2, 3, 4, 5}:
        scenario = 1

    print("Multi-agent Interview Trainer")
    name = input("Имя кандидата (ФИО на русском): ").strip() or "Кандидат"
    position = input("Позиция (например Backend): ").strip() or "Backend"
    grade = _norm_grade(input("Грейд (Junior/Middle/Senior): ").strip())
    experience = input("Опыт (например 1 год Python): ").strip() or "-"

    session = InterviewSession(
        position=position,
        grade=grade,
        experience=experience,
        candidate_name=name,
        scenario_id=scenario,
    )

    # приветствие + первый вопрос (НЕ логируем)
    print()
    print(session.first_message())

    # пользователь отвечает на первый вопрос turn_id=1
    while True:
        user = input("\n> ")
        reply = session.step(user)
        print()
        print(reply)

        # завершаем
        if reply and reply.startswith("## A) Decision"):
            print(f"\nЛог сохранён в: interview_log_{scenario}.json")
            break
        if reply.strip().lower() in {"интервью завершено.", "интервью завершено"}:
            print(f"\nЛог сохранён в: interview_log_{scenario}.json")
            break
