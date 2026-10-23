"""Обнаружение JDK: версии ``javac`` и ``java``.

Целевой уровень языка — Java 21 (``javac --release 21``), поэтому нужен JDK 21 или новее;
более новый JDK подходит, так как ``--release`` собирает под 21.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

MIN_JDK_MAJOR = 21


@dataclass(frozen=True, slots=True)
class JdkInfo:
    javac: str | None  # например "26" или "21.0.4"
    java: str | None
    major: int | None

    @property
    def ok(self) -> bool:
        return self.major is not None and self.major >= MIN_JDK_MAJOR


def tool_path(name: str, java_home: Path | None = None) -> str | None:
    """Путь к ``javac``/``java``: из ``JB_JAVA_HOME`` или из ``PATH``."""
    if java_home is not None:
        found = shutil.which(name, path=str(java_home / "bin"))
        if found:
            return found
    return shutil.which(name)


def _version(tool: str, flag: str, pattern: str) -> str | None:
    try:
        proc = subprocess.run(
            [tool, flag], capture_output=True, text=True, timeout=15, encoding="utf-8"
        )
    except (OSError, subprocess.SubprocessError):
        return None
    match = re.search(pattern, proc.stdout + proc.stderr)
    return match.group(1) if match else None


def detect_jdk(java_home: Path | None = None) -> JdkInfo:
    javac = tool_path("javac", java_home)
    java = tool_path("java", java_home)
    javac_version = _version(javac, "-version", r"javac\s+(\S+)") if javac else None
    java_version = _version(java, "-version", r'version\s+"([^"]+)"') if java else None
    major = None
    if javac_version:
        head = javac_version.split(".")[0]
        major = int(head) if head.isdigit() else None
    return JdkInfo(javac_version, java_version, major)
