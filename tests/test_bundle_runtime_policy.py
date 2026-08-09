import hashlib
import json

import pytest

from embedagent.bundle_policy import load_bundle_policy, load_current_bundle_policy


def _write_bundle_policy(
    root,
    applications=("embedagent.generic",),
    shells=("cli",),
    manifest_hash=None,
):
    for relative in ("app/embedagent", "runtime/python", "bin"):
        root.joinpath(*relative.split("/")).mkdir(parents=True, exist_ok=True)
    manifests = root / "manifests"
    manifests.mkdir()
    plan = {
        "schema_version": 1,
        "flavor_id": "minimal-cli",
        "allowed_agent_application_ids": list(applications),
        "shell_ids": list(shells),
    }
    plan_path = manifests / "bundle-plan.json"
    plan_path.write_text(json.dumps(plan, sort_keys=True), encoding="ascii")
    plan_sha256 = hashlib.sha256(plan_path.read_bytes()).hexdigest()
    (manifests / "bundle-manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "flavor_id": "minimal-cli",
                "bundle_plan_sha256": manifest_hash or plan_sha256,
            }
        ),
        encoding="ascii",
    )
    return root, plan_sha256


def test_bundle_policy_rejects_unplanned_application_and_shell(tmp_path):
    bundle, plan_sha256 = _write_bundle_policy(tmp_path)

    policy = load_bundle_policy(str(bundle))

    assert policy.bundled is True
    assert policy.bundle_plan_sha256 == plan_sha256
    assert policy.require_application("") == "embedagent.generic"
    assert policy.require_application("embedagent.generic") == "embedagent.generic"
    assert policy.require_shell("cli") == "cli"
    with pytest.raises(ValueError, match="not included in bundle flavor"):
        policy.require_application("embedagent.default_c_cpp")
    with pytest.raises(ValueError, match="not included in bundle flavor"):
        policy.require_shell("gui")


def test_absent_bundle_root_returns_unrestricted_development_policy():
    policy = load_bundle_policy(None)

    assert policy.bundled is False
    assert policy.require_application("tests.custom") == "tests.custom"
    assert policy.require_shell("gui") == "gui"


@pytest.mark.parametrize("malformation", ["missing_plan", "bad_hash", "empty_applications"])
def test_malformed_discovered_bundle_fails_closed(tmp_path, malformation):
    bundle, _ = _write_bundle_policy(
        tmp_path,
        applications=() if malformation == "empty_applications" else ("embedagent.generic",),
        manifest_hash="f" * 64 if malformation == "bad_hash" else None,
    )
    if malformation == "missing_plan":
        (bundle / "manifests" / "bundle-plan.json").unlink()

    with pytest.raises(ValueError, match="bundle"):
        load_bundle_policy(str(bundle))


def test_current_policy_discovers_launcher_bundle_from_environment(tmp_path, monkeypatch):
    bundle, _ = _write_bundle_policy(tmp_path)
    monkeypatch.setenv("EMBEDAGENT_BUNDLE_ROOT", str(bundle))

    policy = load_current_bundle_policy(__file__)

    assert policy.bundled is True
    assert policy.flavor_id == "minimal-cli"
