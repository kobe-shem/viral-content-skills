import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("suite_install", Path(__file__).resolve().parents[1] / "tools" / "install.py")
INSTALL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INSTALL)


class InstallerTests(unittest.TestCase):
    def source(self, root):
        source = root / "source"
        for name in INSTALL.NAMES:
            directory = source / name
            directory.mkdir(parents=True)
            (directory / "SKILL.md").write_text("---\nname: " + name + "\n---\n")
        return source

    def test_installs_all_siblings_and_backs_up_owned_update(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = self.source(root), root / "skills"
            first = INSTALL.install(source, target)
            self.assertEqual(set(first["hashes"]), set(INSTALL.NAMES))
            prior = (target / "viral-script" / "SKILL.md").read_text()
            (source / "viral-script" / "SKILL.md").write_text(prior + "new version\n")
            second = INSTALL.install(source, target, True)
            self.assertEqual((Path(second["backup"]) / "viral-script" / "SKILL.md").read_text(), prior)
            self.assertIn("new version", (target / "viral-script" / "SKILL.md").read_text())

    def test_preserves_unrelated_skill_before_any_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = self.source(root), root / "skills"
            (target / "viral-script").mkdir(parents=True)
            (target / "viral-script" / "SKILL.md").write_text("user's skill")
            with self.assertRaises(ValueError):
                INSTALL.install(source, target, True)
            self.assertFalse((target / "viral-content").exists())
            self.assertEqual((target / "viral-script" / "SKILL.md").read_text(), "user's skill")

    def test_missing_source_preserves_prior_install(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = self.source(root), root / "skills"
            INSTALL.install(source, target)
            before = INSTALL.tree_hash(target / "viral-content")
            (source / "viral-learn" / "SKILL.md").unlink()
            with self.assertRaises(ValueError):
                INSTALL.install(source, target, True)
            self.assertEqual(before, INSTALL.tree_hash(target / "viral-content"))

    def test_actual_install_contains_runnable_feedback_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "skills"
            source = Path(__file__).resolve().parents[1] / "skills"
            INSTALL.install(source, target)
            cli = target / "viral-learn" / "scripts" / "feedback.py"
            result = subprocess.run(
                [sys.executable, str(cli), "--help"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("editorial-add", result.stdout)


if __name__ == "__main__":
    unittest.main()
