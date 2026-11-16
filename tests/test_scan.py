import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCAN = os.path.join(ROOT, "skills", "setup-home-repo", "scan.py")
GIT = ["git", "-c", "user.email=t@t", "-c", "user.name=t"]


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


class ScanTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.workspace = os.path.join(os.path.realpath(self.tmp.name), "workspace")
        new_repo(os.path.join(self.workspace, "api"), {"go.mod": "module api\n", "CLAUDE.md": "rules\n"})
        new_repo(os.path.join(self.workspace, "web"), {"package.json": "{}\n"})
        os.makedirs(os.path.join(self.workspace, "notes"))
        subprocess.run(["git", "-C", os.path.join(self.workspace, "api"), "remote", "add", "origin",
                        "git@example.com:team/api.git"], check=True)

    def scan(self, *args, root=None):
        run = subprocess.run([sys.executable, SCAN, root or self.workspace, *args], capture_output=True, text=True)
        return run.returncode, run.stdout, run.stderr

    def test_lists_only_the_child_folders_that_are_git_repos(self):
        code, out, _ = self.scan()
        result = json.loads(out)
        self.assertEqual(code, 0)
        self.assertFalse(result["is_home_repo"])
        self.assertIsNone(result["inside_another_repo"])
        self.assertEqual(result["repos"], [
            {"name": "api", "remote": "git@example.com:team/api.git", "default_branch": "main",
             "manifests": ["go.mod"], "has_claude_md": True},
            {"name": "web", "remote": None, "default_branch": "main",
             "manifests": ["package.json"], "has_claude_md": False},
        ])

    def test_reports_the_repo_a_folder_sits_inside(self):
        _, out, _ = self.scan(root=os.path.join(self.workspace, "api"))
        self.assertEqual(json.loads(out)["inside_another_repo"], None)
        nested = os.path.join(self.workspace, "api", "packages")
        os.makedirs(nested)
        _, out, _ = self.scan(root=nested)
        self.assertEqual(json.loads(out)["inside_another_repo"], os.path.join(self.workspace, "api"))

    def test_recognises_an_existing_home_repo(self):
        subprocess.run(["git", "init", "-q", self.workspace], check=True)
        _, out, _ = self.scan()
        self.assertTrue(json.loads(out)["is_home_repo"])

    def test_refresh_keeps_notes_adds_new_repos_and_reports_dropped_ones(self):
        rules = os.path.join(self.workspace, "CLAUDE.md")
        wr(rules, "\n".join([
            "# Workspace", "", "My own notes.", "", "<!-- other-repos:start -->",
            "| Repo | Remote | Default branch | Notes |", "|---|---|---|---|",
            "| `api` | old-remote | master | The Go service; owns billing |",
            "| `gone` | x | main | Retired |",
            "<!-- other-repos:end -->", "", "## After", ""]))
        code, out, _ = self.scan("--update", rules)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["dropped_rows"], ["gone"])
        text = rd(rules)
        self.assertIn("| `api` | git@example.com:team/api.git | main | The Go service; owns billing |", text)
        self.assertIn("| `web` | none | main |  |", text)
        self.assertNotIn("gone", text)
        self.assertTrue(text.startswith("# Workspace\n\nMy own notes.\n"))
        self.assertTrue(text.endswith("\n## After\n"))
        self.scan("--update", rules)
        self.assertEqual(rd(rules), text)

    def test_refresh_refuses_a_file_without_the_markers(self):
        rules = os.path.join(self.workspace, "CLAUDE.md")
        wr(rules, "# Workspace\n")
        code, _, err = self.scan("--update", rules)
        self.assertEqual(code, 1)
        self.assertIn("markers", err)
        self.assertEqual(rd(rules), "# Workspace\n")

if __name__ == "__main__":
    unittest.main()
