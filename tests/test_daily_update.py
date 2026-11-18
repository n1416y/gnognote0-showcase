from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tools.daily_update as updater


class DailyUpdateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.source = self.base / "source"
        self.repo = self.base / "showcase"
        self.source.mkdir()
        self.repo.mkdir()
        (self.source / "evidence").mkdir()
        (self.repo / "docs").mkdir()
        (self.repo / ".git").mkdir()
        (self.repo / "docs/development-log.md").write_text("# Development log\n", encoding="utf-8")
        (self.repo / "docs/status-and-roadmap.md").write_text(
            "# Status\n\n" + updater.STATUS_START + "\n\nold\n\n" + updater.STATUS_END + "\n",
            encoding="utf-8",
        )
        self.evidence = self.source / "evidence/fixture.json"
        self.evidence.write_text('{"fixture":"approved local evidence"}\n', encoding="utf-8")
        self.evidence_hash = hashlib.sha256(self.evidence.read_bytes()).hexdigest()
        self.manifest = self.source / "manifest-1.json"
        self.manifest.write_text(json.dumps({"path": "evidence/fixture.json", "sha256": self.evidence_hash}), encoding="utf-8")
        self.entry = {
            "id": "offline-filter-improvement-2026-11-18",
            "evidence_path": "evidence/fixture.json",
            "evidence_sha256": self.evidence_hash,
            "date": "2026-11-18",
            "category": "offline_knowledge",
            "headline": "A useful offline filter improvement",
            "summary": "A bounded local task improved how readers find recorded review context. Local checks passed; formal acceptance remains open.",
            "status_summary": "A bounded local filter candidate passed local checks; formal acceptance remains open.",
        }
        self.audit = self.base / "audit/audit.jsonl"
        self.policy_path = self.base / "private-policy.json"
        self.policy = {
            "schema": "gnognote0.showcase.local-policy.v1",
            "source_root": str(self.source),
            "manifest_search_dir": ".",
            "manifest_filename_pattern": r"manifest-(?P<number>\d+)\.json",
            "verifier_module": "trusted.fixture.verifier",
            "verifier_function": "verify_manifest",
            "audit_path": str(self.audit),
            "publishing_enabled": False,
            "expected_remote": "https://github.com/n1416y/gnognote0-showcase.git",
            "approved_public_entries": [self.entry],
        }
        self.write_policy()
        self.verified = {
            "status": "PASS_LOCAL_MANIFEST",
            "manifest_sha256": hashlib.sha256(self.manifest.read_bytes()).hexdigest(),
            "verified_local_bindings": 1,
            "readiness": "STOP",
            "execution_authority": "NOT_GRANTED",
        }
        self.patcher = patch.object(updater, "run_baseline_verifier", return_value=(self.verified, self.source, "manifest-1.json"))
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def tearDown(self):
        self.tmp.cleanup()

    def write_policy(self):
        self.policy_path.write_text(json.dumps(self.policy), encoding="utf-8")

    def git(self, cwd: Path, *args: str):
        return subprocess.run(["git", *args], cwd=cwd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def setup_git_remote(self):
        bare = self.base / "remote.git"
        subprocess.run(["git", "init", "--bare", "--initial-branch=main", str(bare)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.git(self.repo, "init", "--initial-branch=main")
        self.git(self.repo, "config", "user.name", "Showcase Test")
        self.git(self.repo, "config", "user.email", "showcase-test")
        self.git(self.repo, "add", "docs/development-log.md", "docs/status-and-roadmap.md")
        self.git(self.repo, "commit", "-m", "Initial test baseline")
        self.git(self.repo, "remote", "add", "origin", bare.as_uri())
        self.git(self.repo, "push", "-u", "origin", "main")
        self.policy["allow_local_remote_for_tests"] = True
        self.write_policy()

    def test_meaningful_progress_is_prepared_but_no_private_source_is_changed(self):
        before = hashlib.sha256(self.evidence.read_bytes()).hexdigest()
        result = updater.execute(self.policy_path, "prepare", repo_root=self.repo)
        self.assertEqual(result["status"], "PREVIEW_ONLY")
        self.assertIn(self.entry["headline"], result["preview_text"])
        self.assertFalse((self.repo / "docs/development-log.md").read_text().find(self.entry["id"]) >= 0)
        self.assertEqual(hashlib.sha256(self.evidence.read_bytes()).hexdigest(), before)

    def test_no_meaningful_change_publishes_nothing(self):
        self.policy["approved_public_entries"] = []
        self.write_policy()
        before = (self.repo / "docs/development-log.md").read_bytes()
        result = updater.execute(self.policy_path, "prepare", repo_root=self.repo)
        self.assertEqual(result["status"], "NO_MEANINGFUL_CHANGE")
        self.assertEqual((self.repo / "docs/development-log.md").read_bytes(), before)

    def test_private_path_secret_and_hidden_content_are_rejected(self):
        bad_path = "/" + "Users" + "/someone/private/file.txt"
        with self.assertRaisesRegex(updater.UpdateError, "PUBLIC_TEXT_REJECTED"):
            updater.safe_text("Found at " + bad_path, "summary")
        synthetic_token = "gh" + "p_" + "A" * 30
        with self.assertRaisesRegex(updater.UpdateError, "PUBLIC_TEXT_REJECTED"):
            updater.safe_text("Use " + synthetic_token, "summary")
        with self.assertRaisesRegex(updater.UpdateError, "PUBLIC_TEXT_REJECTED"):
            updater.safe_text("The hidden " + "code is a sample", "summary")

    def test_interrupted_after_commit_recovers_without_duplicate_commit_or_entry(self):
        self.setup_git_remote()
        before_count = int(self.git(self.repo, "rev-list", "--count", "HEAD").stdout.strip())
        added = updater.append_log(self.repo, [updater.validate_entry(self.entry)])
        self.assertEqual(added, [self.entry["id"]])
        updater.commit_allowed_changes(self.repo, [self.entry])
        committed_sha = self.git(self.repo, "rev-parse", "HEAD").stdout.strip()
        recovered = updater.push_only_allowlisted_ahead(self.repo, self.policy, test_mode=True)
        self.assertEqual(recovered, committed_sha)
        second = updater.append_log(self.repo, [updater.validate_entry(self.entry)])
        self.assertEqual(second, [])
        self.assertEqual(int(self.git(self.repo, "rev-list", "--count", "HEAD").stdout.strip()), before_count + 1)
        self.assertEqual((self.repo / "docs/development-log.md").read_text().count(f"showcase-update:{self.entry['id']}"), 1)

    def test_duplicate_publication_is_noop_after_success(self):
        self.setup_git_remote()
        self.policy["publishing_enabled"] = True
        self.write_policy()
        result = updater.execute(self.policy_path, "publish", repo_root=self.repo, test_mode=True)
        self.assertEqual(result["status"], "PUBLISHED")
        head = self.git(self.repo, "rev-parse", "HEAD").stdout.strip()
        rerun = updater.execute(self.policy_path, "publish", repo_root=self.repo, test_mode=True)
        self.assertIn(rerun["status"], {"NO_MEANINGFUL_CHANGE", "DAILY_RUN_ALREADY_COMPLETED"})
        self.assertEqual(self.git(self.repo, "rev-parse", "HEAD").stdout.strip(), head)

    def test_stale_evidence_hash_and_excluded_binding_fail_closed(self):
        before = self.policy["approved_public_entries"][0]["evidence_sha256"]
        self.evidence.write_text('{"fixture":"changed after curation"}\n', encoding="utf-8")
        with self.assertRaisesRegex(updater.UpdateError, "APPROVED_EVIDENCE_HASH_MISMATCH"):
            updater.eligible_entries(self.policy, self.source, "manifest-1.json", self.verified["manifest_sha256"])
        self.assertEqual(updater.recursively_bound({"path": "evidence/fixture.json", "sha256": before, "copy_in_candidate": False}, "evidence/fixture.json", before), False)

    def test_publishing_disabled_cannot_write_or_push(self):
        self.setup_git_remote()
        before = (self.repo / "docs/development-log.md").read_bytes()
        preview = updater.execute(self.policy_path, "prepare", repo_root=self.repo, test_mode=True)
        self.assertEqual(preview["status"], "PREVIEW_ONLY")
        result = updater.execute(self.policy_path, "publish", repo_root=self.repo, test_mode=True)
        self.assertEqual(result["status"], "PUBLISHING_DISABLED")
        self.assertEqual((self.repo / "docs/development-log.md").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
