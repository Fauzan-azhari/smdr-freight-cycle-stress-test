"""Uji tabel kurasi dan registri (M0 dan bukti): skema, referensi, dan hash sumber."""
import ast
import csv
import os
import unittest

try:
    import needs_sources as ns
except ImportError:   # dijalankan sebagai tests.test_x
    from tests import needs_sources as ns
from smdr import baseline, datapaths

ALLOWED = {"retain", "extend", "recalibrate", "redefine", "context_only", "quarantine", "archive_only", "benchmark"}


def read(name):
    with open(datapaths.table(name), encoding="utf-8") as f:
        return list(csv.DictReader(f))


class TransitionTablesTest(unittest.TestCase):
    @ns.needs("Annual-Report")
    def test_source_manifest_hash_matches_files(self):
        for r in read("source_manifest.csv"):
            self.assertEqual(baseline.sha256(os.path.join(baseline.ROOT, r["path_or_url"])), r["sha256"], r["source_id"])

    def test_evidence_references_known_sources(self):
        known = {r["source_id"] for r in read("source_manifest.csv")}
        with open(datapaths.table("fs_source_manifest.csv"), encoding="utf-8") as f:
            known |= {r["file_id"] for r in csv.DictReader(f)}
        ev = read("evidence.csv")
        self.assertEqual(len({r["evidence_id"] for r in ev}), len(ev))
        for r in ev:
            self.assertIn(r["source_id"], known, r["evidence_id"])
            self.assertTrue(r["locator"] and r["claim"] and r["value"], r["evidence_id"])

    def test_conflict_groups_have_two_sides(self):
        groups = {}
        for r in read("evidence.csv"):
            if r["conflict_group_id"]:
                groups.setdefault(r["conflict_group_id"], []).append(r["acceptance_status"])
        for g, v in groups.items():
            self.assertGreaterEqual(len(v), 2, g)
            self.assertLessEqual(v.count("usable"), 1, g)  # satu sisi dipilih; sisi lain tidak boleh ikut dipakai
            if "usable" in v:  # sisi terpilih harus punya keputusan pengguna yang tercatat
                self.assertIn(g, {"CG-COGSDEP-FY2025"} & set(groups))
                self.assertIn("D01", {r["decision_id"] for r in read("decisions.csv")})

    def test_user_decisions_recorded(self):
        d = {r["decision_id"]: r for r in read("decisions.csv")}
        self.assertEqual(d["D01"]["decision"], "pdf_audit")
        self.assertEqual(d["D02"]["decision"], "approved")
        self.assertTrue(all(r["decided_by"] == "pengguna" and r["decided_on"] for r in d.values()))
        for r in read("zero_fill_rules.csv"):
            self.assertIn(r["status"], ("approved", "proposed"))
            self.assertEqual(bool(r["approved_on"]), r["status"] == "approved", r["rule_id"])

    def test_legacy_decisions_valid(self):
        rows = read("legacy_decisions.csv")
        self.assertEqual(len({r["legacy_id"] for r in rows}), len(rows))
        for r in rows:
            self.assertTrue(set(r["disposition"].split("+")) <= ALLOWED, r["legacy_id"])
            for k in ("legacy_path", "metric", "new_target", "reason", "expected_impact", "verification_step"):
                self.assertTrue(r[k], "%s.%s" % (r["legacy_id"], k))

    def test_no_runtime_dependency_on_legacy_folder(self):
        # tidak ada modul yang boleh membaca model/data (pipeline v4 sudah diarsipkan)
        src = os.path.join(baseline.ROOT, "src", "smdr")
        for fn in sorted(os.listdir(src)):
            if not fn.endswith(".py"):
                continue
            tree = ast.parse(open(os.path.join(src, fn), encoding="utf-8").read())
            strings = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
            doc = ast.get_docstring(tree, clean=False)
            self.assertFalse([x for x in strings if x != doc and "model/data" in x], fn)
            joined = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "join"]
            for call in joined:
                args = [a.value for a in call.args if isinstance(a, ast.Constant)]
                self.assertFalse("model" in args and "data" in args and "transition" not in args, fn)


if __name__ == "__main__":
    unittest.main()
