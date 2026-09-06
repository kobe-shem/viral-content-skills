# Project and production handoffs

The project stores brand facts, credentials, source media, research datasets, scripts, feedback, and results. The skill package stores reusable instructions, schemas, code, and source-attributed craft. Relative paths below are a suggested project layout, not a required existing filesystem.

```text
content-project/
  brand-context.json
  research/                 raw provider responses + normalized records
  concepts/                 selected and rejected concepts
  scripts/                  immutable numbered revisions
  productions/<video-id>/   production.json, assets, editing outputs
  feedback/                 owner notes and outcome snapshots
```

## Brand context

Keep audience/situation, objective, offer facts, supported claims with source, prohibited/unsupported claims, CTA, speaker, voice examples, format preferences, and approved research/account pointers. Unknown facts stay unknown. A new brand can begin with the supplied brief; do not require every field before a simple rewrite.

## Ideation → scripting

Pass the selected concept ID, objective, audience/awareness, promise, useful answer/payoff, format, opening picture, available proof, and explicit constraints. Keep the original idea and rejected alternatives, including actual rejection reasons.

If a grill-me interview generated the material, cite the saved answer/decision rather than presenting an agent's inference as the speaker's belief. A direct user instruction can supersede an older profile; update its provenance.

## Scripting → direction

Use a `production.json` record, or equivalent readable brief, containing:

- `schema_version`, `project_id`, `video_id`, `revision`, and parent revision when applicable;
- objective/mode, awareness, format, target duration, and brand-context reference;
- script text/version/hash and immutable claim sources;
- opening: first frame/action, spoken line, exact text, and promised payoff;
- ordered beats: ID, exact spoken copy or selected speaking notes, narrative job, pictured action, camera, graphics/text, audio, and source/asset requirements;
- payoff map: promise ID, where it opens, intermediate rewards, and where it resolves;
- `timing_basis: estimated | measured`, timing notes, and unresolved assets/choices;
- separate review states for factual integrity, editorial quality, owner taste, and publication/campaign approval.

Timecodes in a script plan are estimates. Store exact picture/speech timing only after recorded media is inspected. A planned effect is not an observed effect. An illustration is not proof of the associated claim.

## Direction → video-edit

If installed, the existing `video-edit` skill owns media ingest, source hashes, source-use eligibility, actual timing, final caption alignment, timeline validation, rendering, audio mixing, and audiovisual review. Read its current manifest before producing a compatible timeline; do not rely on an old copied schema.

For the inspected manifest-v1 interface, `edit.json` is the single master timeline. It uses integer output frames, explicit source-in mappings, eligible ingest records, and separate clips/B-roll/graphics/captions/audio. Convert narrative cue timings to frames only after actual source media and the output FPS are known. Keep script/claim references in project metadata. Derivative renders and props do not become competing masters.

The existing `video-style-study` workflow accepts source-attributed local reference records and emits measured artifacts and versioned candidate style packs. Full visual and audio review, calibration/generalization artifacts, and actual owner feedback are separate evidence. This skill suite must not write fake review/approval values to satisfy its compiler.

If either external skill is absent, retain the editor-neutral production plan and explain the unresolved execution step. Do not install or download other skills merely because this handoff mentions them.

## Direction revisions

Keep cue IDs stable. “Hold the presenter through beat B3; remove the SFX on cue C2” should be actionable without rewriting the whole concept. Record whether a revision changes words, claims, picture, sound, timing, or format. A style change must not silently change an offer or claim.

## Generation interfaces

Pass exact dialogue, aspect ratio, duration target, identity/reference requirements, approved claim scope, shot start/action/end, and continuity to the selected generation skill. Generated footage requires inspection. A model's completion message does not establish matching dialogue, acting, text, continuity, or evidence of a real result.
