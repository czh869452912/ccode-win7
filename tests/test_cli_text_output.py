import io


def _text_stream(encoding):
    raw = io.BytesIO()
    return raw, io.TextIOWrapper(raw, encoding=encoding, errors="strict")


def test_prepare_cli_standard_streams_preserves_encoding_and_replaces_errors(monkeypatch):
    import embedagent.cli.text_output as text_output

    stdout_bytes, stdout = _text_stream("cp1252")
    stderr_bytes, stderr = _text_stream("utf-8")
    with monkeypatch.context() as patch:
        patch.setattr(text_output.sys, "stdout", stdout)
        patch.setattr(text_output.sys, "stderr", stderr)
        text_output.prepare_cli_standard_streams()

    assert stdout.encoding == "cp1252"
    assert stderr.encoding == "utf-8"
    assert stdout.errors == "replace"
    assert stderr.errors == "replace"

    stdout.write("该操作会修改工作区文件。")
    stderr.write("该操作会修改工作区文件。")
    stdout.flush()
    stderr.flush()
    assert b"?" in stdout_bytes.getvalue()
    assert stderr_bytes.getvalue().decode("utf-8") == "该操作会修改工作区文件。"


def test_prepare_cli_standard_streams_leaves_non_reconfigurable_streams_untouched(monkeypatch):
    import embedagent.cli.text_output as text_output

    stdout = io.StringIO()
    stderr = io.StringIO()
    with monkeypatch.context() as patch:
        patch.setattr(text_output.sys, "stdout", stdout)
        patch.setattr(text_output.sys, "stderr", stderr)
        text_output.prepare_cli_standard_streams()

    stdout.write("该操作会修改工作区文件。")
    stderr.write("该操作会修改工作区文件。")
    assert stdout.getvalue() == "该操作会修改工作区文件。"
    assert stderr.getvalue() == "该操作会修改工作区文件。"
