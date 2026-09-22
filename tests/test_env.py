from bot.env import load_env_file, parse_env


def test_parse_env_ignores_comments_blank_and_invalid_lines():
    text = '# comment\nA=1\nB="two"\nC=\'three\'\n\nnot-a-line\n'

    assert parse_env(text) == {"A": "1", "B": "two", "C": "three"}


def test_parse_env_keeps_value_with_equals_signs():
    assert parse_env("URL=https://x/y?a=b") == {"URL": "https://x/y?a=b"}


def test_load_env_file_fills_only_missing_keys(tmp_path):
    path = tmp_path / "bot.env"
    path.write_text("A=1\nB=2\n", encoding="utf-8")
    environ = {"A": "keep"}

    loaded = load_env_file([str(path)], environ)

    assert environ == {"A": "keep", "B": "2"}
    assert loaded == {"B": "2"}


def test_load_env_file_missing_paths_is_noop(tmp_path):
    assert load_env_file([str(tmp_path / "nope")], {}) == {}
