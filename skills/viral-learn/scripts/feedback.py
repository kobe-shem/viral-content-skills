#!/usr/bin/env python3
"""Append-only editorial, performance, and lesson feedback workflow.

Python 3.9+, standard library only. This tool records supplied evidence and
explicit human decisions. It does not infer causality, declare creative winners,
or promote public engagement into taste rules.
"""

import argparse
import copy
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


EVENT_TYPES = {"editorial_review", "metric_snapshot", "lesson_proposed", "lesson_status_changed"}
EDITORIAL_VERDICTS = {"approved", "rejected"}
LESSON_STATUSES = {"hypothesis", "candidate", "approved", "rejected"}
INITIAL_LESSON_STATUSES = {"hypothesis", "candidate"}
CHANNELS = {"organic", "paid"}


class FeedbackError(ValueError):
    """Raised when an event or requested state transition is invalid."""


def _parse_datetime(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise FeedbackError("{} must be a non-empty ISO-8601 string".format(field))
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise FeedbackError("{} is not valid ISO-8601: {}".format(field, value)) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise FeedbackError("{} must include a UTC offset or Z".format(field))
    return parsed.astimezone(timezone.utc)


def _require_string(event: Mapping[str, Any], field: str) -> None:
    if field not in event:
        raise FeedbackError("{} is required".format(field))
    if not isinstance(event[field], str) or not event[field].strip():
        raise FeedbackError("{} must be a non-empty string".format(field))


def _require_nullable_string(event: Mapping[str, Any], field: str) -> None:
    if field not in event:
        raise FeedbackError("{} is required even when null".format(field))
    if event[field] is not None and (not isinstance(event[field], str) or not event[field].strip()):
        raise FeedbackError("{} must be a non-empty string or null".format(field))


def _require_object(event: Mapping[str, Any], field: str) -> None:
    if field not in event:
        raise FeedbackError("{} is required".format(field))
    if not isinstance(event[field], dict) or not event[field]:
        raise FeedbackError("{} must be a non-empty object".format(field))


def _require_refs(event: Mapping[str, Any]) -> None:
    refs = event.get("provenance_refs")
    if not isinstance(refs, list) or not refs:
        raise FeedbackError("provenance_refs must be a non-empty list")
    if any(not isinstance(ref, str) or not ref.strip() for ref in refs):
        raise FeedbackError("every provenance_refs item must be a non-empty string")


def _validate_common(event: Mapping[str, Any]) -> None:
    _require_string(event, "event_id")
    _require_string(event, "event_type")
    if event["event_type"] not in EVENT_TYPES:
        raise FeedbackError("event_type must be one of {}".format(sorted(EVENT_TYPES)))
    _require_string(event, "recorded_at")
    _parse_datetime(event["recorded_at"], "recorded_at")
    _require_refs(event)


def _validate_editorial(event: Mapping[str, Any]) -> None:
    for field in ("artifact_id", "reviewer", "exact_excerpt", "reason"):
        _require_string(event, field)
    _require_nullable_string(event, "desired_change")
    _require_object(event, "scope")
    if event.get("verdict") not in EDITORIAL_VERDICTS:
        raise FeedbackError("verdict must be approved or rejected")
    if event["verdict"] == "rejected" and event["desired_change"] is None:
        raise FeedbackError("desired_change must be supplied for a rejection")


def _number_or_null(event: Mapping[str, Any], field: str) -> Optional[float]:
    if field not in event:
        raise FeedbackError("{} is required even when null".format(field))
    value = event[field]
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise FeedbackError("{} must be a finite non-negative number or null".format(field))
    if value < 0:
        raise FeedbackError("{} cannot be negative".format(field))
    return float(value)


def _validate_window(value: Any) -> Tuple[datetime, datetime]:
    if not isinstance(value, dict):
        raise FeedbackError("window must be an object")
    if "start" not in value or "end" not in value:
        raise FeedbackError("window.start and window.end are required")
    start = _parse_datetime(value["start"], "window.start")
    end = _parse_datetime(value["end"], "window.end")
    if start > end:
        raise FeedbackError("window.start cannot follow window.end")
    return start, end


def metric_calculation(event: Mapping[str, Any]) -> Dict[str, Any]:
    numerator = event["numerator"]
    denominator = event["denominator"]
    if numerator is None or denominator is None:
        return {"status": "unknown_input", "rate": None}
    if denominator == 0:
        return {"status": "zero_denominator", "rate": None}
    return {"status": "computed", "rate": numerator / denominator}


def _validate_metric(event: Mapping[str, Any]) -> None:
    for field in ("artifact_id", "metric_name", "metric_definition", "denominator_definition"):
        _require_string(event, field)
    if event.get("channel") not in CHANNELS:
        raise FeedbackError("channel must be organic or paid")
    _number_or_null(event, "numerator")
    _number_or_null(event, "denominator")
    _validate_window(event.get("window"))
    _require_object(event, "attribution")
    _require_object(event, "cohort")
    if event.get("source_class") not in {"authorized_account", "public_platform", "public_ad_library", "other"}:
        raise FeedbackError("source_class must be authorized_account, public_platform, public_ad_library, or other")
    if event["source_class"] == "public_ad_library" and event.get("channel") != "paid":
        raise FeedbackError("public_ad_library metric snapshots must use channel=paid")


def _validate_lesson_proposed(event: Mapping[str, Any]) -> None:
    for field in ("lesson_id", "statement", "reason"):
        _require_string(event, field)
    _require_object(event, "scope")
    if event.get("status") not in INITIAL_LESSON_STATUSES:
        raise FeedbackError("a proposed lesson must start as hypothesis or candidate; approval/rejection requires an explicit status event")


def _validate_lesson_status(event: Mapping[str, Any]) -> None:
    for field in ("lesson_id", "reason"):
        _require_string(event, field)
    _require_object(event, "scope")
    if event.get("status") not in LESSON_STATUSES:
        raise FeedbackError("status must be one of {}".format(sorted(LESSON_STATUSES)))


def validate_event(event: Any) -> Dict[str, Any]:
    if not isinstance(event, dict):
        raise FeedbackError("event must be a JSON object")
    _validate_common(event)
    event_type = event["event_type"]
    if event_type == "editorial_review":
        _validate_editorial(event)
    elif event_type == "metric_snapshot":
        _validate_metric(event)
    elif event_type == "lesson_proposed":
        _validate_lesson_proposed(event)
    elif event_type == "lesson_status_changed":
        _validate_lesson_status(event)
    return copy.deepcopy(event)


def load_events(log_path: Path) -> List[Dict[str, Any]]:
    if not log_path.exists():
        return []
    events = []
    seen_ids = set()
    for line_number, line in enumerate(log_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise FeedbackError("invalid JSONL at line {}: {}".format(line_number, exc)) from exc
        try:
            validate_event(event)
        except FeedbackError as exc:
            raise FeedbackError("invalid event at line {}: {}".format(line_number, exc)) from exc
        if event["event_id"] in seen_ids:
            raise FeedbackError("duplicate event_id already present in log: {}".format(event["event_id"]))
        seen_ids.add(event["event_id"])
        events.append(event)
    return events


def _lesson_proposals(events: Sequence[Mapping[str, Any]]) -> Dict[str, Mapping[str, Any]]:
    proposals = {}
    for event in events:
        if event["event_type"] != "lesson_proposed":
            continue
        lesson_id = event["lesson_id"]
        if lesson_id in proposals:
            raise FeedbackError("duplicate lesson_id already present in log: {}".format(lesson_id))
        proposals[lesson_id] = event
    return proposals


def scope_is_within(child: Mapping[str, Any], parent: Mapping[str, Any]) -> bool:
    """A decision may retain the proposal scope or narrow it by adding keys."""
    return all(key in child and child[key] == value for key, value in parent.items())


def validate_event_against_log(event: Mapping[str, Any], existing: Sequence[Mapping[str, Any]]) -> None:
    if any(previous["event_id"] == event["event_id"] for previous in existing):
        raise FeedbackError("duplicate event_id: {}".format(event["event_id"]))
    proposals = _lesson_proposals(existing)
    if event["event_type"] == "lesson_proposed" and event["lesson_id"] in proposals:
        raise FeedbackError("duplicate lesson_id: {}".format(event["lesson_id"]))
    if event["event_type"] == "lesson_status_changed":
        proposal = proposals.get(event["lesson_id"])
        if proposal is None:
            raise FeedbackError("cannot change status for unknown lesson_id: {}".format(event["lesson_id"]))
        if not scope_is_within(event["scope"], proposal["scope"]):
            raise FeedbackError("lesson status scope must preserve the proposal scope and may only narrow it")


def append_event(log_path: Path, event: Mapping[str, Any]) -> Dict[str, Any]:
    """Validate and append one immutable JSONL event.

    Existing content is parsed first. Duplicate IDs and malformed history stop the
    append. The function opens only in append mode and never rewrites prior lines.
    """
    normalized = validate_event(event)
    existing = load_events(log_path)
    validate_event_against_log(normalized, existing)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(normalized, sort_keys=True, separators=(",", ":")) + "\n"
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    return normalized


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _window_duration_seconds(event: Mapping[str, Any]) -> float:
    start, end = _validate_window(event["window"])
    return (end - start).total_seconds()


def metric_compatibility_signature(event: Mapping[str, Any]) -> Dict[str, Any]:
    validate_event(event)
    if event["event_type"] != "metric_snapshot":
        raise FeedbackError("metric comparison accepts only metric_snapshot events")
    return {
        "channel": event["channel"],
        "metric_name": event["metric_name"],
        "metric_definition": event["metric_definition"],
        "denominator_definition": event["denominator_definition"],
        "window_duration_seconds": _window_duration_seconds(event),
        "attribution": copy.deepcopy(event["attribution"]),
        "cohort": copy.deepcopy(event["cohort"]),
    }


def compare_metric_events(events: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    if not events:
        raise FeedbackError("select at least one metric snapshot")
    signatures = [metric_compatibility_signature(event) for event in events]
    expected = _canonical(signatures[0])
    incompatible = [events[index]["event_id"] for index, signature in enumerate(signatures) if _canonical(signature) != expected]
    if incompatible:
        raise FeedbackError("incompatible metric snapshots cannot be combined: {}".format(", ".join(incompatible)))
    snapshots = []
    for event in sorted(events, key=lambda item: (item["window"]["end"], item["event_id"])):
        snapshots.append(
            {
                "event_id": event["event_id"],
                "artifact_id": event["artifact_id"],
                "numerator": event["numerator"],
                "denominator": event["denominator"],
                "calculation": metric_calculation(event),
                "window": copy.deepcopy(event["window"]),
            }
        )
    return {
        "compatibility": signatures[0],
        "snapshot_count": len(snapshots),
        "snapshots": snapshots,
        "interpretation_limit": "This is a compatible descriptive comparison, not evidence that the creative caused the result.",
    }


def list_lessons(events: Sequence[Mapping[str, Any]], include_all: bool = False) -> List[Dict[str, Any]]:
    proposals = _lesson_proposals(events)
    decisions: Dict[str, List[Mapping[str, Any]]] = {lesson_id: [] for lesson_id in proposals}
    for event in events:
        if event["event_type"] == "lesson_status_changed" and event["lesson_id"] in decisions:
            decisions[event["lesson_id"]].append(event)
    results = []
    for lesson_id in sorted(proposals):
        proposal = proposals[lesson_id]
        base_status = proposal["status"]
        scoped_decisions = []
        latest_by_scope: Dict[str, Mapping[str, Any]] = {}
        exact_scope_status = base_status
        for decision in decisions[lesson_id]:
            scoped_decisions.append(
                {
                    "event_id": decision["event_id"],
                    "status": decision["status"],
                    "reason": decision["reason"],
                    "scope": copy.deepcopy(decision["scope"]),
                    "provenance_refs": list(decision["provenance_refs"]),
                    "recorded_at": decision["recorded_at"],
                }
            )
            latest_by_scope[_canonical(decision["scope"])] = decision
            if _canonical(decision["scope"]) == _canonical(proposal["scope"]):
                exact_scope_status = decision["status"]
        item = {
            "lesson_id": lesson_id,
            "statement": proposal["statement"],
            "status": exact_scope_status,
            "base_status": base_status,
            "scope": copy.deepcopy(proposal["scope"]),
            "reason": proposal["reason"],
            "provenance_refs": list(proposal["provenance_refs"]),
            "scoped_decisions": sorted(scoped_decisions, key=lambda value: (value["recorded_at"], value["event_id"])),
        }
        has_open_scoped_decision = any(
            decision["status"] in {"hypothesis", "candidate"}
            for decision in latest_by_scope.values()
        )
        if include_all or item["status"] in {"hypothesis", "candidate"} or has_open_scoped_decision:
            results.append(item)
    return results


def make_editorial_event(
    event_id: str,
    recorded_at: str,
    artifact_id: str,
    reviewer: str,
    verdict: str,
    exact_excerpt: str,
    reason: str,
    desired_change: Optional[str],
    scope: Mapping[str, Any],
    provenance_refs: Sequence[str],
) -> Dict[str, Any]:
    return {
        "event_id": event_id,
        "event_type": "editorial_review",
        "recorded_at": recorded_at,
        "artifact_id": artifact_id,
        "reviewer": reviewer,
        "verdict": verdict,
        "exact_excerpt": exact_excerpt,
        "reason": reason,
        "desired_change": desired_change,
        "scope": dict(scope),
        "provenance_refs": list(provenance_refs),
    }


def make_metric_event(
    event_id: str,
    recorded_at: str,
    artifact_id: str,
    channel: str,
    metric_name: str,
    metric_definition: str,
    numerator: Optional[float],
    denominator: Optional[float],
    denominator_definition: str,
    window: Mapping[str, str],
    attribution: Mapping[str, Any],
    cohort: Mapping[str, Any],
    source_class: str,
    provenance_refs: Sequence[str],
) -> Dict[str, Any]:
    return {
        "event_id": event_id,
        "event_type": "metric_snapshot",
        "recorded_at": recorded_at,
        "artifact_id": artifact_id,
        "channel": channel,
        "metric_name": metric_name,
        "metric_definition": metric_definition,
        "numerator": numerator,
        "denominator": denominator,
        "denominator_definition": denominator_definition,
        "window": dict(window),
        "attribution": dict(attribution),
        "cohort": dict(cohort),
        "source_class": source_class,
        "provenance_refs": list(provenance_refs),
    }


def make_lesson_event(
    event_id: str,
    recorded_at: str,
    lesson_id: str,
    statement: str,
    status: str,
    reason: str,
    scope: Mapping[str, Any],
    provenance_refs: Sequence[str],
) -> Dict[str, Any]:
    return {
        "event_id": event_id,
        "event_type": "lesson_proposed",
        "recorded_at": recorded_at,
        "lesson_id": lesson_id,
        "statement": statement,
        "status": status,
        "reason": reason,
        "scope": dict(scope),
        "provenance_refs": list(provenance_refs),
    }


def make_lesson_status_event(
    event_id: str,
    recorded_at: str,
    lesson_id: str,
    status: str,
    reason: str,
    scope: Mapping[str, Any],
    provenance_refs: Sequence[str],
) -> Dict[str, Any]:
    return {
        "event_id": event_id,
        "event_type": "lesson_status_changed",
        "recorded_at": recorded_at,
        "lesson_id": lesson_id,
        "status": status,
        "reason": reason,
        "scope": dict(scope),
        "provenance_refs": list(provenance_refs),
    }


def _read_json_argument(value: str, field: str) -> Dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise FeedbackError("{} must be valid JSON: {}".format(field, exc)) from exc
    if not isinstance(parsed, dict):
        raise FeedbackError("{} must be a JSON object".format(field))
    return parsed


def _read_event(path_text: str) -> Dict[str, Any]:
    if path_text == "-":
        text = sys.stdin.read()
    else:
        text = Path(path_text).read_text(encoding="utf-8")
    try:
        event = json.loads(text)
    except json.JSONDecodeError as exc:
        raise FeedbackError("event input is invalid JSON: {}".format(exc)) from exc
    if not isinstance(event, dict):
        raise FeedbackError("event input must be a JSON object")
    return event


def _number_argument(value: str) -> Optional[float]:
    if value.lower() == "null":
        return None
    try:
        number = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("use a number or null") from exc
    return number


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--event-id", required=True)
    parser.add_argument("--recorded-at", required=True)
    parser.add_argument("--provenance-ref", action="append", required=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate-log", help="Validate every event and duplicate ID in a JSONL log")
    validate.add_argument("--log", type=Path, required=True)

    append = commands.add_parser("append", help="Append one generic event JSON object")
    append.add_argument("--log", type=Path, required=True)
    append.add_argument("--event", required=True, help="JSON file path, or - for stdin")

    editorial = commands.add_parser("editorial-add", help="Append an approval or rejection")
    _add_common(editorial)
    editorial.add_argument("--artifact-id", required=True)
    editorial.add_argument("--reviewer", required=True)
    editorial.add_argument("--verdict", choices=sorted(EDITORIAL_VERDICTS), required=True)
    editorial.add_argument("--excerpt", required=True)
    editorial.add_argument("--reason", required=True)
    editorial.add_argument("--desired-change", help="Required for a rejection; omit for an approval to store null")
    editorial.add_argument("--scope-json", required=True)

    metric = commands.add_parser("metric-add", help="Append an organic or paid metric snapshot")
    _add_common(metric)
    metric.add_argument("--artifact-id", required=True)
    metric.add_argument("--channel", choices=sorted(CHANNELS), required=True)
    metric.add_argument("--metric-name", required=True)
    metric.add_argument("--metric-definition", required=True)
    metric.add_argument("--numerator", type=_number_argument, required=True)
    metric.add_argument("--denominator", type=_number_argument, required=True)
    metric.add_argument("--denominator-definition", required=True)
    metric.add_argument("--window-start", required=True)
    metric.add_argument("--window-end", required=True)
    metric.add_argument("--attribution-json", required=True)
    metric.add_argument("--cohort-json", required=True)
    metric.add_argument("--source-class", choices=["authorized_account", "public_platform", "public_ad_library", "other"], required=True)

    lesson = commands.add_parser("lesson-add", help="Append a hypothesis or candidate lesson")
    _add_common(lesson)
    lesson.add_argument("--lesson-id", required=True)
    lesson.add_argument("--statement", required=True)
    lesson.add_argument("--status", choices=sorted(INITIAL_LESSON_STATUSES), required=True)
    lesson.add_argument("--reason", required=True)
    lesson.add_argument("--scope-json", required=True)

    lessons = commands.add_parser("lesson-list", help="List candidate lessons and explicit scoped decisions")
    lessons.add_argument("--log", type=Path, required=True)
    lessons.add_argument("--all", action="store_true", help="Include lessons whose broad status is approved/rejected")

    promote = commands.add_parser("lesson-promote", help="Explicitly approve a lesson for a stated scope")
    _add_common(promote)
    promote.add_argument("--lesson-id", required=True)
    promote.add_argument("--reason", required=True)
    promote.add_argument("--scope-json", required=True)

    status = commands.add_parser("lesson-status", help="Explicitly set candidate/rejected/hypothesis status")
    _add_common(status)
    status.add_argument("--lesson-id", required=True)
    status.add_argument("--status", choices=sorted(LESSON_STATUSES - {"approved"}), required=True)
    status.add_argument("--reason", required=True)
    status.add_argument("--scope-json", required=True)

    compare = commands.add_parser("metric-compare", help="Compare only explicitly compatible snapshot events")
    compare.add_argument("--log", type=Path, required=True)
    compare.add_argument("--event-id", action="append", required=True)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate-log":
            events = load_events(args.log)
            print(json.dumps({"valid": True, "event_count": len(events)}, indent=2, sort_keys=True))
            return 0
        if args.command == "append":
            event = append_event(args.log, _read_event(args.event))
        elif args.command == "editorial-add":
            if args.verdict == "rejected" and not args.desired_change:
                raise FeedbackError("desired-change is required for a rejection")
            event = make_editorial_event(
                args.event_id, args.recorded_at, args.artifact_id, args.reviewer, args.verdict,
                args.excerpt, args.reason, args.desired_change, _read_json_argument(args.scope_json, "scope-json"),
                args.provenance_ref,
            )
            append_event(args.log, event)
        elif args.command == "metric-add":
            event = make_metric_event(
                args.event_id, args.recorded_at, args.artifact_id, args.channel, args.metric_name,
                args.metric_definition, args.numerator, args.denominator, args.denominator_definition,
                {"start": args.window_start, "end": args.window_end},
                _read_json_argument(args.attribution_json, "attribution-json"),
                _read_json_argument(args.cohort_json, "cohort-json"), args.source_class, args.provenance_ref,
            )
            append_event(args.log, event)
        elif args.command == "lesson-add":
            event = make_lesson_event(
                args.event_id, args.recorded_at, args.lesson_id, args.statement, args.status,
                args.reason, _read_json_argument(args.scope_json, "scope-json"), args.provenance_ref,
            )
            append_event(args.log, event)
        elif args.command == "lesson-list":
            print(json.dumps({"lessons": list_lessons(load_events(args.log), args.all)}, indent=2, sort_keys=True))
            return 0
        elif args.command in {"lesson-promote", "lesson-status"}:
            target_status = "approved" if args.command == "lesson-promote" else args.status
            event = make_lesson_status_event(
                args.event_id, args.recorded_at, args.lesson_id, target_status, args.reason,
                _read_json_argument(args.scope_json, "scope-json"), args.provenance_ref,
            )
            append_event(args.log, event)
        elif args.command == "metric-compare":
            events = load_events(args.log)
            by_id = {event["event_id"]: event for event in events}
            missing = [event_id for event_id in args.event_id if event_id not in by_id]
            if missing:
                raise FeedbackError("unknown event_id: {}".format(", ".join(missing)))
            print(json.dumps(compare_metric_events([by_id[event_id] for event_id in args.event_id]), indent=2, sort_keys=True))
            return 0
        else:
            raise FeedbackError("unknown command")
        print(json.dumps(event, indent=2, sort_keys=True))
        return 0
    except (FeedbackError, OSError) as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
