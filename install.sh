#!/usr/bin/env bash
set -euo pipefail

repo="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
claude="$HOME/.claude"
tmux_dotfile="$HOME/.tmux.conf"
tmux_xdg="${XDG_CONFIG_HOME:-$HOME/.config}/tmux/tmux.conf"
tmux_source="$repo/tmux/tmux.conf"

usage() {
  cat <<EOF
Usage: install.sh [--dry-run] [--uninstall]

Links CLAUDE.md, settings.json, the agents and the skills from this checkout into ~/.claude,
and links ~/.tmux.conf when you have no tmux config yet.
Anything already where a link goes is removed, with a warning.

  --dry-run    print what would change and change nothing
  --uninstall  remove every link into this checkout
EOF
}

dry_run=0
uninstall=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) dry_run=1 ;;
    --uninstall) uninstall=1 ;;
    -h | --help) usage; exit 0 ;;
    *) echo "unknown option: $arg" >&2; usage >&2; exit 2 ;;
  esac
done

changes=0
short() { case "$1" in "$HOME"/*) echo "~${1#"$HOME"}" ;; *) echo "$1" ;; esac; }
say() { echo "  $1: $(short "$2")${3:+ $3}"; }
act() {
  changes=$((changes + 1))
  if [ "$dry_run" -eq 0 ]; then "$@"; fi
}
into_repo() { [ -L "$1" ] && case "$(readlink "$1")" in "$repo" | "$repo"/*) true ;; *) false ;; esac; }
broken() { [ -L "$1" ] && [ ! -e "$1" ]; }

unlink_path() {
  say "remove link" "$1"
  act rm -f "$1"
}

link() {
  local dest="$1" src="$2"
  if [ -L "$dest" ] && [ "$(readlink "$dest")" = "$src" ]; then
    return
  fi
  if [ -L "$dest" ] && ! into_repo "$dest" && ! broken "$dest"; then
    say "warn" "$dest" "links to $(short "$(readlink "$dest")"); replacing it"
  elif [ -e "$dest" ] && [ ! -L "$dest" ]; then
    say "warn" "$dest" "exists; removing it"
  fi
  say "link" "$dest" "-> $(short "$src")"
  act rm -rf "$dest"
  act mkdir -p "$(dirname "$dest")"
  act ln -s "$src" "$dest"
}

real_dir() {
  local dir="$1"
  if [ -L "$dir" ]; then
    say "warn" "$dir" "is a link to $(short "$(readlink "$dir")"); replacing it with a directory"
    act rm -f "$dir"
  fi
  if [ ! -d "$dir" ]; then
    say "create" "$dir"
    act mkdir -p "$dir"
  fi
}

each_link_in_claude() {
  local dir path
  for dir in "$claude" "$claude/agents" "$claude/skills"; do
    [ -d "$dir" ] && [ ! -L "$dir" ] || continue
    for path in "$dir"/* "$dir"/.[!.]*; do
      [ -L "$path" ] && echo "$path"
    done
  done
}

install() {
  real_dir "$claude/agents"
  real_dir "$claude/skills"
  local path name
  while IFS= read -r path; do
    if broken "$path" && { into_repo "$path" || [ "$(dirname "$path")" != "$claude" ]; }; then
      unlink_path "$path"
    fi
  done < <(each_link_in_claude)
  link "$claude/CLAUDE.md" "$repo/claude/CLAUDE.md"
  link "$claude/settings.json" "$repo/claude/settings.json"
  for path in "$repo"/agents/*.md; do
    [ -e "$path" ] || continue
    link "$claude/agents/$(basename "$path")" "$path"
  done
  for path in "$repo"/skills/*/SKILL.md; do
    [ -e "$path" ] || continue
    name="$(basename "$(dirname "$path")")"
    link "$claude/skills/$name" "$repo/skills/$name"
  done
  install_tmux
}

install_tmux() {
  if into_repo "$tmux_dotfile" || broken "$tmux_dotfile" || { [ ! -e "$tmux_dotfile" ] && [ ! -e "$tmux_xdg" ]; }; then
    link "$tmux_dotfile" "$tmux_source"
    return
  fi
  local conf="$tmux_dotfile"
  [ -e "$conf" ] || conf="$tmux_xdg"
  if ! grep -qF "$tmux_source" "$conf" 2>/dev/null; then
    say "note" "$conf" "is your own tmux config; to use this repo's, add:"
    echo "      source-file \"$tmux_source\""
  fi
}

uninstall() {
  local path
  while IFS= read -r path; do
    if into_repo "$path"; then
      unlink_path "$path"
    fi
  done < <(each_link_in_claude)
  if into_repo "$tmux_dotfile"; then
    unlink_path "$tmux_dotfile"
  fi
}

echo "dotclaude $([ "$uninstall" -eq 1 ] && echo uninstall || echo install) from $(short "$repo")"
if [ "$uninstall" -eq 1 ]; then uninstall; else install; fi
if [ "$changes" -eq 0 ]; then
  echo "Everything is in place."
elif [ "$dry_run" -eq 1 ]; then
  echo "Dry run: nothing was changed."
else
  echo "Done."
fi
