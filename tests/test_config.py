"""Pruebas de la lectura de configuración desde variables de entorno."""
import pytest

from src.config import _env_bool


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "si", "sí", " on "])
def test_truthy_values(monkeypatch, value):
    monkeypatch.setenv("FLAG_TEST", value)
    assert _env_bool("FLAG_TEST", False) is True


@pytest.mark.parametrize("value", ["0", "false", "no", "off", ""])
def test_falsy_values(monkeypatch, value):
    monkeypatch.setenv("FLAG_TEST", value)
    assert _env_bool("FLAG_TEST", True) is False


def test_default_when_missing(monkeypatch):
    monkeypatch.delenv("FLAG_TEST", raising=False)
    assert _env_bool("FLAG_TEST", True) is True
    assert _env_bool("FLAG_TEST", False) is False
