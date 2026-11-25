from pathlib import Path

import pytest

from joinpilot.config import REPO_ROOT, ProfilingSettings, Settings


def test_defaults_are_safe_for_local_development() -> None:
    settings = Settings(_env_file=None)
    assert settings.app_env == "dev"
    assert settings.cors_origins == ["http://localhost:5173"]
    assert settings.max_upload_bytes == 50 * 1024 * 1024


def test_environment_variables_override_defaults(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("MAX_UPLOAD_MB", "5")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CORS_ORIGINS", '["https://joinpilot.example"]')
    settings = Settings(_env_file=None)
    assert settings.max_upload_bytes == 5 * 1024 * 1024
    assert settings.projects_dir == tmp_path / "projects"
    assert settings.cors_origins == ["https://joinpilot.example"]


def test_env_example_documents_every_setting() -> None:
    text = (REPO_ROOT / ".env.example").read_text()
    keys = {
        line.lstrip("# ").split("=", 1)[0]
        for line in text.splitlines()
        if "=" in line and line.lstrip("# ").split("=", 1)[0].isupper()
    }
    expected = {
        name.upper() for name in Settings.model_fields if name not in {"synth", "profiling"}
    }
    expected |= {f"PROFILING__{name.upper()}" for name in ProfilingSettings.model_fields}
    assert expected <= keys, sorted(expected - keys)
