"""Deterministic, fail-closed daily showcase updater.

Private source paths and release decisions live only in an out-of-repository
policy file. This program never generates prose from private files; it emits
only curator-approved text whose evidence is hash-bound to the current verified
local baseline. Publishing is disabled unless a separate owner-approved local
policy explicitly enables it.
"""
from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
SAFE_OUTPUTS = {"docs/development-log.md", "docs/status-and-roadmap.md"}
SAFE_CATEGORIES = {"offline_knowledge", "local_engineering", "evaluation"}
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,79}$")
SHA_RE = re.compile(r"^[a-f0-9]{64}$")
MODULE_RE = re.compile(r"^[a-z_][a-z0-9_.]*$")
FORBIDDEN = [
    re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}", re.I),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\b(?:password|passwd|api[_ -]?key)\s*[:=]\s*\S+", re.I),
    re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
    re.compile(r"(?<![\w])(?:\d{1,3}\.){3}\d{1,3}(?![\w])"),
    re.compile(r"(?<![\w])/(?:Users|home|private|Volumes)/[^\s`]+"),
    re.compile(r"\b[A-Za-z]:\\(?:Users|home)\\[^\s`]+", re.I),
    re.compile(r"\b[A-Fa-f0-9]{64}\b"),
    re.compile(r"\bhidden\s+(?:code|message|answer|story)\b", re.I),
]
STATUS_START = "<!-- curated-status:start -->"
STATUS_END = "<!-- curated-status:end -->"


class UpdateError(RuntimeError):
    pass


def safe_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 1600:
        raise UpdateError(f"PUBLIC_TEXT_INVALID:{field}")
    if "http://" in value.lower() or "https://" in value.lower():
        raise UpdateError(f"PUBLIC_LINK_REQUIRES_REVIEW:{field}")
    if any(p.search(value) for p in FORBIDDEN):
        raise UpdateError(f"PUBLIC_TEXT_REJECTED:{field}")
    return value.strip()


def safe_relative(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise UpdateError(f"LOCAL_PATH_INVALID:{field}")
    p = PurePosixPath(value)
    if p.is_absolute() or any(x in ("", ".", "..") for x in p.parts):
        raise UpdateError(f"LOCAL_PATH_INVALID:{field}")
    return p.as_posix()


def secure_file(root: Path, rel: str, *, max_bytes: int = 64 * 1024 * 1024) -> Path:
    cursor = root
    for part in PurePosixPath(rel).parts:
        cursor = cursor / part
        try:
            st = cursor.lstat()
        except OSError:
            raise UpdateError("LOCAL_INPUT_MISSING") from None
        if cursor.is_symlink():
            raise UpdateError("LOCAL_SYMLINK_REJECTED")
    if not cursor.is_file() or cursor.stat().st_size > max_bytes:
        raise UpdateError("LOCAL_INPUT_NOT_REGULAR_OR_TOO_LARGE")
    try:
        cursor.resolve(strict=True).relative_to(root.resolve(strict=True))
    except (OSError, ValueError):
        raise UpdateError("LOCAL_INPUT_OUTSIDE_ROOT") from None
    return cursor


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_policy(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise UpdateError("LOCAL_POLICY_NOT_REGULAR_FILE")
    try:
        policy = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        raise UpdateError("LOCAL_POLICY_INVALID") from None
    required = {"schema", "source_root", "manifest_search_dir", "manifest_filename_pattern", "verifier_module", "verifier_function", "audit_path", "publishing_enabled", "expected_remote", "approved_public_entries"}
    allowed = required | {"allow_local_remote_for_tests"}
    if not isinstance(policy, dict) or policy.get("schema") != "gnognote0.showcase.local-policy.v1" or not required.issubset(policy) or not set(policy).issubset(allowed):
        raise UpdateError("LOCAL_POLICY_SCHEMA_INVALID")
    if not isinstance(policy["publishing_enabled"], bool) or policy["expected_remote"] != "https://github.com/n1416y/gnognote0-showcase.git":
        raise UpdateError("LOCAL_POLICY_AUTHORITY_INVALID")
    if Path(path).expanduser().resolve().is_relative_to(ROOT.resolve()):
        raise UpdateError("LOCAL_POLICY_MUST_REMAIN_OUTSIDE_SHOWCASE")
    return policy


def find_latest_manifest(policy: dict[str, Any]) -> tuple[Path, str]:
    source = Path(policy.get("source_root", "")).expanduser().resolve(strict=True)
    if not source.is_dir():
        raise UpdateError("SOURCE_ROOT_INVALID")
    rel_dir = safe_relative(policy.get("manifest_search_dir"), "manifest_search_dir")
    manifest_dir = source
    for part in PurePosixPath(rel_dir).parts:
        manifest_dir = manifest_dir / part
        if manifest_dir.is_symlink():
            raise UpdateError("MANIFEST_DIRECTORY_SYMLINK")
    manifest_dir = manifest_dir.resolve(strict=True)
    try:
        manifest_dir.relative_to(source)
    except ValueError:
        raise UpdateError("MANIFEST_DIRECTORY_OUTSIDE_SOURCE") from None
    if manifest_dir.is_symlink() or not manifest_dir.is_dir():
        raise UpdateError("MANIFEST_DIRECTORY_INVALID")
    pattern_text = policy.get("manifest_filename_pattern")
    try:
        pattern = re.compile(pattern_text)
    except (TypeError, re.error):
        raise UpdateError("MANIFEST_PATTERN_INVALID") from None
    matches: list[tuple[int, Path]] = []
    for item in manifest_dir.iterdir():
        m = pattern.fullmatch(item.name)
        if m:
            try:
                number = int(m.group("number"))
            except (IndexError, ValueError):
                raise UpdateError("MANIFEST_PATTERN_MUST_CAPTURE_NUMBER") from None
            matches.append((number, item))
    if not matches:
        raise UpdateError("LATEST_MANIFEST_NOT_FOUND")
    matches.sort(key=lambda item: item[0])
    latest = matches[-1][1]
    if latest.is_symlink() or not latest.is_file():
        raise UpdateError("LATEST_MANIFEST_NOT_REGULAR_FILE")
    return source, latest.relative_to(source).as_posix()


def run_baseline_verifier(policy: dict[str, Any]) -> tuple[dict[str, Any], Path, str]:
    source, manifest_rel = find_latest_manifest(policy)
    manifest_path = secure_file(source, manifest_rel, max_bytes=32 * 1024 * 1024)
    manifest_digest = sha256(manifest_path)
    module = policy.get("verifier_module")
    function = policy.get("verifier_function", "verify_manifest")
    if not isinstance(module, str) or not MODULE_RE.fullmatch(module) or function != "verify_manifest":
        raise UpdateError("VERIFIER_TARGET_INVALID")
    py = source / ".venv" / "bin" / "python"
    interpreter = str(py) if py.is_file() and os.access(py, os.X_OK) else sys.executable
    code = (
        "import json,sys; "
        f"m=__import__({module!r},fromlist=['verify_manifest']); "
        "r=m.verify_manifest(sys.argv[1],root=sys.argv[2]); "
        "print(json.dumps(r,separators=(',',':')))"
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(source) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    try:
        result = subprocess.run(
            [interpreter, "-c", code, manifest_rel, str(source)], cwd=source,
            env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, timeout=180, check=False,
        )
    except Exception:
        raise UpdateError("BASELINE_VERIFIER_FAILED") from None
    if result.returncode != 0:
        raise UpdateError("BASELINE_VERIFIER_FAILED")
    try:
        verified = json.loads(result.stdout)
    except Exception:
        raise UpdateError("BASELINE_VERIFIER_OUTPUT_INVALID") from None
    if not isinstance(verified, dict):
        raise UpdateError("BASELINE_VERIFIER_OUTPUT_INVALID")
    expected = ("PASS_LOCAL_MANIFEST", manifest_digest, "STOP", "NOT_GRANTED")
    observed = (
        verified.get("status"), verified.get("manifest_sha256"),
        verified.get("readiness"), verified.get("execution_authority"),
    )
    if observed != expected:
        raise UpdateError("BASELINE_VERIFICATION_OR_AUTHORITY_STOP")
    source_again, rel_again = find_latest_manifest(policy)
    if source_again != source or rel_again != manifest_rel or sha256(secure_file(source_again, rel_again, max_bytes=32 * 1024 * 1024)) != manifest_digest:
        raise UpdateError("BASELINE_CHANGED_DURING_VERIFICATION")
    return verified, source, manifest_rel


def recursively_bound(doc: Any, rel: str, digest: str) -> bool:
    if isinstance(doc, dict):
        if doc.get("path") == rel and doc.get("sha256") == digest and doc.get("copy_in_candidate") is not False:
            return True
        return any(recursively_bound(v, rel, digest) for v in doc.values())
    if isinstance(doc, list):
        return any(recursively_bound(v, rel, digest) for v in doc)
    return False


def validate_entry(entry: Any) -> dict[str, str]:
    required = {"id", "evidence_path", "evidence_sha256", "date", "category", "headline", "summary"}
    if not isinstance(entry, dict) or not required.issubset(entry):
        raise UpdateError("APPROVED_ENTRY_SCHEMA_INVALID")
    event_id = entry["id"]
    if not isinstance(event_id, str) or not ID_RE.fullmatch(event_id):
        raise UpdateError("APPROVED_ENTRY_ID_INVALID")
    path = safe_relative(entry["evidence_path"], "evidence_path")
    digest = entry["evidence_sha256"]
    if not isinstance(digest, str) or not SHA_RE.fullmatch(digest):
        raise UpdateError("APPROVED_ENTRY_HASH_INVALID")
    try:
        dt.date.fromisoformat(entry["date"])
    except (TypeError, ValueError):
        raise UpdateError("APPROVED_ENTRY_DATE_INVALID") from None
    if entry["category"] not in SAFE_CATEGORIES:
        raise UpdateError("APPROVED_ENTRY_CATEGORY_NOT_ALLOWED")
    result = {
        "id": event_id,
        "evidence_path": path,
        "evidence_sha256": digest,
        "date": entry["date"],
        "category": entry["category"],
        "headline": safe_text(entry["headline"], "headline"),
        "summary": safe_text(entry["summary"], "summary"),
    }
    if entry.get("status_summary"):
        result["status_summary"] = safe_text(entry["status_summary"], "status_summary")
    return result


def eligible_entries(policy: dict[str, Any], source: Path, manifest_rel: str, expected_manifest_sha256: str | None = None) -> list[dict[str, str]]:
    manifest_path = secure_file(source, manifest_rel, max_bytes=32 * 1024 * 1024)
    if expected_manifest_sha256 is not None and sha256(manifest_path) != expected_manifest_sha256:
        raise UpdateError("BASELINE_CHANGED_AFTER_VERIFICATION")
    try:
        manifest_doc = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        raise UpdateError("VERIFIED_MANIFEST_DOCUMENT_INVALID") from None
    raw = policy.get("approved_public_entries", [])
    if not isinstance(raw, list):
        raise UpdateError("APPROVED_ENTRIES_INVALID")
    out: list[dict[str, str]] = []
    for item in raw:
        entry = validate_entry(item)
        evidence = secure_file(source, entry["evidence_path"])
        if sha256(evidence) != entry["evidence_sha256"]:
            raise UpdateError("APPROVED_EVIDENCE_HASH_MISMATCH")
        if recursively_bound(manifest_doc, entry["evidence_path"], entry["evidence_sha256"]):
            out.append(entry)
    return sorted(out, key=lambda row: (row["date"], row["id"]))


def render_entry(entry: dict[str, str]) -> str:
    return (
        f"\n<!-- showcase-update:{entry['id']} -->\n\n"
        f"## {entry['date']} — {entry['headline']}\n\n"
        f"{entry['summary']}\n"
    )


def safe_repo_path(repo: Path, rel: str) -> Path:
    if rel not in SAFE_OUTPUTS:
        raise UpdateError("OUTPUT_PATH_NOT_ALLOWLISTED")
    p = repo / rel
    if p.is_symlink() or not p.is_file():
        raise UpdateError("OUTPUT_PATH_NOT_REGULAR_FILE")
    try:
        p.resolve(strict=True).relative_to(repo.resolve(strict=True))
    except ValueError:
        raise UpdateError("OUTPUT_PATH_OUTSIDE_REPOSITORY") from None
    return p


def atomic_write(path: Path, content: str) -> None:
    fd, temp_name = tempfile.mkstemp(prefix=".showcase-update-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_name, path)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass


def append_log(repo: Path, entries: list[dict[str, str]]) -> list[str]:
    path = safe_repo_path(repo, "docs/development-log.md")
    current = path.read_text(encoding="utf-8")
    added: list[str] = []
    for entry in entries:
        marker = f"<!-- showcase-update:{entry['id']} -->"
        if marker in current:
            continue
        current += render_entry(entry)
        added.append(entry["id"])
    if added:
        atomic_write(path, current)
    return added


def update_status(repo: Path, entries: list[dict[str, str]]) -> bool:
    chosen = next((e for e in reversed(entries) if e.get("status_summary")), None)
    if not chosen:
        return False
    path = safe_repo_path(repo, "docs/status-and-roadmap.md")
    text = path.read_text(encoding="utf-8")
    if text.count(STATUS_START) != 1 or text.count(STATUS_END) != 1:
        raise UpdateError("STATUS_MARKERS_INVALID")
    start = text.index(STATUS_START) + len(STATUS_START)
    end = text.index(STATUS_END)
    replacement = f"\n\n**Latest verified local update:** {chosen['status_summary']}\n\n"
    if text[start:end] == replacement:
        return False
    atomic_write(path, text[:start] + replacement + text[end:])
    return True


def run_git(repo: Path, args: list[str], *, timeout: int = 45) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(["git", *args], cwd=repo, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, timeout=timeout, check=False)
    except Exception:
        raise UpdateError("GIT_OPERATION_FAILED") from None


def remote_ok(repo: Path, policy: dict[str, Any], *, test_mode: bool = False) -> bool:
    result = run_git(repo, ["remote", "get-url", "origin"])
    if result.returncode != 0:
        return False
    remote = result.stdout.strip()
    if remote == policy.get("expected_remote"):
        return True
    return bool(test_mode and policy.get("allow_local_remote_for_tests") is True and remote.startswith("file://"))


def ensure_clean_except_outputs(repo: Path) -> None:
    result = run_git(repo, ["status", "--porcelain", "--untracked-files=all"])
    if result.returncode != 0:
        raise UpdateError("GIT_STATUS_FAILED")
    for line in result.stdout.splitlines():
        path = line[3:] if len(line) >= 4 else ""
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if path not in SAFE_OUTPUTS:
            raise UpdateError("UNEXPECTED_REPOSITORY_CHANGE")


def commit_allowed_changes(repo: Path, entries: list[dict[str, str]]) -> bool:
    ensure_clean_except_outputs(repo)
    changed = run_git(repo, ["status", "--porcelain", "--untracked-files=all"])
    if not changed.stdout.strip():
        return False
    for output in SAFE_OUTPUTS:
        run_git(repo, ["add", "--", output])
    staged = run_git(repo, ["diff", "--cached", "--name-only"])
    names = {line.strip() for line in staged.stdout.splitlines() if line.strip()}
    if not names or not names.issubset(SAFE_OUTPUTS):
        raise UpdateError("STAGED_PATH_NOT_ALLOWLISTED")
    diffcheck = run_git(repo, ["diff", "--cached", "--check"])
    if diffcheck.returncode != 0:
        raise UpdateError("GIT_DIFF_CHECK_FAILED")
    ids = ",".join(e["id"] for e in entries) or "curated-status"
    result = run_git(repo, ["commit", "-m", f"Publish curated development update: {ids[:72]}"])
    if result.returncode != 0:
        raise UpdateError("GIT_COMMIT_FAILED")
    return True


def push_only_allowlisted_ahead(repo: Path, policy: dict[str, Any], *, test_mode: bool = False) -> str:
    if not remote_ok(repo, policy, test_mode=test_mode):
        raise UpdateError("REMOTE_NOT_ALLOWLISTED")
    ensure_clean_except_outputs(repo)
    branch = run_git(repo, ["branch", "--show-current"])
    if branch.returncode != 0 or branch.stdout.strip() != "main":
        raise UpdateError("BRANCH_NOT_ALLOWLISTED")
    fetch = run_git(repo, ["fetch", "--quiet", "origin", "main"], timeout=90)
    if fetch.returncode != 0:
        raise UpdateError("REMOTE_FETCH_FAILED")
    diff = run_git(repo, ["diff", "--name-only", "origin/main...HEAD"])
    if diff.returncode != 0:
        raise UpdateError("REMOTE_DIVERGENCE")
    names = {line.strip() for line in diff.stdout.splitlines() if line.strip()}
    if not names:
        return "ALREADY_SYNCED"
    if not names.issubset(SAFE_OUTPUTS):
        raise UpdateError("AHEAD_COMMIT_PATH_NOT_ALLOWLISTED")
    push = run_git(repo, ["push", "origin", "HEAD:main"], timeout=120)
    if push.returncode != 0:
        raise UpdateError("REMOTE_PUSH_FAILED")
    head = run_git(repo, ["rev-parse", "HEAD"])
    if head.returncode != 0:
        raise UpdateError("LOCAL_HEAD_UNAVAILABLE")
    return head.stdout.strip()


def audit_append(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.parent.stat().st_mode & 0o077:
        raise UpdateError("AUDIT_DIRECTORY_PERMISSIONS_TOO_OPEN")
    if path.is_symlink():
        raise UpdateError("AUDIT_PATH_SYMLINK")
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    try:
        if os.fstat(fd).st_mode & 0o077:
            raise UpdateError("AUDIT_FILE_PERMISSIONS_TOO_OPEN")
        fcntl.flock(fd, fcntl.LOCK_EX)
        raw = (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode()
        os.write(fd, raw)
        os.fsync(fd)
    finally:
        os.close(fd)


def git_file(repo: Path, rel: str) -> str:
    result = run_git(repo, ["show", f"HEAD:{rel}"])
    if result.returncode != 0:
        raise UpdateError("GIT_BASELINE_FILE_UNAVAILABLE")
    return result.stdout


def target_log(base: str, entries: list[dict[str, str]]) -> str:
    current = base
    for entry in entries:
        if f"<!-- showcase-update:{entry['id']} -->" not in current:
            current += render_entry(entry)
    return current


def target_status(base: str, entries: list[dict[str, str]]) -> str:
    chosen = next((e for e in reversed(entries) if e.get("status_summary")), None)
    if not chosen:
        return base
    if base.count(STATUS_START) != 1 or base.count(STATUS_END) != 1:
        raise UpdateError("STATUS_MARKERS_INVALID")
    start = base.index(STATUS_START) + len(STATUS_START)
    end = base.index(STATUS_END)
    replacement = f"\n\n**Latest verified local update:** {chosen['status_summary']}\n\n"
    return base[:start] + replacement + base[end:]


def execute(policy_path: Path, mode: str, *, repo_root: Path | None = None, test_mode: bool = False) -> dict[str, Any]:
    policy = load_policy(policy_path)
    verified, source, manifest_rel = run_baseline_verifier(policy)
    entries = eligible_entries(policy, source, manifest_rel, verified.get("manifest_sha256"))
    repo = (repo_root or ROOT).resolve()
    if repo.is_symlink() or not (repo / ".git").exists():
        raise UpdateError("SHOWCASE_REPOSITORY_NOT_INITIALIZED")
    baseline = {k: verified.get(k) for k in ("status", "manifest_sha256", "verified_local_bindings", "readiness", "execution_authority")}
    result: dict[str, Any] = {"mode": mode, "baseline": baseline, "pending_count": 0, "new_files": []}
    audit_value = policy.get("audit_path")
    if not isinstance(audit_value, str) or not audit_value:
        raise UpdateError("AUDIT_PATH_REQUIRED")
    audit_path = Path(audit_value).expanduser()
    audit_resolved = audit_path.parent.resolve() / audit_path.name
    if audit_resolved.is_relative_to(repo) or audit_resolved.is_relative_to(source):
        raise UpdateError("AUDIT_MUST_REMAIN_OUTSIDE_SHOWCASE_AND_SOURCE")
    now = dt.datetime.now(ZoneInfo("America/Chicago"))
    if mode == "publish" and audit_path.is_file() and not audit_path.is_symlink():
        try:
            recent = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        except Exception:
            raise UpdateError("AUDIT_LEDGER_INVALID") from None
        if any(r.get("mode") == "publish" and r.get("date_chicago") == now.date().isoformat() and r.get("status") in {"PUBLISHED", "NO_MEANINGFUL_CHANGE"} for r in recent):
            return {"mode": mode, "status": "DAILY_RUN_ALREADY_COMPLETED", "pending_count": 0, "new_files": []}

    log_path = safe_repo_path(repo, "docs/development-log.md")
    status_path = safe_repo_path(repo, "docs/status-and-roadmap.md")
    current_log = log_path.read_text(encoding="utf-8")
    current_status = status_path.read_text(encoding="utf-8")
    pending = [e for e in entries if f"<!-- showcase-update:{e['id']} -->" not in current_log]
    result["pending_count"] = len(pending)
    if pending:
        result["preview_text"] = "\n".join(render_entry(e) for e in pending)
    if mode == "prepare":
        result["status"] = "PREVIEW_ONLY" if pending else "NO_MEANINGFUL_CHANGE"
    elif not policy.get("publishing_enabled", False):
        result["status"] = "PUBLISHING_DISABLED"
    else:
        if not remote_ok(repo, policy, test_mode=test_mode):
            raise UpdateError("REMOTE_NOT_ALLOWLISTED")
        branch = run_git(repo, ["branch", "--show-current"])
        if branch.returncode != 0 or branch.stdout.strip() != "main":
            raise UpdateError("BRANCH_NOT_ALLOWLISTED")
        ensure_clean_except_outputs(repo)
        base_log = git_file(repo, "docs/development-log.md")
        base_status = git_file(repo, "docs/status-and-roadmap.md")
        desired_log = target_log(base_log, entries)
        desired_status = target_status(base_status, entries)
        if current_log not in {base_log, desired_log} or current_status not in {base_status, desired_status}:
            raise UpdateError("OUTPUT_DIFF_NOT_EXACTLY_CURATED")
        changed: list[str] = []
        if current_log != desired_log:
            atomic_write(log_path, desired_log)
            changed.append("docs/development-log.md")
        if current_status != desired_status:
            atomic_write(status_path, desired_status)
            changed.append("docs/status-and-roadmap.md")
        if changed:
            commit_allowed_changes(repo, entries)
        result["new_files"] = changed
        result["publication"] = push_only_allowlisted_ahead(repo, policy, test_mode=test_mode)
        result["status"] = "PUBLISHED" if result["publication"] != "ALREADY_SYNCED" else ("NO_MEANINGFUL_CHANGE" if not changed else "ALREADY_SYNCED")

    audit_append(audit_path, {
        "schema": "gnognote0.showcase.audit.v1",
        "mode": mode,
        "date_chicago": now.date().isoformat(),
        "timestamp_chicago": now.isoformat(timespec="seconds"),
        "status": result["status"],
        "baseline_status": baseline["status"],
        "baseline_sha256": baseline["manifest_sha256"],
        "verified_binding_count": baseline["verified_local_bindings"],
        "candidate_count": len(entries),
        "pending_count": len(pending),
        "new_files": result["new_files"],
        "publication": result.get("publication"),
    })
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--mode", choices=("prepare", "publish"), default="prepare")
    args = parser.parse_args()
    try:
        result = execute(args.config, args.mode)
    except UpdateError as exc:
        print(json.dumps({"status": "STOP", "reason": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
