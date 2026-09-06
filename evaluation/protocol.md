# Evaluation protocol

Evaluate writing quality before increasing acquisition volume. A larger corpus cannot repair a scope/routing failure on its own.

1. Save actual rejected outputs, approved calibration examples, exact available original requests, and source pointers privately. Separate the specific correction from your interpretation. Missing briefs remain missing. Consecutive revisions of one brief are not independent cases.
2. Freeze writer inputs with outcomes and corrections removed. Keep locked facts only if the writer actually had them. Do not give one arm private preferences while withholding them from the other. If a rejected draft itself contains a prior decision, both arms receive it and should honor it.
3. Use the same model, effort, inputs and output contract for recovered and candidate instruction stacks. Save exact prompts, reference hashes, CLI version, output, trace and usage. Compare model upgrades in a separate experiment.
4. Randomize A/B per case and give the judge the original input plus two unlabeled outputs. Hide the version key and correction archive. Grade task/scope/format, factual fidelity, audience/concrete stakes, progression/value, fulfilled promise/product bridge, and usable speech or developed ideation (0–4 each). Also give a pairwise preference and concrete failure evidence. Use `insufficient_brief` when the request cannot resolve the choice; do not force a winner from a number.
5. Report controlled-eligible and reconstructed/diagnostic cases separately. A nominal holdout is no longer fresh once its feedback has shaped the next version. Record exposure rather than relabeling it independent. Root judgment can challenge the judge with evidence; preserve the original judgment and record the override separately.
6. Independently test routing and new formats using fresh fictional facts: organic education, cold paid, aware paid, body-only, UGC, skit, claymation and jumbotron. Check whether a different competent agent can execute the skill without the author coaching it.
7. Produce a before/after packet for the owner. Their actual review is a separate column. Published/paid performance is a later column with measured exposure, attribution and conversion outcomes.

## Portable runner

`tools/benchmark.py` prepares two arms or runs them using an authenticated current Codex CLI. By default it uses `gpt-6-astra` with high effort; a compatible CLI and account access are required. No provider credentials or private cases are bundled.

Input file:

```json
{"cases":[{"case_id":"example-001","input":"Write only the body of this paid ad. Supplied facts and draft: ..."}]}
```

Each arm file is a JSON list of instruction/reference paths, relative to that file or absolute. Include every reference the isolated writer needs. Run from a private workspace and keep output outside the portable repository:

```bash
python3 tools/benchmark.py --cases /private/writer-inputs.json --arm-a /private/recovered-files.json --arm-b /private/candidate-files.json --out /private/prepared-run
python3 tools/benchmark.py --cases /private/writer-inputs.json --arm-a /private/recovered-files.json --arm-b /private/candidate-files.json --out /private/executed-run --run
```

The runner saves blind packets; judging and editorial adjudication remain deliberate steps. Inspect traces for any tool use and inspect outputs for self-identifying phrases before judging. Read-only sandboxing does not guarantee a perfectly isolated research experiment. Keep artifacts for failed runs and record failure; do not silently retry until a preferred winner appears.
