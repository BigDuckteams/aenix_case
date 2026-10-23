from __future__ import annotations

import pytest

from engine.runtime.jdk import detect_jdk


@pytest.mark.jdk
def test_detect_jdk_finds_supported_version():
    info = detect_jdk()
    assert info.javac is not None
    assert info.java is not None
    assert info.ok, f"нужен JDK 21+, найден {info.javac}"
