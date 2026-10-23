"""Выгрузка OpenAPI-схемы в файл без запуска сервера.

    uv run python -m app.export_openapi ../frontend/openapi.json

Из этого файла ``pnpm gen:api`` генерирует TypeScript-типы (docs/03-tech-stack.md, ADR-10).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from app.main import create_app


def main() -> None:
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "openapi.json")
    schema = create_app().openapi()
    target.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"OpenAPI written: {target}")  # ASCII: консоль Windows может быть не в UTF-8


if __name__ == "__main__":
    main()
