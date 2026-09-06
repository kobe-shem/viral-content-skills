# Normalized creative corpus contract

Use this contract before comparing performance or preparing a performance-blind annotation packet.
The portable validator and CLI are [`corpus.py`](../scripts/corpus.py). It uses Python 3.9 and the
standard library only; it performs no network or paid-provider operations. In the commands below,
replace `/path/to/viral-research` with the installed skill directory.

## Input envelope

The CLI accepts one of:

- a JSON array of records;
- a JSON object with a `records` array;
- JSONL, selected by a `.jsonl` filename.

Every record has these required keys. A required nullable key must be present even when its value is
unknown.

| Field | Type | Rule |
|---|---|---|
| `id` | non-empty string | Stable within this corpus. Duplicate IDs are errors. |
| `platform` | non-empty string | Use a stable platform name, not a URL or account handle. |
| `creator` | non-empty string | Resolved creator/advertiser identity. Do not merge similar names. |
| `format` | non-empty string | Explicit comparable format, such as `short_video` or `image_ad`. |
| `distribution` | string enum | `organic`, `paid`, or `unknown`. Never infer paid/boosted status. |
| `source_url` | HTTP(S) URL | Original public or authorized source pointer. |
| `published_at` | ISO-8601 datetime | Must include `Z` or a UTC offset. |
| `captured_at` | ISO-8601 datetime | Must include `Z` or a UTC offset and cannot precede publication. |
| `views` | integer or `null` | Non-negative. Unknown is `null`; unknown is never zero. |
| `view_metric_definition` | non-empty string | Exact semantics, such as `platform_play_count` or `account_export_reach`. Different definitions are not pooled. |
| `likes` | integer or `null` | Non-negative. Required key; nullable value. |
| `comments` | integer or `null` | Non-negative. Required key; nullable value. |
| `transcript_coverage` | coverage object | Independent transcript coverage. |
| `visual_coverage` | coverage object | Independent visual coverage. A caption or transcript does not satisfy it. |
| `audio_coverage` | coverage object | Independent listening/inspection coverage. |
| `provenance` | provenance object | How this normalized record was obtained. |
| `raw_ref` | string or `null` | Project-local raw-data pointer. Keep credentials out of it. |

Optional creative fields are `title`, `caption`, `transcript`, `on_screen_text`,
`visual_observations`, and `audio_observations`. The blind packet omits `title` because titles and
filenames often expose winner/loser selection. It includes the other creative fields after removing
exact source pointers, IDs, and raw filenames.

## Coverage objects

Each coverage object has a required `status` and optional nullable `method` and `notes` strings.

```json
{
  "transcript_coverage": {
    "status": "full",
    "method": "platform transcript checked against playback",
    "notes": null
  },
  "visual_coverage": {
    "status": "opening_only",
    "method": "first five seconds inspected",
    "notes": "The rest of the video was not viewed."
  },
  "audio_coverage": {
    "status": "none",
    "method": null,
    "notes": null
  }
}
```

Allowed transcript statuses: `none`, `partial`, `full`.

Allowed visual statuses: `none`, `opening_only`, `sampled`, `full`.

Allowed audio statuses: `none`, `partial`, `full`.

Coverage stays modality-specific. Text that says what appeared on screen is still text evidence
unless the visual was inspected. Contact sheets support `sampled`, not automatically `full`.

## Provenance object

`provenance` requires:

- `source_type`: one of `first_party_export`, `public_platform`, `public_ad_library`, `provider`,
  `manual`, or `other`;
- `collector`: the tool, export, or human normalization process;
- `retrieved_at`: ISO-8601 datetime with timezone.

`request_ref` is an optional string or `null` for a saved request, query, export, pagination, or
manifest pointer. Provider/model analysis belongs in a separate evidence field or artifact; it does
not become direct observation through normalization.

## Complete example

```json
{
  "id": "example-001",
  "platform": "example-video-platform",
  "creator": "creator-a",
  "format": "short_video",
  "distribution": "organic",
  "source_url": "https://example.invalid/video/001",
  "published_at": "2026-08-01T12:00:00Z",
  "captured_at": "2026-08-15T12:00:00Z",
  "views": 1200,
  "view_metric_definition": "platform_play_count",
  "likes": null,
  "comments": 12,
  "transcript_coverage": {"status": "full", "method": "manual correction", "notes": null},
  "visual_coverage": {"status": "sampled", "method": "timecoded frames", "notes": null},
  "audio_coverage": {"status": "none", "method": null, "notes": null},
  "provenance": {
    "source_type": "public_platform",
    "collector": "authorized local export",
    "retrieved_at": "2026-08-15T12:00:00Z",
    "request_ref": "exports/run-001.json"
  },
  "raw_ref": "raw/run-001/record-001.json",
  "caption": "Example caption",
  "transcript": "Example spoken content.",
  "on_screen_text": "EXAMPLE",
  "visual_observations": "00:00: face and object visible.",
  "audio_observations": null
}
```

## Cohorts and metrics

The CLI compares only exact `(creator, platform, format, distribution)` groups inside an explicit
publication-date and/or post-age window. An age window requires `--as-of`; this prevents a later run
from silently changing cohort membership.

For every cohort the report includes:

- `denominator`: records in the configured cohort before exact-source deduplication;
- `deduplicated_denominator`: records after normalized source URL/raw reference deduplication;
- `known_view_sample_size`: deduplicated records whose `views` is not `null`;
- exact metric-definition counts;
- a median and per-record relative value only within one exact metric definition.

Mixed metric definitions are split into separate metric groups and flagged. A zero median is
reported as zero; ratios are `null`, never infinity or an invented multiplier. Small cohorts,
duplicate sources, and excluded unknown metrics are flagged.

Public paid-library records may show visible creative, dates, and recorded longevity. They do not
establish profitability, ROAS, CPA, or even whether delivery was meaningfully scaled. The comparison
report emits this limitation whenever `provenance.source_type` is `public_ad_library`.

## Deterministic samples and blind packets

Sampling operates independently within each exact cohort and metric definition. It deduplicates
exact sources, orders by `(views, id)`, selects low and high edges, then selects records nearest the
median from the remaining records. A record cannot appear in more than one band.

The annotation packet:

- replaces source IDs with deterministic opaque IDs;
- sorts by opaque ID rather than performance band;
- omits views, likes, comments, metric definitions, dates, creator, rank/outlier labels, source URLs,
  provenance, titles, raw references, and filenames;
- retains platform, format, distribution, explicit coverage statuses, and available creative text or
  observations.

The separate private mapping contains source identity, performance fields, cohort, and sample band.
Never give that mapping to the blind annotator. Opaque IDs reduce accidental disclosure; they are not
encryption.

## CLI examples

```bash
python3 /path/to/viral-research/scripts/corpus.py validate corpus.json
```

```bash
python3 /path/to/viral-research/scripts/corpus.py compare corpus.json \
  --published-start 2026-06-01 --published-end 2026-08-31 \
  --small-cohort-threshold 6
```

```bash
python3 /path/to/viral-research/scripts/corpus.py sample corpus.json \
  --min-age-days 7 --max-age-days 60 --as-of 2026-09-06T00:00:00Z \
  --per-band 2
```

```bash
python3 /path/to/viral-research/scripts/corpus.py blind corpus.json \
  --published-start 2026-06-01 --published-end 2026-08-31 \
  --per-band 2 \
  --packet-out private-run/annotation-packet.json \
  --mapping-out private-run/performance-map.private.json
```

Use [`research-method.md`](research-method.md) for identity resolution, sample design, full creative
inspection, evidence classes, and synthesis rules. This contract handles normalization and comparison;
it does not turn observational data into a causal experiment.
