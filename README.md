# Viral Content Skills

A portable Codex skill suite for researching, ideating, scripting, and directing organic videos and paid ads. The `viral` entrypoint chooses and sequences the included skills from the requested outcome, current evidence, and available production.

Start with the [practical workflow](WORKFLOW.md), [eight sample briefs](examples/README.md), or [research coverage](research/coverage-2026-09-06.md). The source-attributed [creator decisions](skills/viral-content/references/creator-decisions.md), [paid cases](skills/viral-content/references/paid-cases.md), and [organic comparisons](skills/viral-content/references/organic-cases.md) show what the research changes in actual writing and direction.

## Use

Use `/viral <prompt>` as the concise entrypoint where the client exposes installed skills by name.
The explicit equivalent is `Use $viral ...`. This is invocation by skill name; the package does not
register a separate application-level slash command. Existing `$viral-content` requests remain
supported, and you can enter at a specific stage when you already know what you need.

| Skill | Result |
|---|---|
| `viral` | Chooses the necessary skills, sequences their handoffs, and returns one coherent result |
| `viral-content` | Compatible end-to-end router for existing requests |
| `viral-research` | Creator/ad evidence, strong/typical/weak comparisons, audiovisual coverage, and actionable findings |
| `viral-ideate` | Distinct audience-relevant concepts and a recommended direction |
| `viral-script` | Full scripts, speaking cards, hooks, or body-only rewrites |
| `viral-direct` | Visual hooks, blocking, camera/graphics/sound cues, and an editing handoff |
| `viral-learn` | Attributable taste corrections, performance comparisons, and next tests |

Examples:

```text
/viral Develop a 30-second paid ad for this offer, from evidence through a filmable plan.
Use $viral to turn this audience problem and offer into three organic concepts, then script and direct the best one.
Use $viral-content to develop a 30-second paid ad for this offer.
Use $viral-script to rewrite only the body below. Keep the supplied offer and CTA.
Use $viral-ideate to explore three skit concepts for this organic topic.
Use $viral-direct to plan the spoken, text, and physical hook for this claymation ad.
Use $viral-research to compare this creator's strong, ordinary, and weak videos.
Use $viral-learn to review these seven-day post snapshots and my editing feedback.
```

The skills handle organic reach, organic authority/buyer education, and paid conversion separately. Creative formats include direct-to-camera/UGC-style presenter, claymation, skits, jumbotron concepts, demonstrations, comparisons, teardowns, stories, silent text, and new formats derived from their narrative purpose.

For persistent taste and facts, fill [brand-context.md](templates/brand-context.md) in your project's private `.viral/brand-context.md`, or point to an existing profile in your request. Keep separate brands in separate profiles. Exclude the filled profile, raw research, feedback and credentials from any copy you share; they are project data rather than part of the installed skills.

## Install

Requires Python 3.9 or newer for the installer and included helpers. The writing skills themselves are Markdown instructions. Install all seven skills so their relative shared references remain available:

```bash
python3 tools/validate.py
python3 tools/install.py
```

The default destination is `$CODEX_HOME/skills`, or `~/.codex/skills` when unset. For another computer, copy this repository and run the same command there. To use an explicit destination:

```bash
python3 tools/install.py --target /path/to/codex/skills
```

The installer refuses to overwrite an unrelated skill. To update a prior installation from this package, run `python3 tools/install.py --replace`; the previous version is backed up. Start a new Codex task if its skill catalog has already been loaded before installation.

## Research integrations

Foreplay, Sandcastles, and Apify are optional acquisition providers. Configure the chosen provider in the environment where research will run, following [provider instructions](skills/viral-research/references/providers.md). The skill uses existing research when sufficient, discovers live capabilities, preserves raw responses, records collection costs/coverage, and acquires missing evidence as needed.

No account, API key, SSH host, personal source ledger, client claim, or media archive is embedded. Tools are optional for writing from a sufficient brief. An inaccessible provider does not prevent using existing source material.

## Editing and interviews

`grill-me` can supply source-grounded interview material when installed and requested. `video-style-study` can produce measured style packs. `video-edit` can turn the production plan into an actual editable/rendered candidate. These are optional external skills; this package does not silently install them. The [handoff contract](skills/viral-content/references/handoffs.md) also works for a human editor or another production system.

## Evidence and limits

The reference library distinguishes primary teachings, inspected creative, media measurements, provider interpretation, editorial preference, and actual performance. Popularity, longevity, or a provider's virality score is not proof of profit or causation. Missing visual/audio coverage stays explicit.

Private raw media, complete course materials, customer research, account data, credentials, and actual client benchmarks belong in the user's project. This repository contains reusable instructions, concise source-attributed learning, constructed examples, and portable validation tools. It is not affiliated with or endorsed by the referenced creators or providers.

The [evaluation report](evaluation/results-2026-09-06.md) preserves improvements, losses, ties and remaining weaknesses. These results describe the tested instruction snapshots; they do not guarantee reach or commercial results. Release notes are in [CHANGELOG.md](CHANGELOG.md).
