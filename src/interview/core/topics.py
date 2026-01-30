from __future__ import annotations

import re
from typing import List, Dict, Optional, Tuple

from .prompts import QUESTION_GEN_SYSTEM, QUESTION_GEN_USER_TEMPLATE
from .utils import safe_json


# словарь
VOCAB_ALIASES: Dict[str, List[str]] = {
    # ЯП
    "go": ["go", "golang", "го", "голанг"],
    "python": ["python", "питон", "py"],
    "java": ["java"],
    "javascript": ["javascript", "js", "жаваскрипт"],
    "typescript": ["typescript", "ts", "тайпскрипт"],

    # данные
    "sql": ["sql"],
    "postgres": ["postgres", "postgresql", "постгрес", "постгресql", "pg"],
    "mysql": ["mysql"],

    # backend/web
    "http": ["http", "https"],
    "rest": ["rest", "restful"],
    "grpc": ["grpc"],
    "graphql": ["graphql"],


    "docker": ["docker", "докер"],
    "kubernetes": ["kubernetes", "k8s", "кубер", "кубернетес"],
    "linux": ["linux", "линух", "ubuntu", "debian", "centos"],
    "git": ["git", "github", "gitlab"],

    # go ecosystem
    "gin": ["gin"],
    "echo": ["echo"],
    "fiber": ["fiber"],
}

# стандартные топики
TOPICS = [
    "go", "python",
    "sql",
    "http",
    "docker", "kubernetes",
    "git", "linux",
]


# вопросы
QUESTION_BANK: Dict[str, Dict[str, List[str]]] = {
    "go": {
        "easy": [
            "Что такое goroutine и чем она отличается от потока?",
            "Чем отличается slice от array в Go?",
            "Как устроены ошибки в Go и как принято их обрабатывать?",
            "Что такое map в Go и какие есть ограничения по ключам?",
        ],
        "medium": [
            "Что такое interface в Go? Как проверяется соответствие интерфейсу?",
            "Как работает channel: буферизованный vs небуферизованный? Пример, когда выбрать каждый.",
            "Что такое context в Go и зачем он нужен (timeouts/cancel)?",
            "Какие типичные причины data race и как их находить/исправлять?",
        ],
        "hard": [
            "Как бы ты спроектировал(а) worker pool в Go? Какие edge-cases учтёшь?",
            "Как устроена сборка мусора в Go и как она влияет на latency?",
            "Какие проблемы бывают при высоких нагрузках в Go (GC, contention, IO) и как диагностировать?",
        ],
    },
    "python": {
        "easy": [
            "Чем list отличается от dict?",
            "Как работают исключения (try/except)?",
            "Что такое virtualenv/venv и зачем он нужен?",
        ],
        "medium": [
            "Что такое iterator/iterable? Приведи пример.",
            "Что такое GIL и как он влияет на многопоточность?",
            "Чем отличается multiprocessing от threading в Python?",
        ],
        "hard": [
            "Когда выбирать async/await и какие типичные ошибки в async-коде?",
            "Как устроен garbage collector в Python на верхнем уровне?",
        ],
    },
    "sql": {
        "easy": [
            "Что такое первичный ключ и индекс? Зачем индекс нужен?",
            "Чем JOIN отличается от UNION?",
            "Что такое нормализация данных и зачем она нужна (в 1-2 предложениях)?",
        ],
        "medium": [
            "INNER JOIN vs LEFT JOIN — в чём разница? Приведи пример запроса.",
            "Что такое транзакция и уровни изоляции? Чем опасны dirty read/phantom read?",
            "Как работает составной индекс и как его правильно выбрать?",
        ],
        "hard": [
            "Как бы ты оптимизировал(а) медленный запрос? Какие шаги (EXPLAIN/ANALYZE, индексы, переписывание)?",
            "Что такое deadlock и как его диагностировать/минимизировать?",
        ],
    },
    "http": {
        "easy": [
            "Чем отличается GET от POST?",
            "Что означает код ответа 404 и 500?",
            "Что такое headers и для чего они нужны?",
        ],
        "medium": [
            "Что такое идемпотентность? Какие HTTP-методы идемпотентны?",
            "Что такое CORS и зачем он нужен?",
            "Как работает авторизация через JWT на высоком уровне?",
        ],
        "hard": [
            "Как работает HTTP-кеширование (ETag/Cache-Control) и какие подводные камни бывают?",
            "Как бы ты ограничивал(а) rate limit на API? Где хранить состояние?",
        ],
    },
    "docker": {
        "easy": [
            "Что такое Docker image и container?",
            "Для чего нужен Dockerfile?",
            "В чём разница между COPY и ADD?",
        ],
        "medium": [
            "CMD vs ENTRYPOINT — в чём разница и когда что использовать?",
            "Как работает сеть в Docker (bridge/host) на базовом уровне?",
            "Как бы ты уменьшил(а) размер образа (multi-stage build, slim base)?",
        ],
        "hard": [
            "Как бы ты построил(а) CI/CD пайплайн с Docker для микросервисов? Какие шаги?",
            "Какие риски безопасности контейнеров и как их снижать (least privilege, scanning)?",
        ],
    },
    "kubernetes": {
        "easy": [
            "Что такое Pod и Deployment в Kubernetes?",
            "Зачем нужны Service и Ingress?",
        ],
        "medium": [
            "Что такое readiness/liveness probes и зачем они нужны?",
            "Как бы ты раскатывал(а) обновления без даунтайма (rolling update)?",
        ],
        "hard": [
            "Какие причины CrashLoopBackOff и как ты бы отлаживал(а)?",
            "Как бы ты организовал(а) observability (logs/metrics/traces) в k8s?",
        ],
    },
    "git": {
        "easy": [
            "Чем отличаются merge и rebase?",
            "Как откатить последний коммит (разные варианты)?",
        ],
        "medium": [
            "Что такое cherry-pick и когда он уместен?",
            "Как решать конфликт при merge? Какой порядок действий?",
        ],
        "hard": [
            "Как бы ты настроил(а) git-flow или trunk-based development и почему?",
        ],
    },
    "linux": {
        "easy": [
            "Как посмотреть занятый порт и кто его слушает?",
            "Что делает команда grep и как ей искать по логам?",
        ],
        "medium": [
            "Как бы ты нашёл(а) причину высокой нагрузки на CPU/Memory на сервере?",
            "Что такое permissions (chmod) и почему 644/755 отличаются?",
        ],
        "hard": [
            "Как бы ты диагностировал(а) утечки файловых дескрипторов/сетевых соединений?",
        ],
    },
}


GENERIC: Dict[str, List[str]] = {
    "easy": [
        "Расскажи про свой последний проект: что делал(а) лично ты?",
        "Опиши типичный баг, который ты находил(а), и как ты его исправил(а).",
    ],
    "medium": [
        "Как ты дебажишь проблему в проде: какие шаги предпринимаешь?",
        "Что для тебя важнее: читаемость или производительность? Приведи пример компромисса.",
    ],
    "hard": [
        "Как бы ты спроектировал(а) сервис под высокую нагрузку: компоненты и компромиссы?",
        "Расскажи про случай, когда пришлось менять архитектуру. Что было до/после?",
    ],
}


def _norm_text(text: str) -> str:
    t = (text or "").lower()
    # normalize common aliases quickly
    t = t.replace("postgresql", "postgres")
    return t


def extract_tech_stack(text: str) -> List[str]:

    t = _norm_text(text)
    found: List[str] = []

    def add(x: str):
        if x not in found:
            found.append(x)


    for canonical, aliases in VOCAB_ALIASES.items():
        for a in aliases:
            if re.search(rf"(^|[^a-zа-я0-9_]){re.escape(a)}([^a-zа-я0-9_]|$)", t):
                add(canonical)
                break


    if ("postgres" in found or "mysql" in found) and "sql" not in found:
        add("sql")

    if "go" in found:
        found = ["go"] + [x for x in found if x != "go"]

    return found[:12]


def _topic_candidates(mem) -> List[str]:
    cands = []
    for t in (mem.tech_stack or []):
        if t in TOPICS and t not in cands:
            cands.append(t)

    if not cands:
        for msg in mem.last_user_messages[-3:]:
            for t in extract_tech_stack(msg):
                if t in TOPICS and t not in cands:
                    cands.append(t)

    if not cands:
        cands = ["http", "sql"]

    if "go" in cands:
        cands = ["go"] + [x for x in cands if x != "go"]

    return cands


def _ensure_generated(mem, topic: str, difficulty: str) -> None:
    if not hasattr(mem, "generated_questions"):
        mem.generated_questions = {}
    if topic not in mem.generated_questions:
        mem.generated_questions[topic] = {}
    if difficulty in mem.generated_questions[topic] and mem.generated_questions[topic][difficulty]:
        return

    if not mem.llm:
        mem.generated_questions[topic][difficulty] = []
        return

    already = "\n".join(mem.asked_questions[-25:]) or "-"
    user = QUESTION_GEN_USER_TEMPLATE.format(
        topic=topic,
        difficulty=difficulty,
        position=mem.position,
        grade=mem.grade,
        experience=mem.experience,
        already_asked=already,
    )
    raw = mem.llm.generate(QUESTION_GEN_SYSTEM, user, temperature=0.4)
    data = safe_json(raw) or {}
    qs = data.get("questions", [])

    out: List[str] = []
    if isinstance(qs, list):
        for q in qs:
            if isinstance(q, str):
                q = re.sub(r"\s+", " ", q).strip()
                if q and not q.endswith("?"):
                    q += "?"
                if q and q not in out and q not in mem.asked_questions:
                    out.append(q[:180])

    mem.generated_questions[topic][difficulty] = out


def pick_next_question(mem, topic_hint: Optional[str] = None, force_difficulty: Optional[str] = None) -> Tuple[str, Optional[str], str]:
    difficulty = force_difficulty or mem.difficulty
    candidates = _topic_candidates(mem)

    if topic_hint and topic_hint in TOPICS:
        candidates = [topic_hint] + [c for c in candidates if c != topic_hint]

    for topic in candidates:
        _ensure_generated(mem, topic, difficulty)

        bank = QUESTION_BANK.get(topic, {}).get(difficulty, [])
        gen = getattr(mem, "generated_questions", {}).get(topic, {}).get(difficulty, [])

        pool = [q for q in (bank + gen) if q and q not in mem.asked_questions]
        if pool:
            return pool[0], topic, "bank/gen"

    g = GENERIC.get(difficulty) or GENERIC["easy"]
    for q in g:
        if q not in mem.asked_questions:
            return q, None, "generic"
    return g[0], None, "generic"
