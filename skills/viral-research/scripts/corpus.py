#!/usr/bin/env python3
"""Validate, compare, sample, and blind a normalized creative corpus.

Python 3.9+, standard library only. The module is both an importable library and a
CLI. It never calls a provider API and never infers profitability from public ad
library records.
"""

import argparse
import copy
import hashlib
import json
import math
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
from urllib.parse import urlsplit, urlunsplit


REQUIRED_FIELDS = (
    "id",
    "platform",
    "creator",
    "format",
    "distribution",
    "source_url",
    "published_at",
    "captured_at",
    "views",
    "view_metric_definition",
    "likes",
    "comments",
    "transcript_coverage",
    "visual_coverage",
    "audio_coverage",
    "provenance",
    "raw_ref",
)

DISTRIBUTIONS = {"organic", "paid", "unknown"}
COVERAGE_STATUSES = {
    "transcript": {"none", "partial", "full"},
    "visual": {"none", "opening_only", "sampled", "full"},
    "audio": {"none", "partial", "full"},
}
PROVENANCE_SOURCE_TYPES = {
    "first_party_export",
    "public_platform",
    "public_ad_library",
    "provider",
    "manual",
    "other",
}
CREATIVE_FIELDS = (
    "caption",
    "transcript",
    "on_screen_text",
    "visual_observations",
    "audio_observations",
)
PRIVATE_OR_PERFORMANCE_KEYS = {
    "id",
    "creator",
    "source_url",
    "published_at",
    "captured_at",
    "views",
    "view_metric_definition",
    "likes",
    "comments",
    "rank",
    "outlier",
    "outlier_status",
    "outlier_score",
    "performance",
    "sample_band",
    "source_filename",
    "filename",
    "path",
    "raw_ref",
    "provenance",
    "title",
}


class CorpusError(ValueError):
    """Raised for invalid corpus configuration or unusable input."""


def _issue(level: str, code: str, message: str, record_id: Optional[str] = None) -> Dict[str, Any]:
    result = {"level": level, "code": code, "message": message}
    if record_id is not None:
        result["record_id"] = record_id
    return result


def _parse_datetime(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise CorpusError("{} must be a non-empty ISO-8601 string".format(field))
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise CorpusError("{} is not valid ISO-8601: {}".format(field, value)) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise CorpusError("{} must include a UTC offset or Z".format(field))
    return parsed.astimezone(timezone.utc)


def _parse_boundary(value: Optional[str], end: bool = False) -> Optional[datetime]:
    if value is None:
        return None
    try:
        if len(value) == 10:
            parsed_date = date.fromisoformat(value)
            boundary_time = time.max if end else time.min
            return datetime.combine(parsed_date, boundary_time, tzinfo=timezone.utc)
        return _parse_datetime(value, "cohort boundary")
    except ValueError as exc:
        raise CorpusError("invalid date boundary: {}".format(value)) from exc


def _is_nonnegative_integer_or_null(value: Any) -> bool:
    return value is None or (isinstance(value, int) and not isinstance(value, bool) and value >= 0)


def _validate_coverage(record_id: str, field: str, value: Any, modality: str) -> List[Dict[str, Any]]:
    issues = []
    if not isinstance(value, dict):
        return [_issue("error", "invalid_coverage", "{} must be an object".format(field), record_id)]
    status = value.get("status")
    if status not in COVERAGE_STATUSES[modality]:
        issues.append(
            _issue(
                "error",
                "invalid_coverage_status",
                "{}.status must be one of {}".format(field, sorted(COVERAGE_STATUSES[modality])),
                record_id,
            )
        )
    for name in ("method", "notes"):
        if name in value and value[name] is not None and not isinstance(value[name], str):
            issues.append(_issue("error", "invalid_coverage", "{}.{} must be string or null".format(field, name), record_id))
    return issues


def _validate_provenance(record_id: str, value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, dict):
        return [_issue("error", "invalid_provenance", "provenance must be an object", record_id)]
    issues = []
    for field in ("source_type", "collector", "retrieved_at"):
        if field not in value:
            issues.append(_issue("error", "missing_provenance_field", "provenance.{} is required".format(field), record_id))
    if value.get("source_type") not in PROVENANCE_SOURCE_TYPES:
        issues.append(
            _issue(
                "error",
                "invalid_provenance_source_type",
                "provenance.source_type must be one of {}".format(sorted(PROVENANCE_SOURCE_TYPES)),
                record_id,
            )
        )
    if "collector" in value and (not isinstance(value["collector"], str) or not value["collector"].strip()):
        issues.append(_issue("error", "invalid_provenance", "provenance.collector must be a non-empty string", record_id))
    if "retrieved_at" in value:
        try:
            _parse_datetime(value["retrieved_at"], "provenance.retrieved_at")
        except CorpusError as exc:
            issues.append(_issue("error", "invalid_datetime", str(exc), record_id))
    if "request_ref" in value and value["request_ref"] is not None and not isinstance(value["request_ref"], str):
        issues.append(_issue("error", "invalid_provenance", "provenance.request_ref must be string or null", record_id))
    return issues


def normalize_source_url(value: str) -> str:
    """Normalize only URL details that are safe for exact duplicate detection."""
    parts = urlsplit(value.strip())
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, ""))


def validate_records(records: Sequence[Any]) -> Dict[str, Any]:
    """Return validation errors and warnings without mutating input records."""
    issues: List[Dict[str, Any]] = []
    ids: Dict[str, List[int]] = defaultdict(list)
    urls: Dict[str, List[str]] = defaultdict(list)
    raw_refs: Dict[str, List[str]] = defaultdict(list)

    for index, raw_record in enumerate(records):
        if not isinstance(raw_record, dict):
            issues.append(_issue("error", "invalid_record", "record {} must be an object".format(index)))
            continue
        record = raw_record
        provisional_id = record.get("id")
        record_id = provisional_id if isinstance(provisional_id, str) and provisional_id else "index:{}".format(index)
        for field in REQUIRED_FIELDS:
            if field not in record:
                issues.append(_issue("error", "missing_field", "{} is required".format(field), record_id))

        for field in ("id", "platform", "creator", "format", "source_url", "view_metric_definition"):
            if field in record and (not isinstance(record[field], str) or not record[field].strip()):
                issues.append(_issue("error", "invalid_string", "{} must be a non-empty string".format(field), record_id))

        if isinstance(provisional_id, str) and provisional_id.strip():
            ids[provisional_id].append(index)
        if record.get("distribution") not in DISTRIBUTIONS:
            issues.append(
                _issue(
                    "error",
                    "invalid_distribution",
                    "distribution must be one of {}".format(sorted(DISTRIBUTIONS)),
                    record_id,
                )
            )

        source_url = record.get("source_url")
        if isinstance(source_url, str) and source_url.strip():
            parsed_url = urlsplit(source_url)
            if parsed_url.scheme not in ("http", "https") or not parsed_url.netloc:
                issues.append(_issue("error", "invalid_source_url", "source_url must be an http(s) URL", record_id))
            else:
                urls[normalize_source_url(source_url)].append(record_id)

        parsed_dates = {}
        for field in ("published_at", "captured_at"):
            if field in record:
                try:
                    parsed_dates[field] = _parse_datetime(record[field], field)
                except CorpusError as exc:
                    issues.append(_issue("error", "invalid_datetime", str(exc), record_id))
        if set(parsed_dates) == {"published_at", "captured_at"} and parsed_dates["published_at"] > parsed_dates["captured_at"]:
            issues.append(_issue("error", "capture_before_publish", "captured_at cannot precede published_at", record_id))

        for field in ("views", "likes", "comments"):
            if field in record and not _is_nonnegative_integer_or_null(record[field]):
                issues.append(_issue("error", "invalid_metric", "{} must be a non-negative integer or null".format(field), record_id))

        if record.get("views") is None and "views" in record:
            issues.append(_issue("warning", "unknown_views", "views is unknown and will be excluded from performance calculations", record_id))

        if "transcript_coverage" in record:
            issues.extend(_validate_coverage(record_id, "transcript_coverage", record["transcript_coverage"], "transcript"))
        if "visual_coverage" in record:
            issues.extend(_validate_coverage(record_id, "visual_coverage", record["visual_coverage"], "visual"))
        if "audio_coverage" in record:
            issues.extend(_validate_coverage(record_id, "audio_coverage", record["audio_coverage"], "audio"))
        if "provenance" in record:
            issues.extend(_validate_provenance(record_id, record["provenance"]))

        raw_ref = record.get("raw_ref")
        if raw_ref is not None and not isinstance(raw_ref, str):
            issues.append(_issue("error", "invalid_raw_ref", "raw_ref must be a string or null", record_id))
        elif isinstance(raw_ref, str) and raw_ref.strip():
            raw_refs[raw_ref.strip()].append(record_id)

        # Modality coverage is explicit. Text availability never promotes visual/audio status.
        if record.get("caption") and isinstance(record.get("visual_coverage"), dict) and record["visual_coverage"].get("status") == "none":
            issues.append(
                _issue(
                    "warning",
                    "caption_not_visual_evidence",
                    "caption exists while visual coverage is none; visual facts remain unknown",
                    record_id,
                )
            )

    for duplicate_id, indexes in sorted(ids.items()):
        if len(indexes) > 1:
            issues.append(_issue("error", "duplicate_id", "id appears {} times".format(len(indexes)), duplicate_id))
    for normalized_url, record_ids in sorted(urls.items()):
        if len(record_ids) > 1:
            issues.append(
                _issue(
                    "warning",
                    "duplicate_source_url",
                    "same normalized source_url used by: {}".format(", ".join(sorted(record_ids))),
                )
            )
    for raw_ref, record_ids in sorted(raw_refs.items()):
        if len(record_ids) > 1:
            issues.append(
                _issue(
                    "warning",
                    "duplicate_raw_ref",
                    "same raw_ref used by: {}".format(", ".join(sorted(record_ids))),
                )
            )

    errors = [issue for issue in issues if issue["level"] == "error"]
    warnings = [issue for issue in issues if issue["level"] == "warning"]
    return {
        "valid": not errors,
        "record_count": len(records),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }


def assert_valid_records(records: Sequence[Any]) -> None:
    report = validate_records(records)
    if not report["valid"]:
        messages = ["{}: {}".format(issue["code"], issue["message"]) for issue in report["errors"]]
        raise CorpusError("invalid corpus: " + "; ".join(messages))


def load_records(path: Path) -> List[Dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".jsonl":
        records = []
        for line_number, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise CorpusError("invalid JSONL at line {}: {}".format(line_number, exc)) from exc
        return records
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CorpusError("invalid JSON: {}".format(exc)) from exc
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("records"), list):
        return payload["records"]
    raise CorpusError("input must be a JSON array, a JSON object with records[], or JSONL")


class CohortWindow:
    """Deterministic publication-date and/or post-age filter."""

    def __init__(
        self,
        published_start: Optional[str] = None,
        published_end: Optional[str] = None,
        min_age_days: Optional[int] = None,
        max_age_days: Optional[int] = None,
        as_of: Optional[str] = None,
    ) -> None:
        self.published_start = _parse_boundary(published_start, end=False)
        self.published_end = _parse_boundary(published_end, end=True)
        self.min_age_days = min_age_days
        self.max_age_days = max_age_days
        self.as_of = _parse_datetime(as_of, "as_of") if as_of else None
        if self.published_start is None and self.published_end is None and min_age_days is None and max_age_days is None:
            raise CorpusError("configure at least one publication-date or post-age cohort boundary")
        if min_age_days is not None and min_age_days < 0:
            raise CorpusError("min_age_days cannot be negative")
        if max_age_days is not None and max_age_days < 0:
            raise CorpusError("max_age_days cannot be negative")
        if min_age_days is not None and max_age_days is not None and min_age_days > max_age_days:
            raise CorpusError("min_age_days cannot exceed max_age_days")
        if (min_age_days is not None or max_age_days is not None) and self.as_of is None:
            raise CorpusError("as_of is required for a deterministic age cohort")
        if self.published_start and self.published_end and self.published_start > self.published_end:
            raise CorpusError("published_start cannot follow published_end")

    def includes(self, record: Mapping[str, Any]) -> bool:
        published = _parse_datetime(record["published_at"], "published_at")
        if self.published_start and published < self.published_start:
            return False
        if self.published_end and published > self.published_end:
            return False
        if self.as_of is not None:
            age_seconds = (self.as_of - published).total_seconds()
            if age_seconds < 0:
                return False
            age_days = int(math.floor(age_seconds / 86400.0))
            if self.min_age_days is not None and age_days < self.min_age_days:
                return False
            if self.max_age_days is not None and age_days > self.max_age_days:
                return False
        return True

    def as_dict(self) -> Dict[str, Any]:
        return {
            "published_start": self.published_start.isoformat() if self.published_start else None,
            "published_end": self.published_end.isoformat() if self.published_end else None,
            "min_age_days": self.min_age_days,
            "max_age_days": self.max_age_days,
            "as_of": self.as_of.isoformat() if self.as_of else None,
        }


def cohort_key(record: Mapping[str, Any]) -> Tuple[str, str, str, str]:
    return (record["creator"], record["platform"], record["format"], record["distribution"])


def cohort_key_dict(key: Tuple[str, str, str, str]) -> Dict[str, str]:
    return {"creator": key[0], "platform": key[1], "format": key[2], "distribution": key[3]}


def deduplicate_records(records: Sequence[Mapping[str, Any]]) -> Tuple[List[Mapping[str, Any]], List[Dict[str, Any]]]:
    """Deduplicate connected exact-source matches on URL or raw reference.

    A record may bridge two duplicate indicators (same URL as one record and same raw
    reference as another), so a single preferred key is insufficient.
    """
    ordered_records = sorted(records, key=lambda record: record["id"])
    parents = list(range(len(ordered_records)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parents[right_root] = left_root

    seen_urls: Dict[str, int] = {}
    seen_raw_refs: Dict[str, int] = {}
    for index, record in enumerate(ordered_records):
        normalized_url = normalize_source_url(record["source_url"])
        if normalized_url in seen_urls:
            union(index, seen_urls[normalized_url])
        else:
            seen_urls[normalized_url] = index
        raw_ref = record.get("raw_ref")
        if isinstance(raw_ref, str) and raw_ref.strip():
            normalized_raw_ref = raw_ref.strip()
            if normalized_raw_ref in seen_raw_refs:
                union(index, seen_raw_refs[normalized_raw_ref])
            else:
                seen_raw_refs[normalized_raw_ref] = index

    groups: Dict[int, List[Mapping[str, Any]]] = defaultdict(list)
    for index, record in enumerate(ordered_records):
        groups[find(index)].append(record)
    kept = []
    duplicate_groups = []
    for group in groups.values():
        ordered = sorted(group, key=lambda record: record["id"])
        kept.append(ordered[0])
        if len(ordered) > 1:
            duplicate_groups.append(
                {
                    "matched_on": ["source_url and/or raw_ref"],
                    "kept_id": ordered[0]["id"],
                    "dropped_ids": [record["id"] for record in ordered[1:]],
                }
            )
    return sorted(kept, key=lambda record: record["id"]), sorted(duplicate_groups, key=lambda group: group["kept_id"])


def compare_cohorts(
    records: Sequence[Mapping[str, Any]],
    window: CohortWindow,
    small_cohort_threshold: int = 6,
) -> Dict[str, Any]:
    assert_valid_records(records)
    if small_cohort_threshold < 1:
        raise CorpusError("small_cohort_threshold must be at least 1")
    grouped: Dict[Tuple[str, str, str, str], List[Mapping[str, Any]]] = defaultdict(list)
    for record in records:
        if window.includes(record):
            grouped[cohort_key(record)].append(record)

    cohorts = []
    for key in sorted(grouped):
        raw_group = grouped[key]
        deduped, duplicate_groups = deduplicate_records(raw_group)
        known = [record for record in deduped if record["views"] is not None]
        by_definition: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
        for record in known:
            by_definition[record["view_metric_definition"]].append(record)

        flags = []
        if len(known) < small_cohort_threshold:
            flags.append("small_cohort")
        if duplicate_groups:
            flags.append("duplicates_deduplicated")
        if len(by_definition) > 1:
            flags.append("mixed_view_metric_definitions")
        if len(known) < len(deduped):
            flags.append("unknown_views_excluded")
        if key[3] == "paid":
            flags.append("paid_performance_not_inferred")
        if any(record.get("provenance", {}).get("source_type") == "public_ad_library" for record in deduped):
            flags.append("public_ad_library_no_profitability_inference")

        metric_groups = []
        for definition in sorted(by_definition):
            metric_records = sorted(by_definition[definition], key=lambda record: record["id"])
            values = [record["views"] for record in metric_records]
            median = statistics.median(values)
            zero_median = median == 0
            if zero_median:
                flags.append("zero_median:{}".format(definition))
            metric_groups.append(
                {
                    "view_metric_definition": definition,
                    "sample_size": len(values),
                    "median": median,
                    "zero_median": zero_median,
                    "records": [
                        {
                            "id": record["id"],
                            "views": record["views"],
                            "relative_to_median": None if zero_median else record["views"] / median,
                        }
                        for record in metric_records
                    ],
                }
            )

        cohorts.append(
            {
                "cohort": cohort_key_dict(key),
                "denominator": len(raw_group),
                "deduplicated_denominator": len(deduped),
                "known_view_sample_size": len(known),
                "view_metric_definition_counts": dict(sorted(Counter(record["view_metric_definition"] for record in known).items())),
                "median": metric_groups[0]["median"] if len(metric_groups) == 1 else None,
                "metric_groups": metric_groups,
                "duplicate_groups": duplicate_groups,
                "flags": sorted(set(flags)),
                "interpretation": (
                    "Public paid-library data can describe visible creative and recorded longevity only; it does not establish profitability."
                    if "public_ad_library_no_profitability_inference" in flags
                    else None
                ),
            }
        )
    return {
        "cohort_window": window.as_dict(),
        "cohort_key_fields": ["creator", "platform", "format", "distribution"],
        "cohort_count": len(cohorts),
        "cohorts": cohorts,
    }


def _select_band_records(records: Sequence[Mapping[str, Any]], per_band: int) -> List[Tuple[str, Mapping[str, Any]]]:
    if per_band < 1:
        raise CorpusError("per_band must be at least 1")
    ordered = sorted(records, key=lambda record: (record["views"], record["id"]))
    if not ordered:
        return []
    median = statistics.median(record["views"] for record in ordered)
    selected_ids = set()
    result: List[Tuple[str, Mapping[str, Any]]] = []

    for record in ordered[:per_band]:
        selected_ids.add(record["id"])
        result.append(("low", record))
    for record in reversed(ordered):
        if record["id"] in selected_ids:
            continue
        selected_ids.add(record["id"])
        result.append(("high", record))
        if sum(1 for band, _ in result if band == "high") >= per_band:
            break
    typical_candidates = sorted(
        (record for record in ordered if record["id"] not in selected_ids),
        key=lambda record: (abs(record["views"] - median), record["id"]),
    )
    for record in typical_candidates[:per_band]:
        selected_ids.add(record["id"])
        result.append(("typical", record))
    return sorted(result, key=lambda item: ({"low": 0, "typical": 1, "high": 2}[item[0]], item[1]["id"]))


def sample_cohorts(
    records: Sequence[Mapping[str, Any]],
    window: CohortWindow,
    per_band: int = 1,
    small_cohort_threshold: int = 6,
) -> Dict[str, Any]:
    comparison = compare_cohorts(records, window, small_cohort_threshold)
    by_id = {record["id"]: record for record in records}
    samples = []
    for cohort in comparison["cohorts"]:
        key = cohort["cohort"]
        matching = [
            record
            for record in records
            if window.includes(record)
            and cohort_key_dict(cohort_key(record)) == key
            and record["views"] is not None
        ]
        deduped, _ = deduplicate_records(matching)
        definitions: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
        for record in deduped:
            definitions[record["view_metric_definition"]].append(record)
        for definition in sorted(definitions):
            for band, record in _select_band_records(definitions[definition], per_band):
                samples.append(
                    {
                        "id": record["id"],
                        "sample_band": band,
                        "views": record["views"],
                        "view_metric_definition": definition,
                        "cohort": copy.deepcopy(key),
                    }
                )
    # Defensive assertion: a duplicate/cross-band item can never survive.
    if len({entry["id"] for entry in samples}) != len(samples):
        raise CorpusError("sampling produced duplicate IDs")
    return {
        "cohort_window": window.as_dict(),
        "per_band": per_band,
        "sample_count": len(samples),
        "samples": sorted(samples, key=lambda entry: (tuple(entry["cohort"].values()), entry["view_metric_definition"], entry["sample_band"], entry["id"])),
        "comparison": comparison,
    }


def _blind_id(record_id: str, salt: str) -> str:
    digest = hashlib.sha256((salt + "\0" + record_id).encode("utf-8")).hexdigest()[:12].upper()
    return "B-" + digest


def _sensitive_tokens(record: Mapping[str, Any]) -> List[str]:
    values = [record.get("id"), record.get("source_url"), record.get("raw_ref"), record.get("title")]
    raw_ref = record.get("raw_ref")
    if isinstance(raw_ref, str):
        values.append(Path(raw_ref).name)
    return sorted({value for value in values if isinstance(value, str) and len(value) >= 6}, key=len, reverse=True)


def _redact_text(value: Any, tokens: Sequence[str]) -> Any:
    if not isinstance(value, str):
        return copy.deepcopy(value)
    result = value
    for token in tokens:
        result = result.replace(token, "[redacted]")
    result = re.sub(r"https?://[^\s]+", "[redacted-url]", result, flags=re.IGNORECASE)
    result = re.sub(
        r"(?i)(?<!\w)[\w./\\-]+\.(?:mp4|mov|avi|mkv|webm|jsonl?|csv|xlsx?|jpe?g|png|webp|gif|srt|vtt|txt|pdf)\b",
        "[redacted-file]",
        result,
    )
    return result


def _coverage_for_blind(value: Mapping[str, Any]) -> Dict[str, Any]:
    # Method and notes can contain provider names, file paths, or rank hints.
    return {"status": value.get("status")}


def build_blind_packet(
    records: Sequence[Mapping[str, Any]],
    sample_manifest: Mapping[str, Any],
    salt: str = "viral-corpus-v1",
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    assert_valid_records(records)
    by_id = {record["id"]: record for record in records}
    packet_records = []
    mapping_records = []
    for sample in sample_manifest["samples"]:
        record = by_id[sample["id"]]
        blind_id = _blind_id(record["id"], salt)
        tokens = _sensitive_tokens(record)
        packet_record = {
            "blind_id": blind_id,
            "platform": record["platform"],
            "format": record["format"],
            "distribution": record["distribution"],
            "transcript_coverage": _coverage_for_blind(record["transcript_coverage"]),
            "visual_coverage": _coverage_for_blind(record["visual_coverage"]),
            "audio_coverage": _coverage_for_blind(record["audio_coverage"]),
        }
        for field in CREATIVE_FIELDS:
            if field in record and record[field] is not None:
                packet_record[field] = _redact_text(record[field], tokens)
        packet_records.append(packet_record)
        mapping_records.append(
            {
                "blind_id": blind_id,
                "id": record["id"],
                "creator": record["creator"],
                "source_url": record["source_url"],
                "raw_ref": record["raw_ref"],
                "published_at": record["published_at"],
                "captured_at": record["captured_at"],
                "views": record["views"],
                "view_metric_definition": record["view_metric_definition"],
                "likes": record["likes"],
                "comments": record["comments"],
                "sample_band": sample["sample_band"],
                "cohort": copy.deepcopy(sample["cohort"]),
                "provenance": copy.deepcopy(record["provenance"]),
            }
        )

    # Hash order is deterministic and independent of performance rank or band.
    packet_records.sort(key=lambda record: record["blind_id"])
    mapping_records.sort(key=lambda record: record["blind_id"])
    packet = {
        "packet_version": "1.0",
        "performance_blind": True,
        "record_count": len(packet_records),
        "records": packet_records,
    }
    private_mapping = {
        "mapping_version": "1.0",
        "privacy": "PRIVATE: contains performance metadata and source identity; do not give to annotators.",
        "record_count": len(mapping_records),
        "records": mapping_records,
    }
    assert_blind_packet(packet)
    return packet, private_mapping


def _walk_keys(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from _walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_keys(child)


def assert_blind_packet(packet: Mapping[str, Any]) -> None:
    leaked = sorted(set(_walk_keys(packet)) & PRIVATE_OR_PERFORMANCE_KEYS)
    if leaked:
        raise CorpusError("blind packet leaks private/performance keys: {}".format(", ".join(leaked)))


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _add_window_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--published-start", help="Inclusive ISO date/datetime lower bound")
    parser.add_argument("--published-end", help="Inclusive ISO date/datetime upper bound")
    parser.add_argument("--min-age-days", type=int, help="Minimum whole post age in days")
    parser.add_argument("--max-age-days", type=int, help="Maximum whole post age in days")
    parser.add_argument("--as-of", help="Required ISO datetime for age filters")


def _window_from_args(args: argparse.Namespace) -> CohortWindow:
    return CohortWindow(
        published_start=args.published_start,
        published_end=args.published_end,
        min_age_days=args.min_age_days,
        max_age_days=args.max_age_days,
        as_of=args.as_of,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="Validate normalized JSON/JSONL records")
    validate_parser.add_argument("input", type=Path)

    compare_parser = subparsers.add_parser("compare", help="Compare explicit same-context cohorts")
    compare_parser.add_argument("input", type=Path)
    compare_parser.add_argument("--small-cohort-threshold", type=int, default=6)
    _add_window_arguments(compare_parser)

    sample_parser = subparsers.add_parser("sample", help="Select deterministic high/typical/low samples")
    sample_parser.add_argument("input", type=Path)
    sample_parser.add_argument("--per-band", type=int, default=1)
    sample_parser.add_argument("--small-cohort-threshold", type=int, default=6)
    _add_window_arguments(sample_parser)

    blind_parser = subparsers.add_parser("blind", help="Write a blind annotation packet and private mapping")
    blind_parser.add_argument("input", type=Path)
    blind_parser.add_argument("--packet-out", type=Path, required=True)
    blind_parser.add_argument("--mapping-out", type=Path, required=True)
    blind_parser.add_argument("--per-band", type=int, default=1)
    blind_parser.add_argument("--small-cohort-threshold", type=int, default=6)
    blind_parser.add_argument("--salt", default="viral-corpus-v1", help="Stable opacity salt; this is not encryption")
    _add_window_arguments(blind_parser)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        records = load_records(args.input)
        if args.command == "validate":
            result = validate_records(records)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0 if result["valid"] else 1
        window = _window_from_args(args)
        if args.command == "compare":
            result = compare_cohorts(records, window, args.small_cohort_threshold)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        if args.command == "sample":
            result = sample_cohorts(records, window, args.per_band, args.small_cohort_threshold)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        if args.command == "blind":
            if args.packet_out.resolve() == args.mapping_out.resolve():
                raise CorpusError("packet_out and mapping_out must be different files")
            sample = sample_cohorts(records, window, args.per_band, args.small_cohort_threshold)
            packet, mapping = build_blind_packet(records, sample, args.salt)
            write_json(args.packet_out, packet)
            write_json(args.mapping_out, mapping)
            print(json.dumps({"packet_out": str(args.packet_out), "mapping_out": str(args.mapping_out), "record_count": packet["record_count"]}, indent=2, sort_keys=True))
            return 0
        parser.error("unknown command")
        return 2
    except (CorpusError, OSError) as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
