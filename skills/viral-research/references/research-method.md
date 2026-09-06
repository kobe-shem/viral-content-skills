# Forensic method

## Identity and source classes

Keep separate records for creator, channel, advertiser/page, brand/offer, and the speaker inside a clip. Confirm uncertain identities through original profile/company/channel links. Reposts and guest appearances can be useful but should not inflate a creator's own catalog or duplicate evidence.

Use these evidence classes:

- `taught`: a source says the technique works or recommends it;
- `observed`: an inspected example visibly/audibly uses the technique;
- `measured`: a reproducible calculation or media measurement;
- `provider_analysis`: a provider/model's interpretation, not independently inspected;
- `editorial_preference`: attributable human or model preference, with the reviewer identified;
- `performance_association`: a relationship in comparable observed metrics;
- `experiment`: an actual test, with design and limitations;
- `hypothesis`: proposed explanation or transfer to a new context.

A source can support several classes, but one class does not promote another. Repeated teaching is not independent replication. Interpreting a transcript is not measuring its performance.

## Catalog coverage

Record requested scope and achieved coverage: platform, channel, date range, returned count, pagination end/cursor, collection cap, unavailable sources, and retrieval time. A provider returning a capped latest-post sample cannot establish a full account history. Save the raw response and request metadata, excluding credentials.

For paid libraries, distinguish active-only from active/inactive historical queries. Resolve advertisers by brand/page identifiers before broad keyword sweeps when the creator is known. Track image/video/carousel formats and creative variants. Missing transcripts stay missing in the provider record; attach generated ASR separately with method and provenance.

## Sample selection

Define comparable cohorts before choosing examples: platform, organic/paid status, format, date/age window, creator, and subject where needed. Use sufficient history to estimate an informative baseline; explicitly mark small samples. Report denominator and view-field semantics. Plays, views, reach, and impressions are not interchangeable.

Select high, typical, and low relative outcomes plus repeated formats and deliberately quiet passages. Use several examples per important pattern. Cases selected for teaching relevance form a separate sample from cases selected by performance.

Deduplicate exact IDs/media and inspect near duplicates; preserve distinct hook variants as linked siblings. Avoid counting cross-posts as independent replication. Record known sponsorship/boosting and unknowns.

For a performance-blind pass, give reviewers opaque IDs, transcripts, and media without titles/file names that reveal winner/loser status where feasible. Freeze the annotation rubric before revealing metrics. Compare the descriptive features and actual outcomes afterward; do not rewrite annotations to fit the result.

## Timecoded annotation

For each selected asset, record:

| Layer | Required observations when that modality is available |
|---|---|
| Opening | First visible state, first meaningful movement, camera geometry, prop/object, exact text, first spoken thought, relationship among them |
| Story/argument | Audience situation, premise, beats, transitions, change/reversal, mechanism, first value, open expectations, partial rewards, final payoff |
| Paid structure | Awareness assumptions, qualification, product visible versus named, bridge, claims, proof, objections, offer, CTA |
| Delivery | Speaker intention, phrasing, emphasis, pauses, breath, reaction, eye line, gesture, movement and role changes |
| Editing | Actual/candidate cut boundaries, shot changes, crop/zoom, caption grouping, text hierarchy, graphic entrances/holds/exits, B-roll purpose, continuity |
| Sound | Speech clarity, music role and entrances, SFX, ambience, silence, mix relationships; measurements kept separate from listening judgments |
| Close | Promise resolution, final visual state, CTA timing and destination, last phonemes/frame hold, loop when present |

Use source seconds for observations. Label precise measurement, approximate timestamp, and interpretation. Explain missing coverage: e.g. transcript full, opening frames 0–5s sampled at 4fps, remainder sampled, audio unreviewed. Never fill `audio_full` or `video_full` from metadata alone.

## Transferable rule form

“When the speaker contrasts two options, keep the comparison axis visible and demonstrate the difference before the verdict” is useful. “Use blue captions” describes a surface choice without explaining when it matters.

Store rule ID, condition, behavior, narrative purpose, source/timecodes, counterexample, confidence, and intended modes/formats. Separate general craft from a creator's identity, brand assets, audience trust, offer, and results. A personal anecdote transfers as a story structure, never as a claim for another speaker.

## Finish criterion

The requested priority creators each need an explicit coverage row across teaching, organic history, strong/typical/weak samples, paid library, transcript, visual, and audio. Mark completed, partial, unavailable, or not applicable with evidence. Close accessible gaps and explain true access limits; do not use a full-sounding report title to hide partial inspection.

Give the next creative action for each major finding. Preserve alternative explanations and failures. Never guarantee that implementing a pattern will produce virality or profitable spend.
