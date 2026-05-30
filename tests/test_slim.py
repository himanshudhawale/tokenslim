from tokenslim.slim import slim_text


def test_strips_python_comments():
    src = "# a comment\nx = 1  # inline\nprint(x)\n"
    res = slim_text(src, ext=".py")
    assert "a comment" not in res.text
    assert "inline" not in res.text
    assert "x = 1" in res.text
    assert "print(x)" in res.text


def test_keeps_shebang():
    src = "#!/usr/bin/env python\nx = 1\n"
    res = slim_text(src, ext=".py")
    assert res.text.startswith("#!/usr/bin/env python")


def test_does_not_strip_hash_in_string():
    src = 'url = "https://x#frag"\n'
    res = slim_text(src, ext=".py")
    assert "https://x#frag" in res.text


def test_strips_slash_comments():
    src = "// header\nint x = 1; // inline\n/* block\ncomment */\nreturn x;\n"
    res = slim_text(src, ext=".js")
    assert "header" not in res.text
    assert "inline" not in res.text
    assert "block" not in res.text
    assert "int x = 1;" in res.text
    assert "return x;" in res.text


def test_collapses_blank_lines():
    src = "a = 1\n\n\n\n\nb = 2\n"
    res = slim_text(src, ext=".py")
    assert "\n\n\n" not in res.text


def test_keep_comments_flag():
    src = "# keep me\nx = 1\n"
    res = slim_text(src, ext=".py", strip_comments=False)
    assert "keep me" in res.text


def test_reports_savings():
    src = "# comment line\n" * 20 + "x = 1\n"
    res = slim_text(src, ext=".py")
    assert res.tokens_saved > 0
    assert 0 < res.percent_saved <= 100


def test_no_ext_only_whitespace():
    src = "plain text\n\n\n\nmore text\n"
    res = slim_text(src)
    assert "plain text" in res.text
    assert "\n\n\n" not in res.text


def test_empty_input():
    res = slim_text("")
    assert res.text == ""
    assert res.tokens_saved == 0
    assert res.percent_saved == 0.0
