import importlib.util
import json
from pathlib import Path
import unittest
from unittest import mock


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "viral-research"
    / "scripts"
    / "media.py"
)
SPEC = importlib.util.spec_from_file_location("viral_media", MODULE_PATH)
MEDIA = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MEDIA)


class MediaInspectionTests(unittest.TestCase):
    @mock.patch.object(MEDIA.shutil, "which", return_value="/usr/bin/ffprobe")
    @mock.patch.object(MEDIA, "run")
    def test_missing_duration_is_a_controlled_error(self, mocked_run, _mocked_which):
        mocked_run.return_value.stdout = json.dumps(
            {
                "format": {"duration": None},
                "streams": [{"codec_type": "video", "duration": None}],
            }
        )
        with self.assertRaisesRegex(ValueError, "duration is unavailable"):
            MEDIA.inspect(Path("synthetic.mp4"))

    def test_tiny_interval_fails_before_materializing_huge_schedule(self):
        with self.assertRaisesRegex(ValueError, "Frame budget exceeded"):
            MEDIA.schedule(60.0, 0.000001, max_frames=360)

    def test_schedule_is_unique_sorted_and_within_budget(self):
        times = MEDIA.schedule(6.0, 2.0, max_frames=20)
        self.assertEqual(times, sorted(set(times)))
        self.assertLessEqual(len(times), 20)
        self.assertTrue(all(0 <= value < 6.0 for value in times))


if __name__ == "__main__":
    unittest.main()
