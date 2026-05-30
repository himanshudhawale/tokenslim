import io
import json
import sys

import pytest

from tokenslim.cli import main


def test_count_from_file(tmp_path, capsys):
    f = tmp_path / "sample.py"
    f.write_text("x = 1\nprint(x)\n", encoding="utf-8")
    rc = main(["count", str(f)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Cost estimate" in out
    assert "gpt-4o" in out


def test_slim_in_place(tmp_path, capsys):
    f = tmp_path / "sample.py"
    f.write_text("# remove me\nx = 1\n", encoding="utf-8")
    rc = main(["slim", "-i", str(f)])
    assert rc == 0
    assert "remove me" not in f.read_text(encoding="utf-8")
    err = capsys.readouterr().err
    assert "saved" in err


def test_slim_stdout(tmp_path, capsys):
    f = tmp_path / "sample.py"
    f.write_text("# remove me\nx = 1\n", encoding="utf-8")
    rc = main(["slim", str(f)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "x = 1" in out
    assert "remove me" not in out


def test_count_stdin(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO("hello world\n"))
    rc = main(["count"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "TOTAL" not in out  # single input, no total line


def test_unknown_model_rejected(tmp_path):
    f = tmp_path / "s.py"
    f.write_text("x = 1\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        main(["count", "--model", "bogus", str(f)])


def test_budget_within(tmp_path, capsys):
    f = tmp_path / "s.py"
    f.write_text("x = 1\n", encoding="utf-8")
    rc = main(["count", "--budget", "1000", str(f)])
    assert rc == 0
    assert "within budget" in capsys.readouterr().err


def test_budget_exceeded(tmp_path, capsys):
    f = tmp_path / "s.py"
    f.write_text("word " * 200, encoding="utf-8")
    rc = main(["count", "--budget", "5", str(f)])
    assert rc == 2
    assert "OVER BUDGET" in capsys.readouterr().err


def test_count_directory_recursive(tmp_path, capsys):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "a.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "pkg" / "b.js").write_text("let y = 2;\n", encoding="utf-8")
    (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n")  # non-text, ignored
    rc = main(["count", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "a.py" in out
    assert "b.js" in out
    assert "image.png" not in out


def test_count_ignores_dot_git(tmp_path, capsys):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config.py").write_text("secret = 1\n", encoding="utf-8")
    (tmp_path / "main.py").write_text("x = 1\n", encoding="utf-8")
    rc = main(["count", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "main.py" in out
    assert "config.py" not in out


def test_count_json_output(tmp_path, capsys):
    f = tmp_path / "s.py"
    f.write_text("x = 1\n", encoding="utf-8")
    rc = main(["count", "--json", str(f)])
    out = capsys.readouterr().out
    assert rc == 0
    data = json.loads(out)
    assert data["total_tokens"] > 0
    assert data["files"][0]["path"].endswith("s.py")
    assert "gpt-4o" in data["cost"]


def test_count_json_budget_over(tmp_path, capsys):
    f = tmp_path / "s.py"
    f.write_text("word " * 200, encoding="utf-8")
    rc = main(["count", "--json", "--budget", "5", str(f)])
    out = capsys.readouterr().out
    assert rc == 2
    data = json.loads(out)
    assert data["over_budget"] is True


def test_slim_json_output(tmp_path, capsys):
    f = tmp_path / "s.py"
    f.write_text("# comment\n" * 10 + "x = 1\n", encoding="utf-8")
    rc = main(["slim", "--json", str(f)])
    out = capsys.readouterr().out
    assert rc == 0
    data = json.loads(out)
    assert data["total_tokens_saved"] > 0
    assert data["files"][0]["percent_saved"] > 0
