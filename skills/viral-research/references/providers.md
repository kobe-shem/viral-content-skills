# Provider invocation and evidence preservation

Set `VIRAL_RESEARCH_SKILL` to the directory where this skill's `SKILL.md` was loaded, whether that is
an installed skill directory or a repository checkout. Use its [`provider.py`](../scripts/provider.py)
helper for HTTP providers. It is Python 3.9 compatible and uses only the standard library. It reads
credentials from the process environment, never from CLI flags. Keep account-specific secret files
and SSH details in the user's private project; do not copy them into this skill.

Every paid collection needs a task-specific item/credit/cost ceiling and a fresh output directory.
The helper refuses an existing path before making a request. Keep the generated `manifest.json`, raw
pages, combined items, and provider run record together. It updates evidence after each successful
page and saves Apify recovery IDs immediately after a start. `dataset_complete` only means all rows
in that provider dataset were downloaded. It does not establish that an Actor retrieved the full
source account history. Use `source_history_complete` and its reason on Actor-run manifests; a null
value means the Actor returned below the cap but account exhaustion was not independently verified.

## Foreplay

Credential: `FOREPLAY_API_KEY`. Base API: `https://public.api.foreplay.co`. The live API accepts
`Authorization: Bearer <key>` and the older raw-key header. The helper uses Bearer. Check free usage
before and after a collection:

```bash
python3 "$VIRAL_RESEARCH_SKILL/scripts/provider.py" foreplay-usage
```

Resolve advertiser identity with a deliberately small brand search:

```bash
python3 "$VIRAL_RESEARCH_SKILL/scripts/provider.py" foreplay-brands \
  --query "Creator or company" --limit 3
```

Collect paid ads by resolved Foreplay brand ID. Treat the requested page limits as the charge ceiling:
the observed usage delta can exceed the number of returned ads when a brand has fewer retrievable
records. Check the free usage endpoint before and after every bounded collection.

```bash
python3 "$VIRAL_RESEARCH_SKILL/scripts/provider.py" foreplay-brand-ads \
  --brand-id FOREPLAY_BRAND_ID \
  --credit-budget 250 --page-limit 50 --max-pages 10 \
  --out private/research/creator/paid/foreplay
```

`/api/discovery/ads` and `/api/brand/getAdsByBrandId` paginate with `metadata.cursor`; the helper
replays it until the provider ends pagination or the task budget/page cap is reached. It never sends
`collect=true`. Raw ad data can contain `full_transcription`, `timestamped_transcription`, top-level
image/video URLs, and DCO/carousel `cards[]`; preserve the complete payload before normalization.

## Sandcastles

Sandcastles uses an OAuth-backed HTTP MCP endpoint. Configure it in the MCP client that owns the
authorized account and discover the live tool list there. Do not invent tool names and do not copy
OAuth material between machines. A direct bearer-token environment can be inspected with:

```bash
python3 "$VIRAL_RESEARCH_SKILL/scripts/provider.py" mcp-tools \
  --url https://mcp.sandcastles.ai/ --token-env SANDCASTLES_MCP_TOKEN
```

If the account is stored in a client's OAuth session, use that configured client for actual calls;
`mcp-tools` is schema inventory, not a replacement OAuth client or scraper. Record active workspace,
account, remaining credits, reset date, tool schema, request args, response, and any `next_cursor`.
If live OAuth is unavailable, report it as blocked rather than relying on old credentials. Stored observations show that Sandcastles analysis is provider
interpretation: video detail may include spoken hook, topic, format, visual-layout labels, and
narrative sections without returning the full transcript/audio/scene record. Do not mark transcript,
visual, or audio coverage full unless the returned live schema and inspected source support it.

## Apify

Credential: `APIFY_TOKEN`. Inspect the active account and monthly usage without starting an Actor:

```bash
python3 "$VIRAL_RESEARCH_SKILL/scripts/provider.py" apify-account
```

Preserve an existing dataset before its retention window expires:

```bash
python3 "$VIRAL_RESEARCH_SKILL/scripts/provider.py" apify-dataset \
  --dataset-id DATASET_ID --max-items 1000 --page-size 250 \
  --out private/research/creator/organic/apify-existing
```

Start a fresh Actor only with provider-level `maxItems` and `maxTotalChargeUsd`. The helper starts
once, polls the returned run ID, and recovers results from that run's dataset; it never retries a
start after an ambiguous timeout.

```bash
python3 "$VIRAL_RESEARCH_SKILL/scripts/provider.py" apify-run \
  --actor apify~instagram-scraper --input private/request.json \
  --max-items 300 --max-cost-usd 1.00 \
  --out private/research/creator/organic/apify-run
```

Dataset pagination uses `offset` and `limit` plus Apify's `X-Apify-Pagination-*` response headers.
The helper saves every raw page and reports `provider_total`, `next_offset`, and dataset completeness. Actor
schemas and pricing change; fetch the current Actor detail/input schema immediately before a paid run
and store the selected actor/build/pricing evidence with the request.

Validate preserved CDN media before selecting forensic examples:

```bash
python3 "$VIRAL_RESEARCH_SKILL/scripts/provider.py" validate-media \
  --input private/research/creator/organic/apify-existing/items.json \
  --field videoUrl --field audioUrl \
  --out private/research/creator/organic/apify-existing/media-validation.json
```

## Account isolation and remote execution

When credentials live on another authorized host, run the same helper on that host with the secret
loaded there. Do not pass a token in SSH arguments or copy it locally. Record the host/account alias
in the private run manifest outside this reusable skill. Compare pre/post usage to the task budget and
stop if an account, workspace, plan, or schema differs from the approved one.
