import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENTS = sorted(n for n in os.listdir(os.path.join(ROOT, "agents")) if n.endswith(".md"))
SKILLS = sorted(d for d in os.listdir(os.path.join(ROOT, "skills"))
                if os.path.isfile(os.path.join(ROOT, "skills", d, "SKILL.md")))


def rd(path):
    with open(path) as f:
        return f.read()


def wr(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


def tree(root):
    out = {}
    for dirpath, dirs, files in os.walk(root):
        for name in dirs + files:
            p = os.path.join(dirpath, name)
            out[p] = "-> " + os.readlink(p) if os.path.islink(p) else rd(p) if os.path.isfile(p) else "dir"
    return out


class InstallTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = os.path.realpath(self.tmp.name)
        self.home = os.path.join(base, "home")
        os.makedirs(self.home)
        self.repo = os.path.join(base, "repo")
        shutil.copytree(ROOT, self.repo, symlinks=True,
                        ignore=shutil.ignore_patterns(".git", "agent-memory*", "worktrees", "__pycache__"))
        self.claude = os.path.join(self.home, ".claude")

    def tearDown(self):
        self.tmp.cleanup()

    def run_install(self, *args, repo=None, expect=0):
        env = {k: v for k, v in os.environ.items() if k != "XDG_CONFIG_HOME"}
        env["HOME"] = self.home
        result = subprocess.run(["bash", os.path.join(repo or self.repo, "install.sh"), *args],
                                env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, expect, result.stdout + result.stderr)
        return result.stdout + result.stderr

    def target(self, path):
        return os.path.realpath(os.path.join(self.home, path))

    def assert_installed(self):
        self.assertEqual(self.target(".claude/CLAUDE.md"), os.path.join(self.repo, "claude", "CLAUDE.md"))
        self.assertEqual(self.target(".claude/settings.json"), os.path.join(self.repo, "claude", "settings.json"))
        for name in AGENTS:
            self.assertEqual(self.target(f".claude/agents/{name}"), os.path.join(self.repo, "agents", name))
        for name in SKILLS:
            self.assertEqual(self.target(f".claude/skills/{name}"), os.path.join(self.repo, "skills", name))

    def test_fresh_install_links_everything_and_is_idempotent(self):
        self.run_install()
        self.assert_installed()
        self.assertEqual(self.target(".tmux.conf"), os.path.join(self.repo, "tmux", "tmux.conf"))
        before = tree(self.home)
        self.assertIn("Everything is in place.", self.run_install())
        self.assertEqual(tree(self.home), before)

    def test_dry_run_changes_nothing(self):
        wr(os.path.join(self.claude, "CLAUDE.md"), "mine")
        before = tree(self.home)
        out = self.run_install("--dry-run")
        self.assertIn("Dry run: nothing was changed.", out)
        self.assertEqual(tree(self.home), before)

    def test_existing_files_are_removed_with_a_warning(self):
        wr(os.path.join(self.claude, "CLAUDE.md"), "mine")
        wr(os.path.join(self.claude, "settings.json"), "{}")
        wr(os.path.join(self.claude, "skills", "unslop", "SKILL.md"), "old")
        out = self.run_install()
        self.assertIn("warn: ~/.claude/CLAUDE.md exists; removing it", out)
        self.assertIn("warn: ~/.claude/skills/unslop exists; removing it", out)
        self.assert_installed()

    def test_a_link_into_another_checkout_is_replaced_and_the_checkout_untouched(self):
        other = os.path.join(os.path.dirname(self.repo), "other-clone")
        shutil.copytree(self.repo, other, symlinks=True)
        self.run_install(repo=other)
        before = tree(other)
        out = self.run_install()
        self.assertIn("replacing it", out)
        self.assert_installed()
        self.assertEqual(tree(other), before)

    def test_a_linked_skills_directory_is_replaced_and_its_target_untouched(self):
        other = os.path.join(os.path.dirname(self.repo), "other-clone")
        shutil.copytree(self.repo, other, symlinks=True)
        os.makedirs(self.claude)
        os.symlink(os.path.join(other, "skills"), os.path.join(self.claude, "skills"))
        os.symlink(os.path.join(self.repo, "agents"), os.path.join(self.claude, "agents"))
        before, repo_before = tree(other), tree(self.repo)
        self.run_install()
        self.assertFalse(os.path.islink(os.path.join(self.claude, "skills")))
        self.assertFalse(os.path.islink(os.path.join(self.claude, "agents")))
        self.assert_installed()
        self.assertEqual(tree(other), before)
        self.assertEqual(tree(self.repo), repo_before)

    def test_broken_and_stale_links_are_removed_and_your_own_skills_kept(self):
        gone = os.path.join(os.path.dirname(self.repo), "gone")
        skills = os.path.join(self.claude, "skills")
        os.makedirs(os.path.join(skills, "my-own"))
        for name in ("unslop", "old-skill"):
            os.symlink(os.path.join(gone, "skills", name), os.path.join(skills, name))
        os.symlink(os.path.join(self.repo, "skills", "dropped"), os.path.join(skills, "dropped"))
        os.symlink(os.path.join(gone, "tmux.conf"), os.path.join(self.home, ".tmux.conf"))
        self.run_install()
        self.assert_installed()
        names = os.listdir(skills)
        self.assertIn("my-own", names)
        self.assertNotIn("old-skill", names)
        self.assertNotIn("dropped", names)
        self.assertEqual(self.target(".tmux.conf"), os.path.join(self.repo, "tmux", "tmux.conf"))

    def test_your_tmux_config_is_left_alone_and_the_line_printed(self):
        for conf in (".tmux.conf", ".config/tmux/tmux.conf"):
            with self.subTest(conf=conf):
                path = os.path.join(self.home, conf)
                wr(path, "set -g mouse off\n")
                out = self.run_install()
                self.assertEqual(rd(path), "set -g mouse off\n")
                self.assertIn(f'source-file "{self.repo}/tmux/tmux.conf"', out)
                if conf != ".tmux.conf":
                    self.assertFalse(os.path.lexists(os.path.join(self.home, ".tmux.conf")))
                os.unlink(path)

    def test_a_broken_xdg_tmux_link_counts_as_no_config(self):
        xdg = os.path.join(self.home, ".config", "tmux", "tmux.conf")
        os.makedirs(os.path.dirname(xdg))
        os.symlink(os.path.join(self.home, "gone.conf"), xdg)
        self.run_install()
        self.assertEqual(self.target(".tmux.conf"), os.path.join(self.repo, "tmux", "tmux.conf"))

    def test_repo_reached_through_a_symlink_counts_as_the_same_repo(self):
        alias = os.path.join(os.path.dirname(self.repo), "alias")
        os.symlink(self.repo, alias)
        self.run_install(repo=alias)
        self.assertIn("Everything is in place.", self.run_install())

    def test_uninstall_removes_only_links_into_this_checkout(self):
        wr(os.path.join(self.claude, "skills", "my-own", "SKILL.md"), "mine")
        elsewhere = os.path.join(self.home, "elsewhere.md")
        wr(elsewhere, "x")
        self.run_install()
        os.symlink(elsewhere, os.path.join(self.claude, "agents", "foreign.md"))
        self.run_install("--uninstall")
        self.assertEqual(sorted(os.listdir(os.path.join(self.claude, "skills"))), ["my-own"])
        self.assertEqual(os.listdir(os.path.join(self.claude, "agents")), ["foreign.md"])
        for name in ("CLAUDE.md", "settings.json"):
            self.assertFalse(os.path.lexists(os.path.join(self.claude, name)))
        self.assertFalse(os.path.lexists(os.path.join(self.home, ".tmux.conf")))
        self.assertIn("Everything is in place.", self.run_install("--uninstall"))

    def test_an_unknown_option_is_rejected(self):
        self.assertIn("unknown option: --yes", self.run_install("--yes", expect=2))

    def test_tmux_config_loads(self):
        if not shutil.which("tmux"):
            self.skipTest("tmux not installed")
        sock = os.path.join(os.path.realpath(self.tmp.name), "tmux.sock")
        conf = os.path.join(ROOT, "tmux", "tmux.conf")
        try:
            r = subprocess.run(["tmux", "-S", sock, "-f", conf, "new-session", "-d", ";",
                                "show-options", "-s", "terminal-features"],
                               capture_output=True, text=True, timeout=30)
            self.assertEqual(r.returncode, 0, r.stderr)
            subprocess.run(["tmux", "-S", sock, "source-file", conf], check=True, timeout=30)
            r = subprocess.run(["tmux", "-S", sock, "show-options", "-s", "terminal-features"],
                               capture_output=True, text=True, timeout=30)
            self.assertEqual(r.stdout.count("xterm*:extkeys"), 1, r.stdout)
        finally:
            subprocess.run(["tmux", "-S", sock, "kill-server"], capture_output=True)


if __name__ == "__main__":
    unittest.main()
