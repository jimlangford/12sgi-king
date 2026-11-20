"""Fail-closed PUBLIC release and source-backup contracts."""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import public_build_hygiene as hygiene  # noqa: E402

spec = importlib.util.spec_from_file_location("public_release", TOOLS / "public_release.py")
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)
SHA = "a" * 40


def build(path):
    path.mkdir()
    (path / "index.html").write_text("<html><main>Public education</main></html>")
    (path / "buildinfo.json").write_text(json.dumps({
        "lanes": [{"lane": "test", "ok": True}], "lanes_failed": [],
    }))
    return path


def receipt():
    stages = [
        {"stage": name, "exit_code": 0, "errors": [], "commands": [{"exit_code": 0}]}
        for name in release.validation.STAGES
    ]
    stages[-2]["coverage"] = {"html_pages": 1}
    stages[-1]["coverage"] = {"pages_scanned": 1, "scan_errors": 0, "shard": "all"}
    return {
        "local_validation": "passed", "git": {"commit": SHA, "dirty": False},
        "selected_stages": list(release.validation.STAGES), "stages": stages,
    }


def test_export_only_public_and_omits_build_metadata(tmp_path):
    hashes = release.export_public(build(tmp_path / "site"), tmp_path / "export", SHA)
    assert set(hashes) == {"index.html", "buildinfo.json"}
    marker = json.loads((tmp_path / "export/buildinfo.json").read_text())
    assert marker["sha"] == SHA
    assert set(marker) == {"sha", "sha_short", "validated_at"}


@pytest.mark.parametrize("name", [
    "go/ops.html", "king/go/index.html", "king/a.dc.html", ".env",
    ".git/config", "receipt.json", "models/model.gguf", "x.db",
    "x.log", "owner_jobs.html", "king_private_src/data.pdf",
])
def test_export_rejects_private_paths(tmp_path, name):
    site = build(tmp_path / "site")
    bad = site / name
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text("private")
    with pytest.raises(release.ReleaseError):
        release.export_public(site, tmp_path / "export", SHA)


@pytest.mark.parametrize("text", [
    "PRIVATE: owner runtime", "Tailscale-only", "owner ops board",
    "https://private.tail123.ts.net/", r"C:\Users\Owner\file", "/home/owner/private",
])
def test_export_rejects_private_content(tmp_path, text):
    site = build(tmp_path / "site")
    (site / "leak.js").write_text(text)
    with pytest.raises(release.ReleaseError):
        release.export_public(site, tmp_path / "export", SHA)


def test_symlinks_and_hardlinks_rejected(tmp_path):
    site = build(tmp_path / "site")
    (site / "linked.html").symlink_to(site / "index.html")
    with pytest.raises(release.ReleaseError):
        release.export_public(site, tmp_path / "export", SHA)
    (site / "linked.html").unlink()
    os.link(site / "index.html", site / "linked.html")
    with pytest.raises(release.ReleaseError):
        release.export_public(site, tmp_path / "export", SHA)


def test_lock_excludes_overlap_and_cleans_up(tmp_path):
    with release.release_lock(tmp_path):
        with pytest.raises(release.ReleaseError):
            with release.release_lock(tmp_path):
                pytest.fail("overlap")
    assert not (tmp_path / "release.lock").exists()


def test_atomic_promotion_failure_and_rollback(tmp_path):
    old, new = tmp_path / "old", tmp_path / "new"
    for path in (old, new):
        (path / "public").mkdir(parents=True)
    release.promote(tmp_path, old)
    with mock.patch.object(release.os, "replace", side_effect=OSError):
        with pytest.raises(OSError):
            release.promote(tmp_path, new)
    assert (tmp_path / "current").resolve() == old / "public"
    release.promote(tmp_path, new)
    release.promote(tmp_path, old)
    assert (tmp_path / "current").resolve() == old / "public"


def test_manifest_detects_tampering(tmp_path):
    site = build(tmp_path / "site")
    release.export_public(site, tmp_path / "public", SHA)
    public = tmp_path / "public"
    (tmp_path / "manifest.json").write_text(json.dumps({
        "commit": SHA, "files": release.file_hashes(public),
    }))
    release.verify_release(tmp_path, SHA)
    (public / "index.html").write_text("changed")
    with pytest.raises(release.ReleaseError):
        release.verify_release(tmp_path, SHA)


@pytest.mark.parametrize("mutation", [
    "stage", "shard", "commit", "dirty", "command", "pages", "status",
])
def test_supplied_or_incomplete_validation_evidence_rejected(tmp_path, mutation):
    data = receipt()
    if mutation == "stage":
        data["stages"].pop(0)
    elif mutation == "shard":
        data["stages"][-1]["coverage"]["shard"] = "1/4"
    elif mutation == "commit":
        data["git"]["commit"] = "b" * 40
    elif mutation == "dirty":
        data["git"]["dirty"] = True
    elif mutation == "command":
        data["stages"][0]["commands"][0]["exit_code"] = 1
    elif mutation == "pages":
        data["stages"][-1]["coverage"]["pages_scanned"] = 2
    else:
        data["local_validation"] = "failed"
    run = tmp_path / "state/work/id/validation"
    evidence = run / "run-test"
    evidence.mkdir(parents=True)
    (evidence / "receipt.json").write_text(json.dumps(data))
    with mock.patch.object(release.validation, "execute") as process:
        process.return_value = {"exit_code": 0}
        with pytest.raises(release.ReleaseError):
            release.validate(tmp_path, run, "base", SHA)
        command = process.call_args.args[0]
        assert "--stage" not in command and "--shard" not in command
        process.assert_called_once()


def test_validation_requires_fresh_process_success(tmp_path):
    run = tmp_path / "state/work/id/validation"
    evidence = run / "run-test"
    evidence.mkdir(parents=True)
    (evidence / "receipt.json").write_text(json.dumps(receipt()))
    with mock.patch.object(release.validation, "execute") as process:
        process.return_value = {"exit_code": 1}
        with pytest.raises(release.ReleaseError):
            release.validate(tmp_path, run, "base", SHA)
        assert process.call_args.args[-1] == 3900


def test_export_secret_scanner_failure_is_blocking(tmp_path):
    with mock.patch.object(release.validation, "execute") as process:
        process.return_value = {"exit_code": 1}
        with pytest.raises(release.ReleaseError):
            release.scan_export(tmp_path, tmp_path, tmp_path)
        assert process.call_args.args[-1] == 600


@pytest.mark.parametrize("url", [
    "http://localhost:1234/owner/repo", "https://github.com/other/repo.git",
    "https://credential@github.com/owner/repo.git",
])
def test_origin_identity_rejected_before_network(tmp_path, url):
    with mock.patch.object(release, "git", return_value=url):
        with pytest.raises(release.ReleaseError):
            release.origin_url(tmp_path, "owner/repo")


def test_history_scan_failure_prevents_all_network(tmp_path):
    with mock.patch.object(release.validation, "execute") as process, \
            mock.patch.object(release, "git") as git:
        process.return_value = {"exit_code": 1}
        with pytest.raises(release.ReleaseError):
            release.sync_source(tmp_path, tmp_path, "owner/repo", "main", SHA, "hash", tmp_path)
        git.assert_not_called()
        assert process.call_args.args[-1] == 600


def test_divergence_prevents_push(tmp_path):
    def git(root, *args):
        if args[0] == "branch":
            return "main"
        if args[0] == "ls-remote":
            return f"{'b' * 40}\trefs/heads/main"
        if args[0] == "merge-base":
            raise release.ReleaseError("divergent")
        return ""
    with mock.patch.object(release.validation, "execute") as process, \
            mock.patch.object(release, "origin_url", return_value="https://github.com/owner/repo"), \
            mock.patch.object(release, "clean_source", return_value="hash"), \
            mock.patch.object(release, "git", side_effect=git) as calls:
        process.return_value = {"exit_code": 0}
        with pytest.raises(release.ReleaseError):
            release.sync_source(tmp_path, tmp_path, "owner/repo", "main", SHA, "hash", tmp_path)
        assert not any(call.args[1] == "push" for call in calls.call_args_list)


def test_cname_never_exports(tmp_path):
    site = build(tmp_path / "site")
    (site / "CNAME").write_text("primary.example.com")
    release.export_public(site, tmp_path / "export", SHA)
    assert not (tmp_path / "export/CNAME").exists()


def test_unowned_state_permissions_unchanged(tmp_path):
    state = tmp_path / "shared"
    state.mkdir(mode=0o755)
    before = state.stat().st_mode
    with pytest.raises(release.ReleaseError):
        release.managed_state(state)
    assert state.stat().st_mode == before
    assert list(state.iterdir()) == []


@pytest.mark.parametrize("name", ["work", "releases", "browser", "latest.json"])
def test_managed_paths_refuse_symlinks(tmp_path, name):
    state = release.managed_state(tmp_path / "state")
    (state / name).symlink_to(tmp_path / "unrelated")
    with pytest.raises(release.ReleaseError):
        release.managed_state(state)


def test_unowned_current_is_not_replaced(tmp_path):
    state = release.managed_state(tmp_path / "state")
    (state / "current").symlink_to(tmp_path / "primary")
    with pytest.raises(release.ReleaseError):
        release.check_current(state)
    assert (state / "current").is_symlink()


@pytest.mark.parametrize("settings", [
    {"cname": "primary.example.com", "html_url": "https://owner.github.io/repo/",
     "build_type": "workflow"},
    {"cname": None, "html_url": "https://other.example.com/", "build_type": "workflow"},
    {"cname": None, "html_url": "https://owner.github.io/repo/", "build_type": "legacy"},
])
def test_pages_refuses_primary_or_unknown_hosting(settings):
    with mock.patch.object(release.urllib.request, "urlopen") as fetch:
        fetch.return_value.__enter__.return_value.read.return_value = json.dumps(settings)
        with pytest.raises(release.ReleaseError):
            release.check_pages("owner/repo", "https://owner.github.io/repo/", "test-token")


def test_pages_read_only_preflight_success():
    settings = {
        "cname": None, "html_url": "https://owner.github.io/repo/", "build_type": "workflow",
    }
    with mock.patch.object(release.urllib.request, "urlopen") as fetch:
        fetch.return_value.__enter__.return_value.read.return_value = json.dumps(settings)
        release.check_pages("owner/repo", settings["html_url"], "test-token")
        request = fetch.call_args.args[0]
        assert request.get_method() == "GET"
        assert request.get_header("Authorization").endswith("test-token")


def test_once_idempotent_backup_failure_does_not_undo_local(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    state = tmp_path / "state"
    args = SimpleNamespace(
        state=state, expected_sha=SHA, rollback=False, base="base",
        package_only=False, sync_source=True, repository="owner/repo", branch="main",
    )
    monkeypatch.setattr(release, "ROOT", root)
    monkeypatch.setattr(release, "clean_source", lambda *args: "fingerprint")
    monkeypatch.setattr(release, "check_base", lambda *args: None)
    monkeypatch.setattr(release, "scan_export", lambda *args: None)
    monkeypatch.setattr(release, "sync_source", mock.Mock(side_effect=OSError))

    def git(root, *args):
        assert args[0] == "worktree"
        if args[1] == "add":
            Path(args[-2]).mkdir()
        else:
            shutil.rmtree(args[-1])
        return ""

    monkeypatch.setattr(release, "git", mock.Mock(side_effect=git))

    def validate(source, run, base, sha):
        return build(source.parent / "built")

    validator = mock.Mock(side_effect=validate)
    monkeypatch.setattr(release, "validate", validator)
    assert release.run(args) == 2
    assert (state / "current").resolve() == state / "releases" / SHA / "public"
    status = json.loads((state / "latest.json").read_text())
    assert status["local_promotion"] == "passed"
    assert status["source_backup"] == "failed"
    assert release.run(args) == 2
    validator.assert_called_once()
    assert not (state / "release.lock").exists()
    assert not list((state / "work").glob("*/source"))


def test_source_modification_blocks_promotion(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    state = release.managed_state(tmp_path / "state")
    work = state / "work"
    work.mkdir()
    snapshot = work / "source"
    snapshot.mkdir()
    site = build(work / "site")
    args = SimpleNamespace(
        expected_sha=SHA, base="base", package_only=False, sync_source=False,
    )
    monkeypatch.setattr(release, "ROOT", root)
    monkeypatch.setattr(release, "validate", lambda *args: site)
    monkeypatch.setattr(release, "clean_source", mock.Mock(side_effect=["old", "new"]))
    with pytest.raises(release.ReleaseError):
        release.prepare_release(
            args, state, state / "releases" / SHA, "old", work, snapshot, {},
        )
    assert not (state / "current").exists()


@pytest.mark.parametrize("command", ["push", "worktree"])
def test_git_timeout_stops_tree_and_preserves_push_hooks(tmp_path, command):
    with mock.patch.object(release.subprocess, "Popen") as popen, \
            mock.patch.object(release.validation, "terminate_tree") as stop:
        process = popen.return_value
        process.communicate.side_effect = subprocess.TimeoutExpired("git", 120)
        with pytest.raises(release.ReleaseError):
            release.git(tmp_path, command, "origin")
        stop.assert_called_once_with(process)
        argv = popen.call_args.args[0]
        assert ("core.hooksPath=/dev/null" in argv) == (command == "worktree")
        assert popen.call_args.kwargs["env"]["GIT_TERMINAL_PROMPT"] == "0"


def test_same_sha_lint_base_is_rejected(tmp_path):
    with mock.patch.object(release, "git") as git:
        with pytest.raises(release.ReleaseError):
            release.check_base(tmp_path, SHA, SHA)
        git.assert_not_called()


@pytest.mark.parametrize("kind", ["descendant", "unrelated", "missing"])
def test_nonancestor_lint_base_is_rejected(tmp_path, kind):
    base = "b" * 40
    with mock.patch.object(release, "git") as git:
        git.side_effect = (
            release.ReleaseError("missing") if kind == "missing"
            else [base, release.ReleaseError("not ancestor")]
        )
        with pytest.raises(release.ReleaseError):
            release.check_base(tmp_path, base, SHA)


def test_prior_ancestor_lint_base_is_accepted(tmp_path):
    base = "b" * 40
    with mock.patch.object(release, "git", side_effect=[base, ""]) as git:
        release.check_base(tmp_path, base, SHA)
        assert git.call_args.args[1:] == ("merge-base", "--is-ancestor", base, SHA)


def test_state_parent_symlinks_and_dotdot_refused(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "alias"
    link.symlink_to(real, target_is_directory=True)
    for path in (link / "state", real / ".." / "state"):
        with pytest.raises(release.ReleaseError):
            release.managed_state(path)
    assert not (real / "state").exists()
    assert not (tmp_path / "state").exists()


def test_origin_without_url_rewrites_is_supported(tmp_path):
    url = "https://github.com/owner/repo.git"
    with mock.patch.object(release, "git", side_effect=[url, url]), \
            mock.patch.object(release.subprocess, "run") as process:
        process.return_value.returncode = 1
        assert release.origin_url(tmp_path, "owner/repo") == url


def test_complete_full_validation_evidence_accepted(tmp_path):
    run = tmp_path / "state/work/id/validation"
    evidence = run / "run-test"
    evidence.mkdir(parents=True)
    (evidence / "receipt.json").write_text(json.dumps(receipt()))
    with mock.patch.object(release.validation, "execute", return_value={"exit_code": 0}):
        assert release.validate(tmp_path, run, "base", SHA) == evidence / "a11y/site"


def test_public_build_hygiene_preserves_sources_and_private_mirror(tmp_path):
    source, public, private = [tmp_path / name for name in ("source", "site", "king-local")]
    names = (
        "sage/js/engine_check.py", "king/charter-explainer.html.bak", "sage/no-reopen",
        "king/cache.pyc", "king/cache.pyo", "index.html", "king/corpus/record.md",
        "king/gis/public.geojson", "games/play.mjs",
    )
    for root in (source, public, private):
        for name in names:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("unchanged")
    assert hygiene.purge_build_artifacts(public) == sorted(names[:5])
    for name in names:
        assert (source / name).read_text() == "unchanged"
        assert (private / name).read_text() == "unchanged"
        assert (public / name).exists() == (name not in names[:5])
    assert hygiene.purge_build_artifacts(public) == []


@pytest.mark.parametrize("suffix", [".mjs", ".geojson", ".md"])
def test_reviewed_static_asset_types_still_enforce_privacy(tmp_path, suffix):
    site = build(tmp_path / "site")
    (site / ("public" + suffix)).write_text("public educational asset")
    release.export_public(site, tmp_path / "export", SHA)
    (site / ("private" + suffix)).write_text("PRIVATE: owner data")
    with pytest.raises(release.ReleaseError):
        release.export_public(site, tmp_path / "rejected", SHA)


def test_isolated_build_hygiene_precedes_validation_of_public_tree(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    site = run / "a11y/site"
    site.parent.mkdir()
    build(site)
    (site / "copied.py").write_text("implementation")
    (site / "index.html.bak").write_text("backup")
    before = (site / "index.html").read_bytes()
    original = release.validation.check_build

    def check(directory):
        assert not (directory / "copied.py").exists()
        assert not (directory / "index.html.bak").exists()
        assert (directory / "index.html").read_bytes() == before
        return original(directory)

    with mock.patch.object(release.validation, "execute", return_value={"exit_code": 0}), \
            mock.patch.object(release.validation, "check_build", side_effect=check):
        result = release.validation.stage("build", run, None, False)
    assert result["exit_code"] == 0
    assert result["removed_build_artifacts"] == ["copied.py", "index.html.bak"]


def test_backup_verifies_only_known_https_marker_and_writes_public_summary(tmp_path):
    url = "https://owner.github.io/repo/"
    summary = tmp_path / "summary"
    with mock.patch.object(release.urllib.request, "build_opener") as build_opener, \
            mock.patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(summary)}):
        opener = build_opener.return_value
        opener.open.return_value.__enter__.return_value.read.return_value = json.dumps({
            "sha": SHA,
        }).encode()
        assert release.main([
            "--verify-backup", "--repository", "owner/repo", "--backup-url", url,
            "--expected-sha", SHA,
        ]) == 0
        request = opener.open.call_args.args[0]
        assert request.full_url == url + "buildinfo.json"
        assert opener.open.call_args.kwargs["timeout"] == 10
        assert request.get_header("Authorization") is None
        assert isinstance(build_opener.call_args.args[0], release.NoRedirect)
    text = summary.read_text()
    assert url in text and SHA in text and "Verified at:" in text
    assert "PRIVATE" not in text


def test_backup_stale_marker_retries_bounded_and_reports_failure(tmp_path):
    summary = tmp_path / "summary"
    with mock.patch.object(release.urllib.request, "build_opener") as build_opener, \
            mock.patch.object(release.time, "sleep") as sleep, \
            mock.patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(summary)}):
        opener = build_opener.return_value
        opener.open.return_value.__enter__.return_value.read.return_value = b'{"sha":"stale"}'
        assert release.main([
            "--verify-backup", "--repository", "owner/repo",
            "--backup-url", "https://owner.github.io/repo/", "--expected-sha", SHA,
        ]) == 1
        assert opener.open.call_count == 3
        assert sleep.call_count == 2
    assert "FAILED" in summary.read_text()
    assert "no rollback was attempted" in summary.read_text()


def test_backup_refuses_unapproved_url_without_network():
    with mock.patch.object(release.urllib.request, "build_opener") as opener:
        with pytest.raises(release.ReleaseError):
            release.verify_backup("owner/repo", "https://primary.example.com/", SHA)
        opener.assert_not_called()
    assert release.NoRedirect().redirect_request(None, None, 302, "", {}, "https://other/") is None


def test_deploy_job_rechecks_owner_approval_before_publication():
    workflow = (TOOLS.parent / ".github/workflows/public-static-backup.yml").read_text()
    deploy = workflow.split("\n  deploy:\n", 1)[1]
    guard = deploy.split("    environment:", 1)[0]
    assert "vars.PUBLIC_BACKUP_ENABLED == 'true'" in guard
    assert "vars.PUBLIC_BACKUP_APPROVED_SHA == github.sha" in guard
    assert "    permissions:\n      contents: read\n      pages: write" in deploy
