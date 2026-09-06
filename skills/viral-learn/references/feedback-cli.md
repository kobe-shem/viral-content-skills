# Feedback event log

Use the bundled [`feedback.py`](../scripts/feedback.py) to keep editorial decisions, performance observations, and lesson decisions in an append-only JSONL log. The tool uses Python 3.9 or later and the standard library only. In the commands below, replace `/path/to/viral-learn` with the installed skill directory. A source checkout also provides the convenience wrapper `tools/feedback.py`.

The log records evidence supplied by a person or an authorized export. It does not turn engagement into taste guidance, infer which creative caused a result, or describe a public ad-library record as profitable.

## Shared event fields

Every JSON object requires:

- `event_id`: a unique, stable identifier. A duplicate stops the append.
- `event_type`: `editorial_review`, `metric_snapshot`, `lesson_proposed`, or `lesson_status_changed`.
- `recorded_at`: an ISO-8601 timestamp with `Z` or an explicit UTC offset.
- `provenance_refs`: one or more exact references to the source review, export row, or approval.

The file is read and validated before each append. Existing events are never rewritten. Keep the log in the private workspace when its source material is private.

## Editorial decisions

An editorial event retains the exact reviewed passage, the reason, the requested change, and the scope where the feedback applies:

```json
{
  "event_id": "review-2026-001",
  "event_type": "editorial_review",
  "recorded_at": "2026-01-05T16:30:00Z",
  "artifact_id": "draft-17",
  "reviewer": "editor-1",
  "verdict": "rejected",
  "exact_excerpt": "The exact sentence under review.",
  "reason": "The sentence states a result without a supplied source.",
  "desired_change": "Remove the result or attach its source.",
  "scope": {"format": "short_video", "section": "hook"},
  "provenance_refs": ["editorial-session:2026-01-05:item-4"]
}
```

For an approval, `desired_change` remains present and may be `null`. Every rejection requires a desired change, including events submitted through the generic JSON command:

```bash
python3 /path/to/viral-learn/scripts/feedback.py editorial-add \
  --log private/feedback.jsonl \
  --event-id review-2026-001 \
  --recorded-at 2026-01-05T16:30:00Z \
  --artifact-id draft-17 \
  --reviewer editor-1 \
  --verdict rejected \
  --excerpt 'The exact sentence under review.' \
  --reason 'The sentence states a result without a supplied source.' \
  --desired-change 'Remove the result or attach its source.' \
  --scope-json '{"format":"short_video","section":"hook"}' \
  --provenance-ref editorial-session:2026-01-05:item-4
```

## Metric snapshots

Supply the numerator, denominator, observation window, attribution definition, and cohort explicitly. `null` means unknown. Zero is a recorded value. A zero denominator produces a `null` rate with `zero_denominator` status; it is never treated as a missing value or divided through.

```json
{
  "event_id": "metric-2026-001",
  "event_type": "metric_snapshot",
  "recorded_at": "2026-01-08T12:00:00Z",
  "artifact_id": "creative-22",
  "channel": "organic",
  "metric_name": "completed_views",
  "metric_definition": "platform completed-view count",
  "numerator": 240,
  "denominator": 1200,
  "denominator_definition": "platform video starts",
  "window": {
    "start": "2026-01-01T00:00:00Z",
    "end": "2026-01-08T00:00:00Z"
  },
  "attribution": {"model": "platform_reported"},
  "cohort": {"platform": "example", "format": "short_video", "distribution": "organic"},
  "source_class": "authorized_account",
  "provenance_refs": ["authorized-export:row-22"]
}
```

The same event can be appended with `metric-add`; use the literal `null` for an unknown number:

```bash
python3 /path/to/viral-learn/scripts/feedback.py metric-add \
  --log private/feedback.jsonl \
  --event-id metric-2026-001 \
  --recorded-at 2026-01-08T12:00:00Z \
  --artifact-id creative-22 \
  --channel paid \
  --metric-name qualified_leads \
  --metric-definition 'CRM leads meeting the supplied qualification rule' \
  --numerator null \
  --denominator 5000 \
  --denominator-definition impressions \
  --window-start 2026-01-01T00:00:00Z \
  --window-end 2026-01-08T00:00:00Z \
  --attribution-json '{"model":"last_click","lookback_days":7}' \
  --cohort-json '{"platform":"example","format":"short_video","campaign":"prospecting"}' \
  --source-class authorized_account \
  --provenance-ref authorized-export:row-22
```

`metric-compare` accepts snapshots only when channel, metric name and definition, denominator definition, window duration, attribution, and cohort are identical. It reports each supplied numerator, denominator, and calculated rate separately rather than combining them:

```bash
python3 /path/to/viral-learn/scripts/feedback.py metric-compare \
  --log private/feedback.jsonl \
  --event-id metric-2026-001 \
  --event-id metric-2026-002
```

## Lessons and promotion

A lesson starts as `hypothesis` or `candidate` with its reason and evidence references:

```bash
python3 /path/to/viral-learn/scripts/feedback.py lesson-add \
  --log private/feedback.jsonl \
  --event-id lesson-event-001 \
  --recorded-at 2026-01-09T10:00:00Z \
  --lesson-id lesson-001 \
  --statement 'State the observable result before explaining the mechanism.' \
  --status candidate \
  --reason 'Two direct editorial reviews requested this sequence.' \
  --scope-json '{"channel":"paid"}' \
  --provenance-ref editorial-review:17 \
  --provenance-ref editorial-review:23
```

Approval is always a separate event with an explicit reason. A promotion may keep the proposal scope or narrow it by adding scope fields. It cannot remove or change the proposal scope:

```bash
python3 /path/to/viral-learn/scripts/feedback.py lesson-promote \
  --log private/feedback.jsonl \
  --event-id lesson-decision-001 \
  --recorded-at 2026-01-10T10:00:00Z \
  --lesson-id lesson-001 \
  --reason 'The editor approved this rule for paid short videos.' \
  --scope-json '{"channel":"paid","format":"short_video"}' \
  --provenance-ref editorial-approval:31
```

List open candidates and hypotheses with `lesson-list`; add `--all` to include approved and rejected broad lessons:

```bash
python3 /path/to/viral-learn/scripts/feedback.py lesson-list --log private/feedback.jsonl
python3 /path/to/viral-learn/scripts/feedback.py lesson-list --log private/feedback.jsonl --all
```

Metric events never create or promote lessons. Public platform engagement remains audience evidence. Public ad-library presence records public distribution only; it cannot establish spend, conversions, or profit.

## Generic JSON input and validation

All event types can be appended from a JSON file or standard input:

```bash
python3 /path/to/viral-learn/scripts/feedback.py append --log private/feedback.jsonl --event event.json
cat event.json | python3 /path/to/viral-learn/scripts/feedback.py append --log private/feedback.jsonl --event -
python3 /path/to/viral-learn/scripts/feedback.py validate-log --log private/feedback.jsonl
```
