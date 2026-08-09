from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_bootstrap_expands_nupkg_through_temporary_zip_copy():
    source = (ROOT / "scripts" / "bootstrap-dev-env.ps1").read_text(encoding="utf-8")

    assert "$expandArchivePath = $zipCachePath" in source
    assert "$temporaryArchivePath = $zipCachePath + '.zip'" in source
    assert "Expand-Archive -LiteralPath $expandArchivePath" in source
    assert "Remove-Item -LiteralPath $temporaryArchivePath" in source
    assert "Expand-Archive -LiteralPath $zipCachePath" not in source
