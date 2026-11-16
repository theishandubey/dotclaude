import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECK_REFS = os.path.join(ROOT, "skills", "map-architecture", "check_refs.py")
GIT = ["git", "-c", "user.email=t@t", "-c", "user.name=t"]
FENCE = "`" * 3


def wr(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def rd(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def new_repo(path, files=None):
    os.makedirs(path)
    subprocess.run(["git", "init", "-q", "-b", "main", path], check=True)
    for name, text in (files or {}).items():
        wr(os.path.join(path, name), text)
    subprocess.run(GIT + ["-C", path, "add", "-A"], check=True)
    subprocess.run(GIT + ["-C", path, "commit", "-q", "--allow-empty", "-m", "init"], check=True)
    return subprocess.run(["git", "-C", path, "rev-parse", "--short", "HEAD"],
                          capture_output=True, text=True, check=True).stdout.strip()


class CheckRefsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = os.path.join(os.path.realpath(self.tmp.name), "repo")
        self.commit = new_repo(self.repo, {"src/orders.py": "one\ntwo\nthree\n"})

    def document(self, ref="src/orders.py:2", rows=("| `[*]` | `draft` | create | `src/orders.py:1` |",
                                                    "| `draft` | `paid` | paid | `src/orders.py:3` |"),
                 pin=True):
        lines = ["# Architecture", ""]
        if pin:
            lines += [f"Commit: `{self.commit}`", ""]
        lines += [f"The handler lives at `{ref}` and listens on `localhost:8080`.", "", "## State machine: order", "",
                  "| From | To | Guard | Where |", "|---|---|---|---|", *rows, "",
                  FENCE + "mermaid", "stateDiagram-v2", "  [*] --> draft", "  draft --> paid: paid", FENCE, ""]
        path = os.path.join(os.path.dirname(self.repo), "architecture.md")
        wr(path, "\n".join(lines))
        return path

    def check(self, document):
        run = subprocess.run([sys.executable, CHECK_REFS, document, "--repo", self.repo], capture_output=True, text=True)
        return run.returncode, run.stdout + run.stderr

    def test_a_document_that_matches_the_code_passes(self):
        code, out = self.check(self.document())
        self.assertEqual(code, 0, out)
        self.assertIn("references: 3 checked", out)
        self.assertIn("state tables: 1 diagrams, 0 mismatches", out)

    def test_a_line_past_the_end_of_the_file_fails(self):
        code, out = self.check(self.document(ref="src/orders.py:40"))
        self.assertEqual(code, 1)
        self.assertIn("src/orders.py:40", out)

    def test_a_file_missing_at_the_pinned_commit_fails(self):
        wr(os.path.join(self.repo, "src/later.py"), "added after the pin\n")
        code, out = self.check(self.document(ref="src/later.py:1"))
        self.assertEqual(code, 1)
        self.assertIn("no such file", out)

    def test_a_transition_drawn_without_a_table_row_fails(self):
        code, out = self.check(self.document(rows=("| `[*]` | `draft` | create | `src/orders.py:1` |",)))
        self.assertEqual(code, 1)
        self.assertIn("draft --> paid is drawn but has no table row", out)

    def test_a_table_row_that_is_not_drawn_fails(self):
        rows = ("| `[*]` | `draft` | create | `src/orders.py:1` |", "| `draft` | `paid` | paid | `src/orders.py:3` |",
                "| `paid` | `refunded` | refund | `src/orders.py:3` |")
        code, out = self.check(self.document(rows=rows))
        self.assertEqual(code, 1)
        self.assertIn("paid --> refunded has a table row but is not drawn", out)

    def test_a_document_without_a_pinned_commit_fails(self):
        code, out = self.check(self.document(pin=False))
        self.assertEqual(code, 1)
        self.assertIn("Commit:", out)

if __name__ == "__main__":
    unittest.main()
