import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


MODULE_PATH = Path(__file__).parents[1] / "skills" / "viral-research" / "scripts" / "corpus.py"
SPEC = importlib.util.spec_from_file_location("viral_corpus", MODULE_PATH)
CORPUS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CORPUS)


def record(
    record_id,
    views,
    *,
    creator="creator-a",
    platform="example-platform",
    format_name="short_video",
    distribution="organic",
    metric_definition="platform_play_count",
    published_at="2026-01-10T12:00:00Z",
    source_url=None,
    raw_ref=None,
    source_type="public_platform",
):
    return {
        "id": record_id,
        "platform": platform,
        "creator": creator,
        "format": format_name,
        "distribution": distribution,
        "source_url": source_url or "https://example.invalid/video/{}".format(record_id),
        "published_at": published_at,
        "captured_at": "2026-03-15T12:00:00Z",
        "views": views,
        "view_metric_definition": metric_definition,
        "likes": None,
        "comments": None,
        "transcript_coverage": {"status": "full", "method": "synthetic fixture", "notes": None},
        "visual_coverage": {"status": "none", "method": None, "notes": None},
        "audio_coverage": {"status": "none", "method": None, "notes": None},
        "provenance": {
            "source_type": source_type,
            "collector": "synthetic test",
            "retrieved_at": "2026-03-15T12:00:00Z",
            "request_ref": None,
        },
        "raw_ref": raw_ref or "raw/{}.json".format(record_id),
        "title": "Fixture {}".format(record_id),
        "caption": "A generic test caption.",
        "transcript": "A generic test transcript.",
    }


def window():
    return CORPUS.CohortWindow(published_start="2026-01-01", published_end="2026-01-31")


class ValidationTests(unittest.TestCase):
    def test_missing_metric_key_is_error_but_null_is_unknown_not_zero(self):
        missing = record("missing-views", 10)
        del missing["views"]
        missing_report = CORPUS.validate_records([missing])
        self.assertFalse(missing_report["valid"])
        self.assertIn("views is required", [item["message"] for item in missing_report["errors"]])

        unknown = record("unknown-views", None)
        zero = record("known-zero", 0)
        report = CORPUS.validate_records([unknown, zero])
        self.assertTrue(report["valid"])
        self.assertIn("unknown_views", [item["code"] for item in report["warnings"]])
        comparison = CORPUS.compare_cohorts([unknown, zero], window())
        cohort = comparison["cohorts"][0]
        self.assertEqual(2, cohort["deduplicated_denominator"])
        self.assertEqual(1, cohort["known_view_sample_size"])
        self.assertEqual(0, cohort["median"])

    def test_caption_does_not_infer_visual_coverage(self):
        item = record("caption-only", 5)
        item["caption"] = "The caption describes a close-up."
        report = CORPUS.validate_records([item])
        self.assertTrue(report["valid"])
        self.assertIn("caption_not_visual_evidence", [warning["code"] for warning in report["warnings"]])
        self.assertEqual("none", item["visual_coverage"]["status"])

    def test_duplicate_ids_error_and_duplicate_sources_are_flagged(self):
        duplicate_id_a = record("same-id", 1, source_url="https://example.invalid/a")
        duplicate_id_b = record("same-id", 2, source_url="https://example.invalid/b")
        report = CORPUS.validate_records([duplicate_id_a, duplicate_id_b])
        self.assertFalse(report["valid"])
        self.assertIn("duplicate_id", [error["code"] for error in report["errors"]])

        first = record("source-a", 1, source_url="https://example.invalid/shared/")
        second = record("source-b", 999, source_url="https://EXAMPLE.invalid/shared")
        report = CORPUS.validate_records([first, second])
        self.assertTrue(report["valid"])
        self.assertIn("duplicate_source_url", [warning["code"] for warning in report["warnings"]])
        deduped, duplicates = CORPUS.deduplicate_records([second, first])
        self.assertEqual(["source-a"], [item["id"] for item in deduped])
        self.assertEqual(["source-b"], duplicates[0]["dropped_ids"])

        raw_first = record("raw-a", 4, source_url="https://example.invalid/raw-a", raw_ref="raw/shared.json")
        raw_second = record("raw-b", 5, source_url="https://example.invalid/raw-b", raw_ref="raw/shared.json")
        deduped, duplicates = CORPUS.deduplicate_records([raw_second, raw_first])
        self.assertEqual(["raw-a"], [item["id"] for item in deduped])
        self.assertEqual(["raw-b"], duplicates[0]["dropped_ids"])


class ComparisonTests(unittest.TestCase):
    def test_mixed_metric_definitions_are_partitioned_and_flagged(self):
        records = [
            record("plays-1", 10, metric_definition="platform_play_count"),
            record("plays-2", 20, metric_definition="platform_play_count"),
            record("reach-1", 100, metric_definition="account_export_reach"),
        ]
        cohort = CORPUS.compare_cohorts(records, window())["cohorts"][0]
        self.assertIn("mixed_view_metric_definitions", cohort["flags"])
        self.assertIsNone(cohort["median"])
        self.assertEqual(2, len(cohort["metric_groups"]))
        medians = {group["view_metric_definition"]: group["median"] for group in cohort["metric_groups"]}
        self.assertEqual(15.0, medians["platform_play_count"])
        self.assertEqual(100, medians["account_export_reach"])

    def test_zero_median_has_no_infinite_or_invented_relative_value(self):
        records = [record("zero-a", 0), record("zero-b", 0), record("ten", 10)]
        cohort = CORPUS.compare_cohorts(records, window())["cohorts"][0]
        group = cohort["metric_groups"][0]
        self.assertEqual(0, group["median"])
        self.assertTrue(group["zero_median"])
        self.assertIn("zero_median:platform_play_count", cohort["flags"])
        self.assertEqual([None, None, None], [item["relative_to_median"] for item in group["records"]])

    def test_small_cohort_and_denominators_are_explicit(self):
        records = [record("one", 1), record("two", 2)]
        cohort = CORPUS.compare_cohorts(records, window(), small_cohort_threshold=3)["cohorts"][0]
        self.assertIn("small_cohort", cohort["flags"])
        self.assertEqual(2, cohort["denominator"])
        self.assertEqual(2, cohort["deduplicated_denominator"])
        self.assertEqual(2, cohort["known_view_sample_size"])

    def test_cohorts_never_mix_creator_platform_format_or_distribution(self):
        records = [
            record("a-organic", 1),
            record("b-organic", 2, creator="creator-b"),
            record("a-image", 3, format_name="image_ad"),
            record("a-paid", 4, distribution="paid"),
            record("outside-date", 5, published_at="2026-02-10T12:00:00Z"),
        ]
        result = CORPUS.compare_cohorts(records, window())
        self.assertEqual(4, result["cohort_count"])
        self.assertEqual(4, sum(item["denominator"] for item in result["cohorts"]))
        keys = {
            (item["cohort"]["creator"], item["cohort"]["platform"], item["cohort"]["format"], item["cohort"]["distribution"])
            for item in result["cohorts"]
        }
        self.assertEqual(4, len(keys))

    def test_public_paid_library_never_gets_profitability_claim(self):
        item = record("paid-library", 100, distribution="paid", source_type="public_ad_library")
        cohort = CORPUS.compare_cohorts([item], window())["cohorts"][0]
        self.assertIn("public_ad_library_no_profitability_inference", cohort["flags"])
        self.assertIn("does not establish profitability", cohort["interpretation"])


class SamplingAndBlindTests(unittest.TestCase):
    def test_sampling_is_deterministic_deduplicated_and_band_disjoint(self):
        records = [record("sample-{}".format(index), views) for index, views in enumerate([1, 2, 3, 4, 5, 6, 7])]
        duplicate = record(
            "sample-duplicate",
            1000,
            source_url=records[0]["source_url"],
            raw_ref="raw/different.json",
        )
        records.append(duplicate)
        first = CORPUS.sample_cohorts(records, window(), per_band=1)
        second = CORPUS.sample_cohorts(list(reversed(records)), window(), per_band=1)
        first_pairs = [(item["id"], item["sample_band"]) for item in first["samples"]]
        second_pairs = [(item["id"], item["sample_band"]) for item in second["samples"]]
        self.assertEqual(first_pairs, second_pairs)
        self.assertEqual(3, len(first_pairs))
        self.assertEqual(3, len({item[0] for item in first_pairs}))
        self.assertNotIn("sample-duplicate", [item[0] for item in first_pairs])
        self.assertEqual({"low", "typical", "high"}, {item[1] for item in first_pairs})

    def test_blind_packet_strips_performance_identity_rank_and_filenames(self):
        records = [record("opaque-source-{}".format(index), views) for index, views in enumerate([10, 20, 30, 40, 50])]
        records[0]["raw_ref"] = "raw/high-winner-file.mp4"
        records[0]["title"] = "Top outlier winner"
        records[0]["transcript"] = "The editor called this high-winner-file.mp4 and another-top-take.mov during review."
        sample = CORPUS.sample_cohorts(records, window(), per_band=1)
        packet, mapping = CORPUS.build_blind_packet(records, sample, salt="test-salt")
        CORPUS.assert_blind_packet(packet)
        encoded_packet = json.dumps(packet)
        for forbidden in (
            "opaque-source-",
            "high-winner-file.mp4",
            "another-top-take.mov",
            "Top outlier winner",
            "source_url",
            '"views"',
            '"likes"',
            '"comments"',
            '"rank"',
            '"outlier"',
            '"sample_band"',
            '"creator"',
            '"raw_ref"',
        ):
            self.assertNotIn(forbidden, encoded_packet)
        encoded_mapping = json.dumps(mapping)
        self.assertIn("sample_band", encoded_mapping)
        self.assertIn("source_url", encoded_mapping)
        self.assertIn("views", encoded_mapping)
        self.assertEqual(packet["record_count"], mapping["record_count"])

    def test_blind_cli_writes_separate_files(self):
        records = [record("cli-{}".format(index), views) for index, views in enumerate([1, 2, 3])]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "corpus.json"
            packet_path = root / "packet.json"
            mapping_path = root / "mapping.private.json"
            input_path.write_text(json.dumps(records), encoding="utf-8")
            result = CORPUS.main(
                [
                    "blind",
                    str(input_path),
                    "--published-start",
                    "2026-01-01",
                    "--published-end",
                    "2026-01-31",
                    "--packet-out",
                    str(packet_path),
                    "--mapping-out",
                    str(mapping_path),
                ]
            )
            self.assertEqual(0, result)
            self.assertTrue(packet_path.exists())
            self.assertTrue(mapping_path.exists())
            self.assertNotIn("views", packet_path.read_text(encoding="utf-8"))
            self.assertIn("views", mapping_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
