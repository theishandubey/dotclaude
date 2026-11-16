import json
import os
import pty
import shutil
import stat
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def rd(path):
    with open(path) as f:
        return f.read()


def wr(path, text):
    with open(path, "w") as f:
        f.write(text)


def load(path):
    return json.loads(rd(path))


def dump(data, path):
    wr(path, json.dumps(data))


DEFAULTS = load(os.path.join(ROOT, "claude", "settings.json"))
RECORDED = sorted(load(os.path.join(ROOT, "skills-lock.json"))["skills"])
FAKE_NPX = """#!/usr/bin/env bash
echo "$*" >> "$HOME/npx.log"
while [ $# -gt 0 ]; do
  if [ "$1" = "-s" ]; then
    mkdir -p "$HOME/.claude/skills/$2"
    echo installed > "$HOME/.claude/skills/$2/SKILL.md"
  fi
  shift
done
"""
AGENTS = sorted(n for n in os.listdir(os.path.join(ROOT, "agents")) if n.endswith(".md"))
SKILLS = sorted(d for d in os.listdir(os.path.join(ROOT, "skills"))
                if os.path.isfile(os.path.join(ROOT, "skills", d, "SKILL.md")))


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
        self.settings = os.path.join(self.claude, "settings.json")
        self.bin = os.path.join(base, "bin")
        os.makedirs(self.bin)
        wr(os.path.join(self.bin, "npx"), FAKE_NPX)
        os.chmod(os.path.join(self.bin, "npx"), 0o755)

    def tearDown(self):
        self.tmp.cleanup()

    def run_install(self, *args, repo=None, expect=0, stdin=subprocess.DEVNULL, path=None):
        env = {k: v for k, v in os.environ.items() if k not in ("XDG_CONFIG_HOME", "NO_COLOR")}
        env["HOME"] = self.home
        env["PATH"] = path or self.bin + os.pathsep + env["PATH"]
        result = subprocess.run(["bash", os.path.join(repo or self.repo, "install.sh"), *args],
                                env=env, stdin=stdin, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, expect, result.stdout + result.stderr)
        return result.stdout + result.stderr

    def run_answering(self, answers, *args):
        master, slave = pty.openpty()
        try:
            os.write(master, answers.encode())
            return self.run_install(*args, stdin=slave)
        finally:
            os.close(master)
            os.close(slave)

    def npx_calls(self):
        log = os.path.join(self.home, "npx.log")
        return rd(log).splitlines() if os.path.exists(log) else []

    def read_settings(self):
        return load(self.settings)

    def write_settings(self, data):
        os.makedirs(self.claude, exist_ok=True)
        dump(data, self.settings)

    def link_target(self, path):
        return os.path.realpath(os.path.join(self.home, path))

    def snapshot(self):
        out = {}
        for dirpath, dirs, files in os.walk(self.home):
            for name in dirs + files:
                p = os.path.join(dirpath, name)
                if os.path.islink(p):
                    out[p] = "-> " + os.readlink(p)
                elif os.path.isfile(p):
                    with open(p, "rb") as f:
                        out[p] = f.read()
        return out

    def test_fresh_install_links_everything_and_is_idempotent(self):
        self.run_install("--yes")
        self.assertEqual(self.link_target(".claude/CLAUDE.md"), os.path.join(self.repo, "claude", "CLAUDE.md"))
        for name in AGENTS:
            self.assertEqual(self.link_target(f".claude/agents/{name}"), os.path.join(self.repo, "agents", name))
        for name in SKILLS:
            self.assertEqual(self.link_target(f".claude/skills/{name}"), os.path.join(self.repo, "skills", name))
        self.assertEqual(self.link_target(".tmux.conf"), os.path.join(self.repo, "tmux", "tmux.conf"))
        self.assertEqual(self.read_settings(), DEFAULTS)
        self.assertEqual(sorted(os.listdir(os.path.join(self.claude, "skills"))), sorted(SKILLS + RECORDED))
        before = self.snapshot()
        out = self.run_install("--yes")
        self.assertIn("Everything is in place.", out)
        self.assertEqual(self.snapshot(), before)

    def test_dry_run_changes_nothing(self):
        self.write_settings({"theme": "light"})
        before = self.snapshot()
        out = self.run_install("--dry-run")
        self.assertIn("Dry run", out)
        self.assertEqual(self.snapshot(), before)

    def test_without_a_terminal_or_yes_it_is_a_dry_run(self):
        self.write_settings({"theme": "light"})
        before = self.snapshot()
        out = self.run_install()
        self.assertIn("No terminal and no --yes", out)
        self.assertEqual(self.snapshot(), before)

    def test_settings_change_is_shown_as_a_diff(self):
        self.write_settings({"theme": "light"})
        out = self.run_install("--dry-run")
        self.assertIn('+  "attribution": false', out)

    def test_each_step_can_be_applied_skipped_or_stopped_at(self):
        out = self.run_answering("y\ns\nq\n")
        self.assertIn("Stopped", out)
        self.assertTrue(os.path.islink(os.path.join(self.claude, "CLAUDE.md")))
        self.assertFalse(os.path.exists(self.settings))
        self.assertFalse(os.path.lexists(os.path.join(self.home, ".tmux.conf")))
        self.assertEqual(self.npx_calls(), [])

    def test_missing_third_party_skills_are_installed_pinned_and_never_updated(self):
        self.run_install("--yes")
        calls = self.npx_calls()
        self.assertEqual(len(calls), len(RECORDED))
        for call in calls:
            self.assertRegex(call, r"^--yes skills@\d+\.\d+\.\d+ add \S+ -g -a claude-code -s \S+ -y$")
        self.run_install("--yes")
        self.assertEqual(self.npx_calls(), calls)

    def test_interactive_install_leaves_the_skills_cli_prompts_on(self):
        self.run_answering("y\ny\ny\ny\n")
        for call in self.npx_calls():
            self.assertNotIn("-y", call.split())
            self.assertNotIn("--yes", call.split())

    def test_without_npx_third_party_skills_are_skipped_with_a_warning(self):
        tools = os.path.join(os.path.dirname(self.bin), "tools")
        os.makedirs(tools)
        for tool in ("bash", "python3", "git", "dirname"):
            os.symlink(shutil.which(tool), os.path.join(tools, tool))
        out = self.run_install("--yes", path=tools)
        self.assertIn("npx is not installed", out)
        self.assertTrue(os.path.islink(os.path.join(self.claude, "CLAUDE.md")))

    def test_a_recorded_skill_this_repo_ships_is_not_installed_twice(self):
        lock = os.path.join(self.repo, "skills-lock.json")
        data = load(lock)
        data["skills"][SKILLS[0]] = {"source": "someone/skills", "sourceType": "github"}
        dump(data, lock)
        out = self.run_install("--yes")
        self.assertIn(f"{SKILLS[0]} is recorded in skills-lock.json but this repo ships its own", out)
        self.assertEqual(self.link_target(f".claude/skills/{SKILLS[0]}"), os.path.join(self.repo, "skills", SKILLS[0]))
        self.assertEqual(len(self.npx_calls()), len(RECORDED))

    def test_unrecorded_skills_are_listed_and_recorded_only_when_chosen(self):
        os.makedirs(os.path.join(self.home, ".agents"))
        dump({"version": 3, "skills": {
            "extra-one": {"source": "a/b", "sourceType": "github", "skillPath": "skills/extra-one/SKILL.md", "skillFolderHash": "x"},
            "extra-two": {"source": "c/d", "sourceType": "github", "skillPath": "SKILL.md"},
        }}, os.path.join(self.home, ".agents", ".skill-lock.json"))
        lock = os.path.join(self.repo, "skills-lock.json")
        before = rd(lock)
        out = self.run_install("--yes")
        self.assertIn("extra-one (a/b)", out)
        self.assertEqual(rd(lock), before)
        self.run_answering("y\nextra-two\n")
        recorded = load(lock)["skills"]
        self.assertEqual(recorded["extra-two"], {"source": "c/d", "sourceType": "github", "skillPath": "SKILL.md"})
        self.assertNotIn("extra-one", recorded)

    def test_plugin_settings_this_repo_used_to_set_are_left_to_the_user(self):
        plugins = {"enabledPlugins": {"mod@claude-mods": True},
                   "extraKnownMarketplaces": {"claude-mods": {"source": {"source": "github", "repo": "x/y"}}}}
        self.write_settings(dict(plugins, hooks={"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "old-guard"}]}],
                                                 "SessionStart": [{"hooks": [{"type": "command", "command": "old-start"}]},
                                                                  {"hooks": [{"type": "command", "command": "mine"}]}]}))
        dump({"repo": self.repo, "settings": dict(plugins, hooks={
            "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "old-guard"}]}],
            "SessionStart": [{"hooks": [{"type": "command", "command": "old-start"}]}]})},
            os.path.join(self.claude, "dotclaude-state.json"))
        self.run_install("--yes")
        s = self.read_settings()
        self.assertEqual({k: s[k] for k in plugins}, plugins)
        self.assertEqual(s["hooks"], {"SessionStart": [{"hooks": [{"type": "command", "command": "mine"}]}]})

    def hook(self, command):
        return {"matcher": "Bash", "hooks": [{"type": "command", "command": command}]}

    def test_hooks_whose_script_is_gone_are_removed_and_the_rest_kept(self):
        os.makedirs(os.path.join(self.claude, "hooks"))
        os.symlink(os.path.join(self.repo, "hooks", "gone.py"), os.path.join(self.claude, "hooks", "gone.py"))
        wr(os.path.join(self.claude, "hooks", "mine.sh"), "echo mine")
        kept = [self.hook("bash '" + os.path.join(self.claude, "hooks", "mine.sh") + "' session"), self.hook("echo no script")]
        dead = [self.hook('f="$HOME/.claude/hooks/old-guard.sh"; [ -x "$f" ] || exit 0; exec "$f"'),
                self.hook('python3 "$HOME/.claude/hooks/gone.py"')]
        self.write_settings({"hooks": {"PreToolUse": kept + dead, "Stop": dead[:1]}})
        self.run_install("--yes")
        self.assertEqual(self.read_settings()["hooks"], {"PreToolUse": kept})
        self.assertIn("Everything is in place.", self.run_install("--yes"))

    def test_links_from_the_old_roster_are_removed(self):
        os.makedirs(os.path.join(self.claude, "agents"))
        os.symlink(os.path.join(self.repo, "agents", "gone"), os.path.join(self.claude, "agents", "gone"))
        wr(os.path.join(self.claude, "agents", "mine.md"), "mine")
        self.run_install("--yes")
        self.assertEqual(sorted(os.listdir(os.path.join(self.claude, "agents"))), sorted(AGENTS + ["mine.md"]))

    def test_user_values_survive_and_removals_stick(self):
        self.write_settings({"theme": "light", "permissions": {"allow": ["Bash(ls:*)"]}})
        self.run_install("--yes")
        s = self.read_settings()
        self.assertEqual(s["theme"], "light")
        self.assertIn("Bash(ls:*)", s["permissions"]["allow"])
        self.assertIn("Bash(make:*)", s["permissions"]["allow"])
        s["permissions"]["allow"].remove("Bash(make:*)")
        del s["tui"]
        s["model"] = "sonnet"
        self.write_settings(s)
        self.run_install("--yes")
        s = self.read_settings()
        self.assertNotIn("Bash(make:*)", s["permissions"]["allow"])
        self.assertNotIn("tui", s)
        self.assertEqual(s["model"], "sonnet")

    def test_changed_repo_defaults_replace_old_ones(self):
        self.run_install("--yes")
        defaults_path = os.path.join(self.repo, "claude", "settings.json")
        new = load(defaults_path)
        new["permissions"]["allow"].remove("Bash(cargo:*)")
        new["permissions"]["allow"].append("Bash(uv:*)")
        new["theme"] = "light"
        dump(new, defaults_path)
        self.run_install("--yes")
        s = self.read_settings()
        self.assertNotIn("Bash(cargo:*)", s["permissions"]["allow"])
        self.assertIn("Bash(uv:*)", s["permissions"]["allow"])
        self.assertEqual(s["theme"], "light")

    def test_existing_files_go_to_the_backup_dir(self):
        os.makedirs(os.path.join(self.claude, "skills", "unslop"))
        wr(os.path.join(self.claude, "skills", "unslop", "SKILL.md"), "old")
        wr(os.path.join(self.claude, "CLAUDE.md"), "mine")
        self.assertIn("backup:", self.run_install("--dry-run"))
        self.run_install("--yes")
        self.assertTrue(os.path.islink(os.path.join(self.claude, "skills", "unslop")))
        self.assertEqual(os.listdir(os.path.join(self.claude, "skills")).count("unslop"), 1)
        self.assertFalse([n for n in os.listdir(os.path.join(self.claude, "skills")) if ".bak" in n])
        backups = os.path.join(self.home, ".dotclaude-backups")
        [stamp] = os.listdir(backups)
        self.assertEqual(rd(os.path.join(backups, stamp, ".claude", "CLAUDE.md")), "mine")
        self.assertTrue(os.path.isfile(os.path.join(backups, stamp, ".claude", "skills", "unslop", "SKILL.md")))

    def test_leaves_unrelated_skills_alone_and_removes_stale_repo_links(self):
        os.makedirs(os.path.join(self.claude, "skills", "my-own", ))
        os.makedirs(os.path.join(self.claude, "skills", "synced"))
        self.run_install("--yes")
        os.symlink(os.path.join(self.repo, "skills", "gone"), os.path.join(self.claude, "skills", "gone"))
        self.run_install("--yes")
        names = os.listdir(os.path.join(self.claude, "skills"))
        self.assertIn("my-own", names)
        self.assertIn("synced", names)
        self.assertNotIn("gone", names)

    def test_repo_reached_through_a_symlink_counts_as_the_same_repo(self):
        alias = os.path.join(os.path.dirname(self.repo), "alias")
        os.symlink(self.repo, alias)
        self.run_install("--yes", repo=alias)
        out = self.run_install("--yes")
        self.assertIn("Everything is in place.", out)

    def test_settings_mode_and_symlink_are_preserved(self):
        dotfiles = os.path.join(self.home, "dotfiles")
        os.makedirs(dotfiles)
        real = os.path.join(dotfiles, "settings.json")
        dump({"theme": "light"}, real)
        os.chmod(real, 0o640)
        os.makedirs(self.claude)
        os.symlink(real, self.settings)
        self.run_install("--yes")
        self.assertTrue(os.path.islink(self.settings))
        self.assertEqual(stat.S_IMODE(os.stat(real).st_mode), 0o640)
        self.assertEqual(load(real)["theme"], "light")

    def test_invalid_settings_abort_without_changes(self):
        os.makedirs(self.claude)
        wr(self.settings, "{not json")
        before = self.snapshot()
        self.run_install("--yes", expect=1)
        self.assertEqual(self.snapshot(), before)

    def test_tmux_existing_config_gets_a_source_line(self):
        conf = os.path.join(self.home, ".tmux.conf")
        wr(conf, "set -g prefix C-a")
        self.run_install("--yes")
        text = rd(conf)
        self.assertTrue(text.startswith("set -g prefix C-a\n"))
        self.assertIn(f'source-file "{self.repo}/tmux/tmux.conf"', text)
        self.assertIn("Everything is in place.", self.run_install("--yes"))
        self.run_install("--uninstall", "--yes")
        self.assertEqual(rd(conf), "set -g prefix C-a\n")

    def test_links_into_another_checkout_are_relinked_not_edited(self):
        other = os.path.join(os.path.dirname(self.repo), "other-clone")
        shutil.copytree(self.repo, other, symlinks=True)
        self.run_install("--yes", repo=other)
        out = self.run_install("--yes")
        self.assertNotIn("backup:", out)
        self.assertEqual(self.link_target(".tmux.conf"), os.path.join(self.repo, "tmux", "tmux.conf"))
        self.assertEqual(self.link_target(".claude/skills/unslop"), os.path.join(self.repo, "skills", "unslop"))
        self.assertNotIn("source-file", rd(os.path.join(other, "tmux", "tmux.conf")))

    def test_migrates_a_whole_directory_link_keeping_the_users_own_files(self):
        old = os.path.join(os.path.dirname(self.repo), "old-clone")
        shutil.copytree(self.repo, old, symlinks=True)
        git = ["git", "-C", old, "-c", "user.email=t@t", "-c", "user.name=t"]
        subprocess.run(["git", "init", "-q", old], check=True)
        subprocess.run(git + ["add", "-A"], check=True)
        subprocess.run(git + ["commit", "-q", "-m", "old"], check=True)
        os.makedirs(os.path.join(old, "skills", "my-skill"))
        wr(os.path.join(old, "skills", "my-skill", "SKILL.md"), "mine")
        os.makedirs(self.claude)
        os.symlink(os.path.join(old, "skills"), os.path.join(self.claude, "skills"))
        os.symlink(os.path.join(old, "agents"), os.path.join(self.claude, "agents"))
        out = self.run_install("--yes")
        self.assertNotIn("backup:", out)
        skills = os.path.join(self.claude, "skills")
        self.assertFalse(os.path.islink(skills))
        self.assertEqual(rd(os.path.join(skills, "my-skill", "SKILL.md")), "mine")
        self.assertEqual(self.link_target(".claude/skills/unslop"), os.path.join(self.repo, "skills", "unslop"))
        self.assertFalse(os.path.islink(os.path.join(self.claude, "agents")))
        self.assertEqual(self.link_target(".claude/agents/worker.md"), os.path.join(self.repo, "agents", "worker.md"))
        self.assertIn("Everything is in place.", self.run_install("--yes"))

    def test_tmux_xdg_config_is_not_shadowed(self):
        xdg = os.path.join(self.home, ".config", "tmux", "tmux.conf")
        os.makedirs(os.path.dirname(xdg))
        wr(xdg, "set -g mouse off\n")
        self.run_install("--yes")
        self.assertFalse(os.path.lexists(os.path.join(self.home, ".tmux.conf")))
        self.assertIn("source-file", rd(xdg))

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

    def test_uninstall_restores_backups_and_removes_defaults(self):
        open_claude = os.path.join(self.claude, "CLAUDE.md")
        os.makedirs(self.claude)
        wr(open_claude, "mine")
        self.write_settings({"theme": "light"})
        self.run_install("--yes")
        s = self.read_settings()
        s["permissions"]["allow"].append("Bash(ls:*)")
        self.write_settings(s)
        self.run_install("--uninstall", "--yes")
        self.assertEqual(rd(open_claude), "mine")
        self.assertEqual(sorted(os.listdir(os.path.join(self.claude, "skills"))), RECORDED)
        self.assertEqual(self.read_settings(), {"theme": "light", "permissions": {"allow": ["Bash(ls:*)"]}})
        self.assertFalse(os.path.exists(os.path.join(self.claude, "dotclaude-state.json")))


if __name__ == "__main__":
    unittest.main()
