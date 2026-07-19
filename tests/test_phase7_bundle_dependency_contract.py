from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_dependency_checker_accepts_product_only_in_app_tree():
    script = (ROOT / "scripts" / "check-bundle-dependencies.py").read_text(encoding="utf-8")

    assert "Product code is intentionally staged under app/embedagent" in script
    assert "Manifest source_mode must be wheel-installed" in script
    assert "Manifest project_wheels must contain the exact six project wheels" in script
    assert "Duplicate product import package" in script
