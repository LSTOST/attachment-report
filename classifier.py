from __future__ import annotations

from typing import Literal

from models import QuizAnswers

TypeCode = Literal["SECURE", "ANXIOUS", "AVOIDANT", "FEARFUL"]

THRESHOLD = 3.5


class ClassificationError(Exception):
    pass


def classify_attachment(answers: dict[str, int]) -> tuple[TypeCode, float, float]:
    required = [f"A{i}" for i in range(1, 7)] + [f"B{i}" for i in range(1, 7)]
    missing = [k for k in required if k not in answers]
    if missing:
        raise ClassificationError(f"missing keys: {sorted(missing)}")

    for k in required:
        v = answers[k]
        if not isinstance(v, int) or v < 1 or v > 7:
            raise ClassificationError(f"invalid value for {k}: {v}")

    anxiety = sum(answers[f"A{i}"] for i in range(1, 7)) / 6.0
    avoidance = sum(answers[f"B{i}"] for i in range(1, 7)) / 6.0

    high_anx = anxiety >= THRESHOLD
    high_avo = avoidance >= THRESHOLD

    if not high_anx and not high_avo:
        code: TypeCode = "SECURE"
    elif high_anx and not high_avo:
        code = "ANXIOUS"
    elif not high_anx and high_avo:
        code = "AVOIDANT"
    else:
        code = "FEARFUL"

    return code, round(anxiety, 2), round(avoidance, 2)


def classify_from_quiz(quiz: QuizAnswers) -> tuple[TypeCode, float, float]:
    return classify_attachment(quiz.answers)
