import io
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
