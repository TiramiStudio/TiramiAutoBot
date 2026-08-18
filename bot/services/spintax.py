"""
Модуль для обработки спинтакса (рандомизации текста сообщений).
Поддерживает вложенные конструкции формата {Вариант1|Вариант2|{Вложенный1|Вложенный2}}.
"""

import random
import re

SPINTAX_PATTERN = re.compile(r"\{([^{}]+)\}")


def process_spintax(text: str) -> str:
    """
    Рекурсивно или циклически раскрывает все конструкции спинтакса в переданной строке.
    
    Пример:
        "{Привет|Здравствуйте}, {друг|коллега}!" -> "Здравствуйте, друг!"
    """
    if not text:
        return ""

    # Раскрываем самые глубокие фигурные скобки, пока они есть в тексте
    while True:
        match = SPINTAX_PATTERN.search(text)
        if not match:
            break
        options = match.group(1).split("|")
        chosen = random.choice(options)
        text = text[:match.start()] + chosen + text[match.end():]

    return text


def has_spintax(text: str) -> bool:
    """Проверяет, содержит ли текст конструкции спинтакса."""
    return bool(SPINTAX_PATTERN.search(text))


def generate_spintax_samples(text: str, count: int = 3) -> list[str]:
    """Генерирует несколько случайных вариантов текста для предпросмотра."""
    return [process_spintax(text) for _ in range(count)]
