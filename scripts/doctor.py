"""Проверка окружения разработки: python scripts/doctor.py

Выводит чек-лист инструментов и код возврата 1, если нет обязательных.
Docker нужен только для сборки образов и сдачи, поэтому его отсутствие — предупреждение.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from dataclasses import dataclass


@dataclass
class Tool:
    name: str
    command: str
    version_args: list[str]
    pattern: str
    minimum: tuple[int, ...] | None = None
    required: bool = True
    hint: str = ""


TOOLS = [
    Tool("Python", sys.executable, ["--version"], r"(\d+(?:\.\d+)+)", (3, 12), hint="python.org"),
    Tool("uv", "uv", ["--version"], r"uv (\d+(?:\.\d+)+)", (0, 5), hint="python -m pip install uv"),
    Tool("Node.js", "node", ["--version"], r"v(\d+(?:\.\d+)+)", (22,), hint="nodejs.org"),
    Tool("pnpm", "pnpm", ["--version"], r"(\d+(?:\.\d+)+)", (9,), hint="npm install -g pnpm"),
    Tool(
        "JDK (javac)",
        "javac",
        ["-version"],
        r"javac (\d+(?:\.\d+)*)",
        (21,),
        hint="Нужен JDK 21+ (Temurin), javac в PATH",
    ),
    Tool("JDK (java)", "java", ["-version"], r'version "(\d+(?:\.\d+)*)', (21,)),
    Tool("git", "git", ["--version"], r"(\d+(?:\.\d+)+)", (2,)),
    Tool(
        "Docker",
        "docker",
        ["--version"],
        r"(\d+(?:\.\d+)+)",
        (24,),
        required=False,
        hint="Нужен для docker compose up и сдачи",
    ),
]


def parse(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def check(tool: Tool) -> tuple[str, str]:
    path = tool.command if tool.command == sys.executable else shutil.which(tool.command)
    if not path:
        return ("FAIL" if tool.required else "WARN", f"не найден. {tool.hint}".strip())
    try:
        proc = subprocess.run(
            [path, *tool.version_args], capture_output=True, text=True, timeout=20, encoding="utf-8"
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return ("FAIL" if tool.required else "WARN", f"не запускается: {exc}")
    match = re.search(tool.pattern, proc.stdout + proc.stderr)
    if not match:
        return ("WARN", "версию определить не удалось")
    version = match.group(1)
    if tool.minimum and parse(version) < tool.minimum:
        need = ".".join(map(str, tool.minimum))
        return ("FAIL" if tool.required else "WARN", f"{version}, нужна {need}+. {tool.hint}".strip())
    return ("OK", version)


def main() -> int:
    failed = False
    for tool in TOOLS:
        status, detail = check(tool)
        failed |= status == "FAIL"
        print(f"[{status:<4}] {tool.name:<12} {detail}")
    print()
    print("Окружение готово." if not failed else "Есть проблемы: исправьте пункты FAIL.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
