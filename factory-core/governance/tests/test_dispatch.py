from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from governance.dispatch import load_dispatch, write_dispatch


SHA = "a" * 40


def dispatch(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "schema_version": 2,
        "dispatch_id": "dispatch-1",
        "change_id": "g2-canary-pr-7",
        "repository": "dfeliu/g2-qualification-canary-20260831",
        "pr_number": 7,
        "head_sha": SHA,
        "policy_source_commit": "b" * 40,
        "policy_id": "g2-disposable",
        "policy_revision": 2,
        "policy_sha256": "f" * 64,
        "enforcement_mode": "shadow",
        "requested_at": "2026-09-01T10:00:00Z",
    }
    return {**value, **overrides}


class DispatchTests(unittest.TestCase):
    def test_writes_and_loads_an_immutable_explicit_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = write_dispatch(Path(temporary), dispatch())
            self.assertEqual(path.name, "dispatch-1.json")
            self.assertEqual(
                load_dispatch(Path(temporary), "g2-canary-pr-7", "dispatch-1")["head_sha"],
                SHA,
            )
            with self.assertRaises(FileExistsError):
                write_dispatch(Path(temporary), dispatch())

    def test_rejects_invalid_schema_and_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "unknown keys"):
                write_dispatch(Path(temporary), {**dispatch(), "extra": True})
            with self.assertRaisesRegex(ValueError, "valid identifier"):
                load_dispatch(Path(temporary), "../other", "dispatch-1")
            with self.assertRaisesRegex(ValueError, "positive"):
                write_dispatch(Path(temporary), dispatch(pr_number=0))

    def test_accepts_distinct_review_head_and_rejects_invalid_value(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = dispatch(review_head_sha="c" * 40)
            path = write_dispatch(root, value)
            self.assertEqual(
                load_dispatch(root, "g2-canary-pr-7", "dispatch-1")["review_head_sha"],
                "c" * 40,
            )
            with self.assertRaisesRegex(ValueError, "review_head_sha"):
                write_dispatch(root / "invalid", dispatch(review_head_sha="invalid"))

    def test_rejects_manifest_identity_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = write_dispatch(root, dispatch())
            path.write_text(
                path.read_text(encoding="utf-8").replace("dispatch-1", "dispatch-2"),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "identity"):
                load_dispatch(root, "g2-canary-pr-7", "dispatch-1")

    def test_rejects_symlinked_manifest_and_unprovisioned_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "dispatch"
            with self.assertRaisesRegex(RuntimeError, "root is not provisioned"):
                load_dispatch(root, "g2-canary-pr-7", "dispatch-1")
            real_root = Path(temporary) / "real"
            path = write_dispatch(real_root, dispatch())
            link = path.with_name("dispatch-link.json")
            try:
                link.symlink_to(path)
            except OSError as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")
            with self.assertRaisesRegex(RuntimeError, "manifest is unavailable"):
                load_dispatch(real_root, "g2-canary-pr-7", "dispatch-link")
