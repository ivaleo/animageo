"""Централизованная конфигурация логирования для AnimaGeo.

Пакет не вызывает logging.basicConfig при импорте — настройка
явная через configure_logging(). CLI вызывает её при старте;
библиотечный код (AnimaGeoScene, parsers и т.д.) полагается на
уже настроенные хендлеры или на дефолтный WARNING→stderr.
"""

from __future__ import annotations

import logging
import sys
from typing import Literal

LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

_FMT_SHORT = "%(name)s: %(levelname)s: %(message)s"
_FMT_DEBUG = "%(asctime)s %(name)s [%(levelname)s] %(message)s"


def configure_logging(
    level: LogLevel | int = "WARNING",
    fmt: str | None = None,
    stream=None,
) -> None:
    """Настроить logging для всего пакета animageo.

    Parameters
    ----------
    level : str или int
        Уровень логирования. По умолчанию WARNING.
    fmt : str или None
        Пользовательский формат. Если None — выбирается автоматически
        в зависимости от уровня (DEBUG с timestamp, остальные — краткий).
    stream
        Поток вывода (по умолчанию sys.stderr).
    """
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.WARNING)

    if fmt is None:
        fmt = _FMT_DEBUG if level <= logging.DEBUG else _FMT_SHORT

    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(fmt))

    root = logging.getLogger()
    # Удаляем старые хендлеры чтобы избежать дублирования при повторных вызовах
    for h in list(root.handlers):
        root.removeHandler(h)
    root.addHandler(handler)
    root.setLevel(level)

    # Убеждаемся что логгер пакета animageo не фильтрует сообщения
    pkg = logging.getLogger("animageo")
    pkg.setLevel(level)
