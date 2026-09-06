import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "skills" / "viral-learn" / "scripts" / "feedback.py"
SPEC = importlib.util.spec_from_file_location("viral_learn_feedback", MODULE_PATH)
FEEDBACK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FEEDBACK)

FeedbackError = FEEDBACK.FeedbackError
append_event = FEEDBACK.append_event
compare_metric_events = FEEDBACK.compare_metric_events
list_lessons = FEEDBACK.list_lessons
load_events = FEEDBACK.load_events
make_editorial_event = FEEDBACK.make_editorial_event
make_lesson_event = FEEDBACK.make_lesson_event
make_lesson_status_event = FEEDBACK.make_lesson_status_event
make_metric_event = FEEDBACK.make_metric_event
metric_calculation = FEEDBACK.metric_calculation
validate_event = FEEDBACK.validate_event


RECORDED_AT = "2026-01-02T12:00:00Z"
WINDOW = {"start": "2026-01-01T00:00:00Z", "end": "2026-01-02T00:00:00Z"}


def metric_event(event_id="metric-1", numerator=12, denominator=100, **overrides):
    values = {
        "event_id": event_id,
        "recorded_at": RECORDED_AT,
        "artifact_id": "creative-1",
        "channel": "organic",
        "metric_name": "completed_views",
        "metric_definition": "platform completed-view count",
        "numerator": numerator,
        "denominator": denominator,
        "denominator_definition": "platform video starts",
        "window": WINDOW,
        "attribution": {"model": "platform_reported"},
        "cohort": {"platform": "example", "format": "short_video"},
        "source_class": "authorized_account",
        "provenance_refs": ["export:row-1"],
    }
    values.update(overrides)
    return make_metric_event(**values)


class FeedbackValidationTests(unittest.TestCase):
    def test_rejection_requires_desired_change_for_generic_input(self):
        event = make_editorial_event(
            "review-1", RECORDED_AT, "draft-1", "editor", "rejected",
            "Exact excerpt.", "The reason.", None, {"format": "short_video"}, ["review:1"],
        )
        with self.assertRaisesRegex(FeedbackError, "desired_change"):
            validate_event(event)

    def test_missing_metric_is_not_silently_zero(self):
        event = metric_event()
        del event["numerator"]
        with self.assertRaisesRegex(FeedbackError, "required even when null"):
            validate_event(event)

        unknown = metric_event(numerator=None, denominator=None)
        validate_event(unknown)
        self.assertEqual(metric_calculation(unknown), {"status": "unknown_input", "rate": None})

    def test_zero_is_data_but_zero_denominator_has_no_rate(self):
        zero_numerator = metric_event(numerator=0, denominator=40)
        self.assertEqual(metric_calculation(zero_numerator), {"status": "computed", "rate": 0})

        zero_denominator = metric_event(numerator=0, denominator=0)
        self.assertEqual(metric_calculation(zero_denominator), {"status": "zero_denominator", "rate": None})

    def test_negative_or_nonfinite_metric_is_rejected(self):
        for value in (-1, float("inf"), float("nan")):
            with self.subTest(value=value):
                with self.assertRaises(FeedbackError):
                    validate_event(metric_event(numerator=value))

    def test_incompatible_metric_definition_and_cohort_are_rejected(self):
        baseline = metric_event("metric-1")
        mixed_definition = metric_event("metric-2", metric_definition="three-second view count")
        mixed_cohort = metric_event(
            "metric-3", cohort={"platform": "example", "format": "image"}
        )
        for other in (mixed_definition, mixed_cohort):
            with self.subTest(event=other["event_id"]):
                with self.assertRaisesRegex(FeedbackError, "incompatible"):
                    compare_metric_events([baseline, other])

    def test_compatible_comparison_is_descriptive_and_keeps_unknown(self):
        result = compare_metric_events([
            metric_event("metric-1", numerator=20, denominator=100),
            metric_event("metric-2", numerator=None, denominator=100),
        ])
        self.assertEqual(result["snapshot_count"], 2)
        self.assertEqual(result["snapshots"][1]["calculation"]["status"], "unknown_input")
        self.assertIn("not evidence", result["interpretation_limit"])


class AppendOnlyTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.log = Path(self.tempdir.name) / "feedback.jsonl"

    def tearDown(self):
        self.tempdir.cleanup()

    def test_duplicate_event_id_does_not_overwrite_prior_bytes(self):
        first = make_editorial_event(
            "review-1", RECORDED_AT, "draft-1", "editor", "rejected",
            "A claim copied exactly.", "The claim has no cited support.",
            "Remove the unsupported claim.", {"format": "short_video"}, ["review:line-8"],
        )
        append_event(self.log, first)
        before = self.log.read_bytes()

        duplicate = dict(first)
        duplicate["reason"] = "This must never replace the stored review."
        with self.assertRaisesRegex(FeedbackError, "duplicate event_id"):
            append_event(self.log, duplicate)

        self.assertEqual(self.log.read_bytes(), before)
        self.assertEqual(load_events(self.log)[0]["exact_excerpt"], "A claim copied exactly.")

    def test_duplicate_lesson_id_is_rejected(self):
        first = make_lesson_event(
            "lesson-event-1", RECORDED_AT, "lesson-1", "State the proof source.",
            "candidate", "Two editorial reviews requested it.", {"format": "short_video"},
            ["review:1", "review:2"],
        )
        append_event(self.log, first)
        second = make_lesson_event(
            "lesson-event-2", RECORDED_AT, "lesson-1", "Different statement.",
            "hypothesis", "One observation.", {"format": "short_video"}, ["review:3"],
        )
        with self.assertRaisesRegex(FeedbackError, "duplicate lesson_id"):
            append_event(self.log, second)


class LessonWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.proposal = make_lesson_event(
            "lesson-event-1", RECORDED_AT, "lesson-1", "Open with the observable result.",
            "candidate", "Repeated direct editorial feedback.", {"channel": "paid"},
            ["review:alpha", "review:beta"],
        )

    def test_lesson_cannot_start_approved(self):
        invalid = dict(self.proposal, status="approved")
        with self.assertRaisesRegex(FeedbackError, "explicit status event"):
            validate_event(invalid)

    def test_scoped_promotion_preserves_broad_candidate(self):
        scoped = make_lesson_status_event(
            "decision-1", RECORDED_AT, "lesson-1", "approved",
            "Approved after direct review in this format.",
            {"channel": "paid", "format": "short_video"}, ["approval:1"],
        )
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "feedback.jsonl"
            append_event(log, self.proposal)
            append_event(log, scoped)
            listed = list_lessons(load_events(log))

        self.assertEqual(listed[0]["status"], "candidate")
        self.assertEqual(listed[0]["scoped_decisions"][0]["status"], "approved")
        self.assertEqual(listed[0]["scoped_decisions"][0]["scope"]["format"], "short_video")

    def test_promotion_cannot_escape_proposal_scope(self):
        escaped = make_lesson_status_event(
            "decision-1", RECORDED_AT, "lesson-1", "approved", "Requested by editor.",
            {"channel": "organic"}, ["approval:1"],
        )
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "feedback.jsonl"
            append_event(log, self.proposal)
            with self.assertRaisesRegex(FeedbackError, "preserve the proposal scope"):
                append_event(log, escaped)

    def test_public_engagement_never_creates_or_promotes_lesson(self):
        paid_public = metric_event(
            event_id="public-1", channel="paid", source_class="public_ad_library",
            numerator=999999, denominator=None,
        )
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "feedback.jsonl"
            append_event(log, paid_public)
            self.assertEqual(list_lessons(load_events(log)), [])


class CliTests(unittest.TestCase):
    def test_generic_json_append_and_validate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            log = root / "feedback.jsonl"
            event_file = root / "event.json"
            event_file.write_text(json.dumps(metric_event()), encoding="utf-8")
            append_result = subprocess.run(
                [sys.executable, str(REPO_ROOT / "tools" / "feedback.py"), "append",
                 "--log", str(log), "--event", str(event_file)],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(append_result.returncode, 0, append_result.stderr)
            validate_result = subprocess.run(
                [sys.executable, str(REPO_ROOT / "tools" / "feedback.py"), "validate-log",
                 "--log", str(log)],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(validate_result.returncode, 0, validate_result.stderr)
            self.assertEqual(json.loads(validate_result.stdout)["event_count"], 1)


if __name__ == "__main__":
    unittest.main()
