"""Рабочее пространство сборки: исходники версии на диске (docs/07 § 2.1).

Каталог ``builds/<content_hash>/`` содержит ``src/`` (файлы проекта с сохранением путей) и
``classes/`` (результат компиляции). Совпадающий хеш — повторное использование каталога и кеш
результата компиляции.
"""

from __future__ import annotations

import os
import shutil
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

_READY = ".ready"


@dataclass(frozen=True, slots=True)
class Workspace:
    root: Path
    src: Path
    classes: Path
    content_hash: str

    @property
    def sources(self) -> list[str]:
        """Пути ``.java`` относительно ``src/`` (в порядке имён) для аргумента-файла javac."""
        return sorted(p.relative_to(self.src).as_posix() for p in self.src.rglob("*.java"))


def _safe_target(src: Path, relative: str) -> Path:
    target = (src / relative).resolve()
    if src.resolve() not in target.parents:
        raise ValueError(f"путь выходит за каталог сборки: {relative}")
    return target


def materialize(files: Mapping[str, str], builds_dir: Path, content_hash: str) -> Workspace:
    """Записывает файлы версии в ``builds/<hash>/src``; готовый каталог не пересоздаётся."""
    root = builds_dir / content_hash
    workspace = Workspace(root, root / "src", root / "classes", content_hash)
    if (root / _READY).exists():
        return workspace

    builds_dir.mkdir(parents=True, exist_ok=True)
    staging = builds_dir / f".{content_hash}.{uuid.uuid4().hex[:8]}"
    src = staging / "src"
    src.mkdir(parents=True)
    (staging / "classes").mkdir()
    for relative, text in files.items():
        target = _safe_target(src, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(text.encode("utf-8"))
    (staging / _READY).write_text("ok", encoding="utf-8")
    try:
        os.replace(staging, root)
    except OSError:
        # параллельный запрос успел создать тот же каталог: берём готовый
        shutil.rmtree(staging, ignore_errors=True)
        if not (root / _READY).exists():
            raise
    return workspace
