# Use the system on real work

Install the seven skills and start a new Codex task. Use `/viral <prompt>` where the client exposes
installed skills by name, or write `Use $viral ...` to invoke the named skill explicitly. This
package supplies a skill entrypoint rather than registering a separate application-level slash
command. The `viral` skill chooses and sequences research → ideas → script → direction → editing →
learning according to the request. A small rewrite can still start and finish at scripting, and
existing `$viral-content` requests remain supported.

## First useful session

Put your current offer facts, audience, speaker preferences, accepted examples and actual rejection reasons in the project's private `.viral/brand-context.md`. Use the [template](templates/brand-context.md). Existing approved project sources can be linked instead of recopied. Keep each brand separate.

```text
/viral Load this project's brand context and develop the right content path.
We need [organic authority / organic reach / paid qualified leads / paid sales].
The audience is [specific situation]. The offer and supported facts are [facts].
Available production is [speaker, props, location, footage].
Develop three materially different concepts, recommend one, and explain
the opening promise, useful body, payoff and reason the format fits.
Use existing research first. Acquire more only for a specific unresolved decision.
```

The same request can be written explicitly as `Use $viral. Load this project's brand context and
develop the right content path.` Use a stage skill directly when the task is deliberately narrow.

When the idea needs your experience or judgment, ask it to use `grill-me` to interview you and save the answers. Give the skill your actual decisions; do not let it manufacture founder stories. If the supplied facts already support a good demonstration, it can develop that directly.

## From concept to filmable script

```text
Use $viral-script on concept 2. Write the full 30-second paid script.
Keep these claims and CTA. Use natural speech for this presenter.
Then use $viral-direct: exact first-frame action, spoken hook and screen text,
followed by synchronized dialogue, blocking, camera, graphics and sound notes.
Identify the payoff and preserve time for the decisive demonstration.
```

For a body-only rewrite, explicitly provide the locked hook/ending when available and request only the body. For a speaking card, request an exact hook, substantial riff bullets and exact close. Do not use a full-script preference from another speaker.

Review the **actual** script and production plan. “Too polished” is useful when attached to a line and a preferred replacement. “Wrong topic” retires the premise; it should not trigger ten rewrites of the same hook. Save the rejected version and exact correction through `viral-learn`.

## Editing handoff

The output of `viral-direct` is a [production plan](templates/production.json), with estimated timing and asset requirements. Give it to the installed `video-edit` skill or a human editor. The editor ingests real footage, measures speech and source timing, then builds the actual timeline. A planning timestamp is not a frame-accurate edit.

To learn an editing style, use `video-style-study` on a coherent set of references. Separate full playback observations, machine measurements and sampled frames. Create a short calibration cut from cleared footage, review specific passages, then test the rules on a different script. Keep the preset a candidate until that evidence exists.

## Review outcomes at useful windows

At publication, save creative ID, script revision/hash, hook/format, objective, publication time and the changed variable. For paid tests, also retain offer, destination, audience, placement and attribution settings. Export from the authorized account/CRM or use its connected read-only tools; Foreplay alone cannot supply your conversion performance.

For organic work, capture comparable post-age snapshots—24 hours and seven days are useful starting examples, not mandatory universal windows. Review retention, completion, shares/saves, qualified replies and business outcomes separately. Compare within an appropriate creator/platform/format/age cohort.

For paid work, inspect spend and delivery maturity alongside the business event. Keep click, lead, qualified-lead, booked-call, sale and revenue definitions distinct. Missing tracking is unknown. A lower cost per click can accompany worse cost per qualified lead.

```text
Use $viral-learn on these account/CRM exports and the matching creative versions.
Check comparability and missing tracking first. Separate measured results,
my editorial feedback and your hypotheses. Inspect the relevant video passages.
Recommend the next two tests, with one primary business metric each,
an observation window and the alternative explanations we need to watch.
```

## One concrete feedback example

The bundled [fictional log](examples/feedback-example.jsonl) deliberately contains an attention/conversion disagreement: hook A has 480 clicks from 40,000 impressions and three qualified leads on $500 spend; B has 320 clicks from 40,000 impressions and eight qualified leads on $500 spend. A has higher CTR (1.2% versus 0.8%); B has lower observed cost per qualified lead ($62.50 versus $166.67). The dataset is illustrative, small and nonrandom; it proves neither causation nor profit.

From the source repository:

```bash
python3 tools/feedback.py validate-log --log examples/feedback-example.jsonl
python3 tools/feedback.py metric-compare --log examples/feedback-example.jsonl \
  --event-id example-ctr-a --event-id example-ctr-b
python3 tools/feedback.py metric-compare --log examples/feedback-example.jsonl \
  --event-id example-cpql-a --event-id example-cpql-b
```

Installed users can run the same commands through the installed `viral-learn/scripts/feedback.py`; keep real logs in the private project. See the [CLI reference](skills/viral-learn/references/feedback-cli.md) for attributable editorial notes, metrics and lesson decisions.

## Make learning durable

After each review, save: what happened, the comparable evidence, what you changed, where the lesson applies, what contradicts it, and what you will test next. Promote a personal correction into that speaker's profile. Promote a general rule only when the evidence and exceptions justify the scope. Keep earlier versions and negative outcomes.

Before a material skill update, replay a frozen set of past failures and positive examples with the same model/settings. Then run fresh briefs that the revision was not tuned against. Preserve ties, failures and insufficient briefs. A model editorial preference, your approval and campaign performance are three different results.
