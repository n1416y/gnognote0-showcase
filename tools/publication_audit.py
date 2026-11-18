"""Curated-tree, link, metadata, and local Git-history publication audit."""
from __future__ import annotations
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = {
    ".gitignore", "README.md", "linkedin-post.md",
    "docs/concept.md", "docs/architecture.md", "docs/autonomy-and-governance.md",
    "docs/g0-case-study.md", "docs/engineering-journey.md", "docs/status-and-roadmap.md",
    "docs/test-evidence-summary.md", "docs/development-log.md", "docs/daily-updates.md",
    "assets/governed-work-loop.svg", "tools/daily_update.py", "tools/publication_audit.py",
    "tests/test_daily_update.py", "config/public-update-policy.example.json",
    "schedule/com.gnognote0.showcase-update.plist.template",
}
LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
SENSITIVE = [
    re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}", re.I),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
    re.compile(r"(?<![\w])(?:\d{1,3}\.){3}\d{1,3}(?![\w])"),
    re.compile(r"(?<![\w])/(?:Users|home|private|Volumes)/[^\s`]+"),
    re.compile(r"\b[A-Za-z]:\\(?:Users|home)\\[^\s`]+", re.I),
    re.compile(r"\bhidden\s+(?:code|message|answer|story)\b", re.I),
]
ALLOWED_EXTERNAL = {"https://github.com/n1416y/gnognote0-showcase.git", "https://github.com/n1416y/gnognote0-showcase"}


def fail(code: str) -> None:
    raise SystemExit(code)


def run_git(*args: str) -> str:
    r = subprocess.run(["git", *args], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if r.returncode:
        fail("GIT_AUDIT_FAILED")
    return r.stdout


def scan_text(label: str, text: str) -> None:
    if any(pattern.search(text) for pattern in SENSITIVE):
        fail("SENSITIVE_PATTERN:" + label)
    for target in LINK.findall(text):
        target = target.strip().split()[0].strip("<>")
        if target.startswith(("https://", "http://")):
            if target not in ALLOWED_EXTERNAL:
                fail("EXTERNAL_LINK_NOT_ALLOWLISTED:" + label)
            continue
        if target.startswith("#"):
            continue
        target_path = target.split("#", 1)[0]
        if not target_path:
            continue
        resolved = (ROOT / label).parent.joinpath(target_path).resolve()
        try:
            resolved.relative_to(ROOT.resolve())
        except ValueError:
            fail("LINK_ESCAPES_REPOSITORY:" + label)
        if not resolved.is_file():
            fail("BROKEN_LOCAL_LINK:" + label)


def audit_worktree() -> list[str]:
    actual: set[str] = set()
    for p in ROOT.rglob("*"):
        if ".git" in p.relative_to(ROOT).parts:
            continue
        if p.is_symlink():
            fail("SYMLINK_NOT_ALLOWED:" + p.relative_to(ROOT).as_posix())
        if p.is_file():
            rel = p.relative_to(ROOT).as_posix()
            actual.add(rel)
            if p.stat().st_size > 2_000_000:
                fail("FILE_TOO_LARGE:" + rel)
            try:
                text = p.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                fail("BINARY_ASSET_REQUIRES_REVIEW:" + rel)
            scan_text(rel, text)
            if rel.endswith(".svg"):
                try:
                    tree = ET.fromstring(text)
                except ET.ParseError:
                    fail("SVG_INVALID:" + rel)
                for element in tree.iter():
                    if element.tag.endswith("script"):
                        fail("SVG_SCRIPT_NOT_ALLOWED")
                    for key, value in element.attrib.items():
                        if key.lower().endswith("href") and (value.startswith("http:") or value.startswith("https:") or value.startswith("data:")):
                            fail("SVG_EXTERNAL_ASSET_NOT_ALLOWED")
                        if key.lower().startswith("on"):
                            fail("SVG_EVENT_HANDLER_NOT_ALLOWED")
    if actual != ALLOWED:
        missing = sorted(ALLOWED - actual)
        extra = sorted(actual - ALLOWED)
        fail("ALLOWLIST_MISMATCH:missing=" + ",".join(missing) + ";extra=" + ",".join(extra))
    return sorted(actual)


def audit_history() -> tuple[int, int]:
    commits = [x for x in run_git("rev-list", "--reverse", "--all").splitlines() if x]
    if not commits:
        fail("NO_LOCAL_HISTORY")
    checked = 0
    for commit in commits:
        names = [x for x in run_git("ls-tree", "-r", "--name-only", commit).splitlines() if x]
        if not set(names).issubset(ALLOWED):
            fail("HISTORY_PATH_NOT_ALLOWLISTED")
        message = run_git("show", "-s", "--format=%B", commit)
        scan_text("commit-message", message)
        for name in names:
            content = run_git("show", f"{commit}:{name}")
            scan_text(name, content)
            checked += 1
    return len(commits), checked


def main() -> int:
    paths = audit_worktree()
    commits, bindings = audit_history()
    print(f"PASS allowlisted_files={len(paths)} local_commits={commits} historical_file_versions_scanned={bindings} links_checked=complete license=none external_links=only_repository_url")
    return 0


if __name__ == "__main__":
    sys.exit(main())
