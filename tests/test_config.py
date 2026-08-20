from __future__ import annotations

import stat

from argus.config import config_dir, config_env_path, load_file_env, mask, save_keys


def test_config_dir_respects_xdg_config_home(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("os.name", "posix")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert config_dir() == tmp_path / "argus"


def test_config_env_path_is_dot_env_inside_config_dir(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert config_env_path() == tmp_path / "argus" / ".env"


def test_save_keys_creates_file_with_owner_only_permissions(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    path = save_keys({"EXA_API_KEY": "secret123"})

    assert path.exists()
    mode = stat.S_IMODE(path.stat().st_mode)
    assert mode == stat.S_IRUSR | stat.S_IWUSR
    assert "EXA_API_KEY=secret123" in path.read_text()


def test_save_keys_merges_with_existing_and_preserves_untouched_keys(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    save_keys({"EXA_API_KEY": "first"})
    save_keys({"OPENAI_API_KEY": "second"})

    loaded = load_file_env(include_project_dotenv=False)
    assert loaded == {"EXA_API_KEY": "first", "OPENAI_API_KEY": "second"}


def test_save_keys_skips_empty_values(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    save_keys({"EXA_API_KEY": "real", "OPENAI_API_KEY": ""})

    loaded = load_file_env(include_project_dotenv=False)
    assert loaded == {"EXA_API_KEY": "real"}


def test_load_file_env_project_dotenv_overrides_global(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    save_keys({"EXA_API_KEY": "global-value"})

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / ".env").write_text("EXA_API_KEY=project-value\n")
    monkeypatch.chdir(project_dir)

    assert load_file_env(include_project_dotenv=True)["EXA_API_KEY"] == "project-value"


def test_load_file_env_without_project_dotenv_ignores_cwd(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    save_keys({"EXA_API_KEY": "global-value"})

    project_dir = tmp_path / "project2"
    project_dir.mkdir()
    (project_dir / ".env").write_text("EXA_API_KEY=project-value\n")
    monkeypatch.chdir(project_dir)

    assert load_file_env(include_project_dotenv=False)["EXA_API_KEY"] == "global-value"


def test_mask_short_value_fully_masked() -> None:
    assert mask("short") == "*****"


def test_mask_long_value_shows_prefix_and_suffix() -> None:
    assert mask("sk-proj-abcdefgh12345678wxyz") == "sk-p...wxyz"
