"""Разбор входящих файлов проекта: пути, кодировка, лимиты, архивы (docs/08-api.md § 2, § 11).

Защита: пути нормализуются, ``..`` и абсолютные пути отклоняются (zip-slip), принимаются только
``.java`` в UTF-8 (BOM удаляется), размеры и число файлов ограничены.
"""

from __future__ import annotations

import io
import posixpath
import re
import zipfile
from collections.abc import Iterable

from app.errors import bad_request, payload_too_large

MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_ARCHIVE_BYTES = 10 * 1024 * 1024
MAX_UNPACKED_BYTES = 50 * 1024 * 1024  # защита от «бомбы»: сумма распакованных размеров
MAX_FILES = 200
_DRIVE = re.compile(r"^[A-Za-z]:")


def normalize_path(raw: str) -> str:
    """Относительный POSIX-путь без ``.``/``..`` или ``bad_request``."""
    path = raw.replace("\\", "/").strip()
    if not path or "\0" in path:
        raise bad_request("пустой или недопустимый путь файла", path=raw)
    if path.startswith("/") or _DRIVE.match(path):
        raise bad_request("абсолютные пути запрещены", path=raw)
    parts = [part for part in path.split("/") if part not in ("", ".")]
    if not parts or any(part == ".." for part in parts):
        raise bad_request("путь выходит за пределы проекта", path=raw)
    return posixpath.join(*parts)


def decode_source(path: str, data: bytes) -> str:
    """UTF-8 без BOM; другая кодировка — ``400``."""
    if len(data) > MAX_FILE_BYTES:
        raise payload_too_large(f"файл {path} больше 2 МБ", path=path, size=len(data))
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise bad_request(
            f"файл {path} не в кодировке UTF-8", path=path, position=exc.start
        ) from exc


def collect(items: Iterable[tuple[str, bytes]]) -> dict[str, str]:
    """Файлы проекта ``путь → текст``: только ``.java``, без дублей, с лимитами."""
    files: dict[str, str] = {}
    for raw_path, data in items:
        path = normalize_path(raw_path)
        if not path.endswith(".java"):
            raise bad_request(f"принимаются только .java: {path}", path=path)
        if path in files:
            raise bad_request(f"файл {path} указан дважды", path=path)
        files[path] = decode_source(path, data)
        if len(files) > MAX_FILES:
            raise payload_too_large(f"в проекте больше {MAX_FILES} файлов")
    if not files:
        raise bad_request("нет ни одного .java файла")
    return files


def read_zip(data: bytes) -> list[tuple[str, bytes]]:
    """Содержимое ``.java`` из zip; остальные файлы архива игнорируются."""
    if len(data) > MAX_ARCHIVE_BYTES:
        raise payload_too_large("архив больше 10 МБ", size=len(data))
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise bad_request("не удалось прочитать zip-архив") from exc
    result: list[tuple[str, bytes]] = []
    total = 0
    with archive:
        infos = [info for info in archive.infolist() if not info.is_dir()]
        if len(infos) > MAX_FILES * 5:
            raise payload_too_large("в архиве слишком много файлов")
        for info in infos:
            path = normalize_path(info.filename)  # zip-slip отсекается здесь
            if path.startswith("__MACOSX/") or not path.endswith(".java"):
                continue
            if info.file_size > MAX_FILE_BYTES:
                raise payload_too_large(f"файл {path} больше 2 МБ", path=path, size=info.file_size)
            total += info.file_size
            if total > MAX_UNPACKED_BYTES:
                raise payload_too_large("распакованный размер архива слишком велик")
            result.append((path, archive.read(info)))
    return result
