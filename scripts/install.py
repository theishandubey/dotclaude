#!/usr/bin/env python3
import argparse
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

REPO = os.path.realpath(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HOME = os.path.realpath(os.environ.get("HOME") or os.path.expanduser("~"))
CLAUDE = os.path.join(HOME, ".claude")
STATE = os.path.join(CLAUDE, "dotclaude-state.json")
BACKUPS = os.path.join(HOME, ".dotclaude-backups")
TMUX_MARK = "# dotclaude"
MANAGED_DIRS = ("agents", "skills")
SETTINGS_HANDED_TO_USER = ("enabledPlugins", "extraKnownMarketplaces")
LOCK = os.path.join(REPO, "skills-lock.json")
GLOBAL_LOCK = os.path.join(HOME, ".agents", ".skill-lock.json")
SKILLS_CLI = "skills@1.8.1"
MISSING = object()
HOOK_SCRIPT = re.compile(r"(?:\$HOME|\$\{HOME\}|~|" + re.escape(HOME) + r")/\.claude/hooks/([\w.-]+)")
COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def labelled(kind, text):
    colors = {"ok": "32", "change": "36", "backup": "33", "warn": "31"}
    label = f"\033[{colors[kind]}m{kind}:\033[0m" if COLOR else f"{kind}:"
    return f"  {label} {text}"


def say(kind, text):
    print(labelled(kind, text))


def short(path):
    return "~" + path[len(HOME):] if path.startswith(HOME + "/") else path


def into_repo(path):
    if not os.path.islink(path):
        return False
    target = os.path.realpath(path)
    return target == REPO or target.startswith(REPO + "/")


def from_any_checkout(path):
    if not os.path.islink(path):
        return False
    directory = os.path.dirname(os.path.realpath(path))
    while directory != os.path.dirname(directory):
        if all(os.path.exists(os.path.join(directory, m)) for m in ("install.sh", "claude/CLAUDE.md", "skills")):
            return True
        directory = os.path.dirname(directory)
    return False


def canon(value):
    return "<missing>" if value is MISSING else json.dumps(value, sort_keys=True)


def merge3(base, ours, theirs):
    if canon(ours) == canon(base):
        return theirs
    if canon(theirs) == canon(base):
        return ours
    if theirs is MISSING and isinstance(ours, (dict, list)) and type(base) is type(ours):
        merged = merge3(base, ours, type(ours)())
        return merged if merged else MISSING
    if isinstance(ours, dict) and isinstance(theirs, dict):
        base = base if isinstance(base, dict) else {}
        out = {}
        for key in list(ours) + [k for k in theirs if k not in ours]:
            value = merge3(base.get(key, MISSING), ours.get(key, MISSING), theirs.get(key, MISSING))
            if value is not MISSING:
                out[key] = value
        return out
    if isinstance(ours, list) and isinstance(theirs, list):
        base_set = {canon(x) for x in base} if isinstance(base, list) else set()
        theirs_set = {canon(x) for x in theirs}
        ours_set = {canon(x) for x in ours}
        kept = [x for x in ours if canon(x) in theirs_set or canon(x) not in base_set]
        added = [x for x in theirs if canon(x) not in ours_set and canon(x) not in base_set]
        return kept + added
    return ours


def load_json(path, default):
    if not os.path.lexists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    path = os.path.realpath(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    mode = os.stat(path).st_mode & 0o7777 if os.path.exists(path) else 0o644
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".dotclaude-")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    os.chmod(tmp, mode)
    os.replace(tmp, path)


class Group:
    def __init__(self, title):
        self.title = title
        self.lines = []
        self.actions = []


class Plan:
    def __init__(self, stamp):
        self.groups = []
        self.stamp = stamp

    def group(self, title):
        self.groups.append(Group(title))

    def ok(self, text):
        self.groups[-1].lines.append(labelled("ok", text))

    def warn(self, text):
        self.groups[-1].lines.append(labelled("warn", text))

    def note(self, text):
        self.groups[-1].lines.append(f"      {text}")

    def add(self, text, action, moves_aside=False):
        self.groups[-1].lines.append(labelled("backup" if moves_aside else "change", text))
        self.groups[-1].actions.append(action)

    def backup(self, path):
        dest = os.path.join(BACKUPS, self.stamp, os.path.relpath(path, HOME))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.move(path, dest)
        return dest


def first_party_skills():
    skills = os.path.join(REPO, "skills")
    return [n for n in sorted(os.listdir(skills)) if os.path.isfile(os.path.join(skills, n, "SKILL.md"))]


def desired_links():
    links = {os.path.join(CLAUDE, "CLAUDE.md"): os.path.join(REPO, "claude", "CLAUDE.md")}
    agents = os.path.join(REPO, "agents")
    for name in sorted(os.listdir(agents)):
        if name.endswith(".md"):
            links[os.path.join(CLAUDE, "agents", name)] = os.path.join(agents, name)
    for name in first_party_skills():
        links[os.path.join(CLAUDE, "skills", name)] = os.path.join(REPO, "skills", name)
    return links


def own_files(directory):
    names = [n for n in sorted(os.listdir(directory)) if not n.startswith(".") and n != "__pycache__"]
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=directory, capture_output=True, text=True, timeout=10)
    except OSError:
        return names
    if out.returncode != 0:
        return names
    tracked = {p.split("/", 1)[0] for p in out.stdout.split("\0") if p}
    return [n for n in names if n not in tracked]


def plan_managed_dir(plan, name):
    path = os.path.join(CLAUDE, name)
    if not os.path.islink(path):
        return False
    if into_repo(path) or from_any_checkout(path):
        old = os.path.realpath(path)
        keep = own_files(old) if os.path.isdir(old) else []

        def run():
            os.unlink(path)
            os.makedirs(path)
            for n in keep:
                src, dst = os.path.join(old, n), os.path.join(path, n)
                if os.path.isdir(src) and not os.path.islink(src):
                    shutil.copytree(src, dst, symlinks=True)
                else:
                    shutil.copy2(src, dst, follow_symlinks=False)

        extra = f", copying your own files from it: {', '.join(keep)}" if keep else ""
        plan.add(f"replace the link {short(path)} with a directory of links{extra}", run)
    else:
        def run():
            say("change", f"backed up {short(path)} to {short(plan.backup(path))}")
            os.makedirs(path)

        plan.add(f"back up the link {short(path)} and replace it with a directory of links", run, moves_aside=True)
    return True


def plan_link(plan, target, source, fresh=False):
    if not fresh and os.path.islink(target) and os.path.realpath(target) == os.path.realpath(source):
        plan.ok(short(target))
        return

    def make(backup=False):
        def run():
            if backup:
                say("change", f"backed up {short(target)} to {short(plan.backup(target))}")
            elif os.path.lexists(target):
                os.unlink(target)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            os.symlink(source, target)
        return run

    if fresh or not os.path.lexists(target):
        plan.add(f"link {short(target)} -> {short(source)}", make())
    elif into_repo(target) or from_any_checkout(target) or not os.path.exists(target):
        plan.add(f"relink {short(target)} -> {short(source)}", make())
    else:
        plan.add(f"back up {short(target)} and link it to {short(source)}", make(backup=True), moves_aside=True)


def stale_links(desired, include_dirs=False):
    found = []
    for directory in [CLAUDE] + [os.path.join(CLAUDE, d) for d in MANAGED_DIRS]:
        if os.path.islink(directory) or not os.path.isdir(directory):
            continue
        for name in sorted(os.listdir(directory)):
            path = os.path.join(directory, name)
            if directory == CLAUDE and name in MANAGED_DIRS and not include_dirs:
                continue
            if into_repo(path) and path not in desired:
                found.append(path)
    return found


def settings_diff(before, after):
    old, new = (json.dumps(x, indent=2).splitlines() for x in (before, after))
    return list(difflib.unified_diff(old, new, lineterm="", n=1))[2:]


def runs_a_missing_script(hook):
    scripts = [os.path.join(CLAUDE, "hooks", name) for name in HOOK_SCRIPT.findall(hook.get("command", ""))]
    return any(not os.path.exists(script) for script in scripts)


def without_dead_hooks(settings):
    events = {}
    for event, entries in settings.get("hooks", {}).items():
        kept = [dict(entry, hooks=[h for h in entry.get("hooks", []) if not runs_a_missing_script(h)])
                for entry in entries]
        kept = [entry for entry in kept if entry["hooks"]]
        if kept:
            events[event] = kept
    cleaned = {key: value for key, value in settings.items() if key != "hooks"}
    if events:
        cleaned["hooks"] = events
    return cleaned


def plan_settings(plan, uninstall=False):
    path = os.path.join(CLAUDE, "settings.json")
    user = load_json(path, {})
    state = load_json(STATE, None)
    base = dict(state.get("settings", {})) if state is not None else {}
    for key in SETTINGS_HANDED_TO_USER:
        base.pop(key, None)
    defaults = {} if uninstall else load_json(os.path.join(REPO, "claude", "settings.json"), {})
    merged = merge3(base, user, defaults)
    if merged is MISSING:
        merged = {}
    if not uninstall:
        merged = without_dead_hooks(merged)
    changed = canon(merged) != canon(user)
    state_changed = uninstall and state is not None or not uninstall and (state is None or canon(base) != canon(defaults))

    def run():
        if changed:
            write_json(path, merged)
        if uninstall:
            if os.path.exists(STATE):
                os.unlink(STATE)
        else:
            write_json(STATE, {"repo": REPO, "settings": defaults})

    if changed:
        keys = sorted({k for k in set(merged) | set(user) if canon(merged.get(k)) != canon(user.get(k))})
        verb = "remove this repo's defaults from" if uninstall else "merge defaults into"
        plan.add(f"{verb} {short(path)} ({', '.join(keys)})", run)
        for line in settings_diff(user, merged):
            plan.note(line)
    elif state_changed:
        plan.add("record the applied settings defaults", run)
    else:
        plan.ok(short(path))


def tmux_paths():
    xdg = os.environ.get("XDG_CONFIG_HOME") or os.path.join(HOME, ".config")
    return os.path.join(HOME, ".tmux.conf"), os.path.join(xdg, "tmux", "tmux.conf")


def source_line():
    return f'source-file "{os.path.join(REPO, "tmux", "tmux.conf")}" {TMUX_MARK}\n'


def plan_tmux(plan, uninstall=False):
    dotfile, xdg = tmux_paths()
    source = os.path.join(REPO, "tmux", "tmux.conf")
    if uninstall:
        if into_repo(dotfile):
            plan.add(f"remove link {short(dotfile)}", lambda: os.unlink(dotfile))
        for conf in (dotfile, xdg):
            if os.path.isfile(conf) and not into_repo(conf):
                lines = open(conf, encoding="utf-8").readlines()
                if any(l.rstrip().endswith(TMUX_MARK) for l in lines):
                    def strip(conf=conf, lines=lines):
                        with open(os.path.realpath(conf), "w", encoding="utf-8") as f:
                            f.writelines(l for l in lines if not l.rstrip().endswith(TMUX_MARK))
                    plan.add(f"remove the dotclaude line from {short(conf)}", strip)
        return
    if into_repo(dotfile) or from_any_checkout(dotfile) or (os.path.islink(dotfile) and not os.path.exists(dotfile)):
        plan_link(plan, dotfile, source)
        return
    active = dotfile if os.path.lexists(dotfile) else xdg if os.path.lexists(xdg) else None
    if active is None:
        plan_link(plan, dotfile, source)
        return
    text = open(active, encoding="utf-8").read()
    if source_line().strip() in text:
        plan.ok(f"{short(active)} sources tmux/tmux.conf")
        return
    lines = [l for l in text.splitlines(keepends=True) if not l.rstrip().endswith(TMUX_MARK)]

    def append():
        with open(os.path.realpath(active), "w", encoding="utf-8") as f:
            f.writelines(lines)
            if lines and not lines[-1].endswith("\n"):
                f.write("\n")
            f.write(source_line())

    plan.add(f"add a source-file line for tmux/tmux.conf to {short(active)}", append)


def newest_backup(path):
    rel = os.path.relpath(path, HOME)
    if not os.path.isdir(BACKUPS):
        return None
    for stamp in sorted(os.listdir(BACKUPS), reverse=True):
        candidate = os.path.join(BACKUPS, stamp, rel)
        if os.path.lexists(candidate):
            return candidate
    return None


def plan_unlink(plan, path, restore):
    backup = newest_backup(path) if restore else None

    def run():
        os.unlink(path)
        if backup:
            shutil.move(backup, path)

    if backup:
        plan.add(f"remove link {short(path)} and restore {short(backup)}", run)
    else:
        plan.add(f"remove link {short(path)}", run)


def installed_by_the_skills_cli(name):
    path = os.path.join(CLAUDE, "skills", name)
    return os.path.isfile(os.path.join(path, "SKILL.md")) and not (into_repo(path) or from_any_checkout(path))


def skills_cli_add(name, source, assume_yes):
    command = ["npx", *(["--yes"] if assume_yes else []), SKILLS_CLI, "add", source, "-g", "-a", "claude-code", "-s", name]
    if assume_yes:
        command.append("-y")
    return command


def plan_third_party(plan, assume_yes):
    recorded = load_json(LOCK, {}).get("skills", {})
    first_party = first_party_skills()
    have_npx = shutil.which("npx") is not None
    for name, entry in sorted(recorded.items()):
        if name in first_party:
            plan.warn(f"{name} is recorded in skills-lock.json but this repo ships its own; skipped")
        elif installed_by_the_skills_cli(name):
            plan.ok(f"{name} ({entry['source']})")
        elif not have_npx:
            plan.warn(f"{name} is missing and npx is not installed; skipped")
        else:
            command = skills_cli_add(name, entry["source"], assume_yes)

            def run(name=name, command=command):
                if subprocess.run(command).returncode != 0:
                    say("warn", f"{name} was not installed: {' '.join(command)} failed")

            plan.add(f"install {name}: {' '.join(command)}", run)


def unrecorded_skills():
    installed = load_json(GLOBAL_LOCK, {}).get("skills", {})
    skip = set(load_json(LOCK, {}).get("skills", {})) | set(first_party_skills())
    return {name: installed[name] for name in sorted(installed) if name not in skip}


def record_chosen(extras):
    answer = prompt('Record which? Names separated by spaces, "all", or nothing: ')
    chosen = list(extras) if answer == "all" else [n for n in answer.split() if n in extras]
    if not chosen:
        return
    lock = load_json(LOCK, {"version": 1, "skills": {}})
    for name in chosen:
        lock["skills"][name] = {k: extras[name][k] for k in ("source", "sourceType", "skillPath") if k in extras[name]}
    write_json(LOCK, lock)
    say("change", f"recorded {', '.join(chosen)} in skills-lock.json")


def plan_extras(plan, interactive):
    extras = unrecorded_skills()
    if not extras:
        return
    plan.group("Installed skills not recorded in skills-lock.json")
    for name, entry in extras.items():
        plan.note(f"{name} ({entry.get('source', 'unknown source')})")
    if interactive:
        plan.add("choose which of these to record", lambda: record_chosen(extras))
    else:
        plan.note("run ./install.sh from a terminal without --yes to record any of them")


def prompt(question):
    try:
        return input(question).strip().lower()
    except EOFError:
        return ""


def decide(group):
    while True:
        answer = prompt(f"{group.title}: apply? [y]es / [s]kip / [q]uit: ")
        if not answer:
            return "quit"
        for choice in ("yes", "skip", "quit"):
            if choice.startswith(answer):
                return choice


def carry_out(plan, assume_yes, dry_run):
    for group in plan.groups:
        if not group.lines:
            continue
        print(group.title)
        print("\n".join(group.lines))
        if dry_run or not group.actions:
            continue
        choice = "yes" if assume_yes else decide(group)
        if choice == "quit":
            print("Stopped; the remaining steps were not applied.")
            return
        if choice == "yes":
            for action in group.actions:
                action()
    if not dry_run:
        print("Done.")


def main(argv):
    parser = argparse.ArgumentParser(prog="install.sh", description="Link this Claude Code config into ~/.claude.")
    parser.add_argument("--dry-run", action="store_true", help="print the plan and change nothing")
    parser.add_argument("-y", "--yes", action="store_true", help="apply every step without asking")
    parser.add_argument("--uninstall", action="store_true", help="remove the links and this repo's settings defaults")
    args = parser.parse_args(argv)
    on_terminal = sys.stdin.isatty()
    dry_run = args.dry_run or not (args.yes or on_terminal)

    plan = Plan(time.strftime("%Y%m%d-%H%M%S"))
    print(f"dotclaude {'uninstall' if args.uninstall else 'install'} from {short(REPO)}")
    try:
        if args.uninstall:
            plan.group("Links")
            for path in stale_links({}, include_dirs=True):
                plan_unlink(plan, path, restore=True)
        else:
            plan.group("Agents, skills and CLAUDE.md")
            desired = desired_links()
            migrating = {os.path.join(CLAUDE, d) for d in MANAGED_DIRS if plan_managed_dir(plan, d)}
            for target, source in desired.items():
                plan_link(plan, target, source, fresh=os.path.dirname(target) in migrating)
            for path in stale_links(desired):
                plan_unlink(plan, path, restore=False)
        plan.group("Settings")
        plan_settings(plan, uninstall=args.uninstall)
        plan.group("tmux")
        plan_tmux(plan, uninstall=args.uninstall)
        if not args.uninstall:
            plan.group("Third-party skills")
            plan_third_party(plan, args.yes)
            plan_extras(plan, interactive=on_terminal and not args.yes and not args.dry_run)
    except (OSError, ValueError) as e:
        print(f"error: {e}; nothing was changed.", file=sys.stderr)
        return 1

    if not any(group.actions for group in plan.groups):
        carry_out(plan, assume_yes=False, dry_run=True)
        print("Everything is in place.")
    elif dry_run:
        carry_out(plan, assume_yes=False, dry_run=True)
        if not args.dry_run:
            print("No terminal and no --yes, so this ran as a dry run.")
        print("Dry run: nothing was changed.")
    else:
        carry_out(plan, args.yes, dry_run=False)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
