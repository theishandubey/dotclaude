import json
import os
import re
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESTRICTS_BUILT_INS = {"allowed-tools", "tools", "model", "effort"}


def rd(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def frontmatter(path):
    match = re.match(r"---\n(.*?)\n---\n", rd(path), re.S)
    assert match, f"{path} has no frontmatter"
    return dict(re.findall(r"^([A-Za-z-]+):\s*(.*)$", match.group(1), re.M))


def first_party_skills():
    skills = os.path.join(ROOT, "skills")
    return sorted(d for d in os.listdir(skills) if os.path.isfile(os.path.join(skills, d, "SKILL.md")))


def tracked_files():
    out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"],
                         cwd=ROOT, capture_output=True, text=True, check=True)
    return [f for f in out.stdout.splitlines() if os.path.isfile(os.path.join(ROOT, f))]


class AgentsTest(unittest.TestCase):
    def test_each_agent_is_named_for_its_file_and_fixes_only_model_and_effort(self):
        folder = os.path.join(ROOT, "agents")
        for name in sorted(os.listdir(folder)):
            with self.subTest(agent=name):
                meta = frontmatter(os.path.join(folder, name))
                self.assertEqual(meta.get("name") + ".md", name)
                self.assertEqual(set(meta), {"name", "description", "model", "effort"})
                self.assertIn(meta["model"], ("sonnet", "opus"))


class SkillsTest(unittest.TestCase):
    def test_each_skill_is_named_for_its_folder_and_says_when_to_use_it(self):
        for name in first_party_skills():
            with self.subTest(skill=name):
                meta = frontmatter(os.path.join(ROOT, "skills", name, "SKILL.md"))
                self.assertEqual(meta.get("name"), name)
                self.assertTrue(meta.get("description"))

    def test_no_skill_restricts_a_built_in_capability(self):
        for name in first_party_skills():
            with self.subTest(skill=name):
                meta = frontmatter(os.path.join(ROOT, "skills", name, "SKILL.md"))
                self.assertFalse(RESTRICTS_BUILT_INS & set(meta))

    def test_skill_links_point_at_files(self):
        for name in first_party_skills():
            folder = os.path.join(ROOT, "skills", name)
            for target in re.findall(r"\]\(([^)#:]+)\)", rd(os.path.join(folder, "SKILL.md"))):
                with self.subTest(skill=name, link=target):
                    self.assertTrue(os.path.isfile(os.path.join(folder, target)))

    def test_skill_evals_have_assertions_and_both_trigger_outcomes(self):
        for name in first_party_skills():
            evals = os.path.join(ROOT, "skills", name, "evals")
            if not os.path.isdir(evals):
                continue
            with self.subTest(skill=name):
                cases = json.loads(rd(os.path.join(evals, "evals.json")))["evals"]
                self.assertEqual(len({c["id"] for c in cases}), len(cases))
                self.assertTrue(all(c["prompt"] and c["assertions"] for c in cases))
                triggers = json.loads(rd(os.path.join(evals, "triggers.json")))
                self.assertEqual({t["should_trigger"] for t in triggers}, {True, False})

    def test_third_party_skills_are_recorded_not_committed(self):
        recorded = json.loads(rd(os.path.join(ROOT, "skills-lock.json")))["skills"]
        self.assertFalse(set(recorded) & set(first_party_skills()))
        for name, entry in recorded.items():
            with self.subTest(skill=name):
                self.assertTrue(entry.get("source"))


class FilesTest(unittest.TestCase):
    def test_no_em_dashes(self):
        for path in tracked_files():
            if path.endswith((".png", ".jpg", ".gif")):
                continue
            with self.subTest(path=path):
                self.assertNotIn(chr(0x2014), rd(os.path.join(ROOT, path)))

    def test_settings_keep_the_fixed_choices(self):
        settings = json.loads(rd(os.path.join(ROOT, "claude", "settings.json")))
        self.assertNotIn("plansDirectory", settings)
        self.assertNotIn("defaultMode", settings["permissions"])
        self.assertNotIn(os.path.expanduser("~"), json.dumps(settings))
        self.assertIs(settings["attribution"], False)
        self.assertEqual(settings["advisorModel"], "fable")


if __name__ == "__main__":
    unittest.main()
