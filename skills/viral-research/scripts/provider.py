#!/usr/bin/env python3
"""Bounded acquisition helpers for Foreplay, Apify, and HTTP MCP servers.

Python 3.9+, standard library only. Credentials are read from environment
variables and are never accepted as command-line arguments or written to disk.
Every paid operation requires an explicit task budget.
"""

import argparse
import hashlib
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


FOREPLAY_BASE = "https://public.api.foreplay.co"
APIFY_BASE = "https://api.apify.com/v2"
DEFAULT_TIMEOUT = 30


class ProviderError(RuntimeError):
    """A provider request failed without exposing credential material."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ProviderError("{} is not configured in this process".format(name))
    return value


def _positive_number(value: float, label: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ProviderError("{} must be a finite number greater than zero".format(label))
    return number


def _create_fresh_output(path: Path) -> None:
    """Create a new evidence directory before any provider request is made."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.mkdir()
    except FileExistsError:
        raise ProviderError("output path already exists; choose a fresh directory: {}".format(path)) from None


def _json_request(
    method: str,
    url: str,
    headers: Optional[Mapping[str, str]] = None,
    body: Optional[Any] = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> Tuple[Any, Mapping[str, str], int]:
    payload = None if body is None else json.dumps(body).encode("utf-8")
    request_headers = {"Accept": "application/json"}
    request_headers.update(dict(headers or {}))
    if payload is not None:
        request_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=payload, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            if not raw and response.status in (202, 204):
                return None, response.headers, response.status
            content_type = response.headers.get("Content-Type", "")
            if "text/event-stream" in content_type:
                parsed = parse_sse_json(raw.decode("utf-8", "replace"))
            else:
                parsed = json.loads(raw.decode("utf-8"))
            return parsed, response.headers, response.status
    except urllib.error.HTTPError as exc:
        # Provider bodies can echo request values. Never surface them in CLI errors.
        try:
            exc.read(200000)
        except Exception:
            pass
        raise ProviderError("provider returned HTTP {}".format(exc.code)) from None
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ProviderError("provider request unavailable: {}".format(type(exc).__name__)) from None
    except json.JSONDecodeError:
        raise ProviderError("provider returned invalid JSON") from None


def _query_url(base: str, params: Mapping[str, Any]) -> str:
    pairs: List[Tuple[str, str]] = []
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            pairs.extend((key, str(item)) for item in value)
        else:
            pairs.append((key, str(value)))
    query = urllib.parse.urlencode(pairs)
    return base + ("?" + query if query else "")


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def _request_fingerprint(provider: str, operation: str, params: Mapping[str, Any]) -> str:
    clean = {key: params[key] for key in sorted(params) if "token" not in key.lower() and "key" not in key.lower()}
    encoded = json.dumps({"provider": provider, "operation": operation, "params": clean}, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def foreplay_headers() -> Dict[str, str]:
    # Live API accepts the documented Bearer form and the legacy raw-key form.
    return {"Authorization": "Bearer " + require_env("FOREPLAY_API_KEY")}


def foreplay_usage() -> Dict[str, Any]:
    body, _, _ = _json_request("GET", FOREPLAY_BASE + "/api/usage", foreplay_headers())
    return dict(body.get("data") or {})


def foreplay_search_brands(query: str, limit: int) -> Dict[str, Any]:
    if not query.strip():
        raise ProviderError("brand query must not be empty")
    bounded = max(1, min(int(limit), 100))
    url = _query_url(FOREPLAY_BASE + "/api/discovery/brands", {"query": query, "limit": bounded, "include_empty": "true"})
    body, _, _ = _json_request("GET", url, foreplay_headers())
    return body


def foreplay_paginate(
    path: str,
    params: Mapping[str, Any],
    credit_budget: int,
    page_limit: int,
    max_pages: int,
    page_sink: Optional[Callable[[int, Mapping[str, Any], Sequence[Mapping[str, Any]], Optional[str]], None]] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Optional[str]]:
    budget = int(_positive_number(credit_budget, "credit budget"))
    per_page = max(1, min(int(page_limit), 250, budget))
    pages_cap = max(1, int(max_pages))
    items: List[Dict[str, Any]] = []
    page_records: List[Dict[str, Any]] = []
    cursor: Optional[str] = None
    for page_index in range(pages_cap):
        remaining = budget - len(items)
        if remaining <= 0:
            break
        request_params = dict(params)
        request_params["limit"] = min(per_page, remaining)
        if cursor:
            request_params["cursor"] = cursor
        body, _, _ = _json_request("GET", _query_url(FOREPLAY_BASE + path, request_params), foreplay_headers())
        page_items = body.get("data") or []
        if not isinstance(page_items, list):
            raise ProviderError("Foreplay data envelope was not an array")
        metadata = body.get("metadata") or {}
        page_records.append({"page": page_index + 1, "request": request_params, "response": body})
        items.extend(item for item in page_items if isinstance(item, dict))
        next_cursor = metadata.get("cursor")
        next_cursor = str(next_cursor) if next_cursor not in (None, "") else None
        if page_sink:
            page_sink(page_index + 1, body, items, next_cursor)
        if not next_cursor or next_cursor == cursor or not page_items:
            cursor = next_cursor
            break
        cursor = next_cursor
    return items[:budget], page_records, cursor


def save_foreplay_collection(
    output: Path,
    operation: str,
    params: Mapping[str, Any],
    credit_budget: int,
    page_limit: int,
    max_pages: int,
) -> Dict[str, Any]:
    if operation == "ads":
        path = "/api/discovery/ads"
    elif operation == "brand-ads":
        path = "/api/brand/getAdsByBrandId"
    else:
        raise ProviderError("unsupported Foreplay operation")
    _create_fresh_output(output)
    base_manifest = {
        "provider": "foreplay",
        "operation": operation,
        "started_at": utc_now(),
        "request_fingerprint": _request_fingerprint("foreplay", operation, params),
        "request": dict(params),
        "credit_budget": int(credit_budget),
        "items_file": "items.json",
    }
    _atomic_json(output / "manifest.json", dict(base_manifest, collection_status="starting", pages_retrieved=0, items_retrieved=0, raw_pages=[]))

    def persist_page(index: int, response: Mapping[str, Any], current_items: Sequence[Mapping[str, Any]], next_cursor: Optional[str]) -> None:
        page_name = "raw/page-{:04d}.json".format(index)
        _atomic_json(output / page_name, response)
        _atomic_json(output / "items.json", list(current_items))
        partial = dict(base_manifest)
        partial.update({
            "updated_at": utc_now(),
            "collection_status": "running",
            "pages_retrieved": index,
            "items_retrieved": len(current_items),
            "next_cursor": next_cursor,
            "complete_under_query": False,
            "raw_pages": ["raw/page-{:04d}.json".format(i) for i in range(1, index + 1)],
        })
        _atomic_json(output / "manifest.json", partial)

    try:
        items, pages, next_cursor = foreplay_paginate(path, params, credit_budget, page_limit, max_pages, page_sink=persist_page)
    except Exception as exc:
        partial_path = output / "manifest.json"
        partial = json.loads(partial_path.read_text(encoding="utf-8"))
        partial.update({"updated_at": utc_now(), "collection_status": "partial_failed", "failure": type(exc).__name__})
        _atomic_json(partial_path, partial)
        raise
    _atomic_json(output / "items.json", items)
    manifest = dict(base_manifest)
    manifest.update({
        "retrieved_at": utc_now(),
        "collection_status": "complete",
        "pages_retrieved": len(pages),
        "items_retrieved": len(items),
        "next_cursor": next_cursor,
        "complete_under_query": next_cursor is None and len(items) < int(credit_budget),
        "raw_pages": ["raw/page-{:04d}.json".format(index) for index in range(1, len(pages) + 1)],
    })
    _atomic_json(output / "manifest.json", manifest)
    return manifest


def apify_headers() -> Dict[str, str]:
    return {"Authorization": "Bearer " + require_env("APIFY_TOKEN")}


def apify_account() -> Dict[str, Any]:
    user, _, _ = _json_request("GET", APIFY_BASE + "/users/me", apify_headers())
    usage, _, _ = _json_request("GET", APIFY_BASE + "/users/me/usage/monthly", apify_headers())
    limits, _, _ = _json_request("GET", APIFY_BASE + "/users/me/limits", apify_headers())
    return {"user": user.get("data") or {}, "usage": usage.get("data") or {}, "limits": limits.get("data") or {}}


def save_apify_dataset(dataset_id: str, output: Path, page_size: int, max_items: int) -> Dict[str, Any]:
    if not dataset_id.strip():
        raise ProviderError("dataset id must not be empty")
    bounded_page = max(1, min(int(page_size), 1000))
    item_cap = int(_positive_number(max_items, "max items"))
    _create_fresh_output(output)
    offset = 0
    items: List[Any] = []
    raw_pages: List[str] = []
    provider_total: Optional[int] = None
    base_manifest = {
        "provider": "apify",
        "operation": "dataset-items",
        "started_at": utc_now(),
        "dataset_id": dataset_id,
        "request_fingerprint": _request_fingerprint("apify", "dataset-items", {"dataset_id": dataset_id}),
        "page_size": bounded_page,
        "max_items": item_cap,
        "items_file": "items.json",
    }
    _atomic_json(output / "manifest.json", dict(base_manifest, collection_status="starting", pages_retrieved=0, items_retrieved=0, raw_pages=[]))
    while len(items) < item_cap:
        limit = min(bounded_page, item_cap - len(items))
        url = _query_url(APIFY_BASE + "/datasets/{}/items".format(urllib.parse.quote(dataset_id)), {"offset": offset, "limit": limit, "clean": 0, "format": "json"})
        try:
            page, headers, _ = _json_request("GET", url, apify_headers())
        except Exception as exc:
            partial = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            partial.update({"updated_at": utc_now(), "collection_status": "partial_failed", "failure": type(exc).__name__, "next_offset": offset})
            _atomic_json(output / "manifest.json", partial)
            raise
        if not isinstance(page, list):
            raise ProviderError("Apify dataset page was not an array")
        page_name = "raw/page-{:04d}.json".format(len(raw_pages) + 1)
        _atomic_json(output / page_name, page)
        raw_pages.append(page_name)
        items.extend(page)
        total_header = headers.get("X-Apify-Pagination-Total")
        if total_header is not None:
            provider_total = int(total_header)
        offset += len(page)
        _atomic_json(output / "items.json", items)
        partial = dict(base_manifest)
        partial.update({
            "updated_at": utc_now(),
            "collection_status": "running",
            "pages_retrieved": len(raw_pages),
            "items_retrieved": len(items),
            "provider_total": provider_total,
            "dataset_complete": provider_total is not None and len(items) >= provider_total,
            "next_offset": offset,
            "raw_pages": raw_pages,
        })
        _atomic_json(output / "manifest.json", partial)
        if not page or len(page) < limit or (provider_total is not None and offset >= provider_total):
            break
    _atomic_json(output / "items.json", items)
    complete = provider_total is not None and len(items) >= provider_total
    manifest = dict(base_manifest)
    manifest.update({
        "retrieved_at": utc_now(),
        "collection_status": "complete",
        "pages_retrieved": len(raw_pages),
        "items_retrieved": len(items),
        "provider_total": provider_total,
        "dataset_complete": complete,
        "next_offset": None if complete else len(items),
        "raw_pages": raw_pages,
    })
    _atomic_json(output / "manifest.json", manifest)
    return manifest


def run_apify_actor(
    actor: str,
    run_input: Mapping[str, Any],
    output: Path,
    max_items: int,
    max_cost_usd: float,
    poll_timeout: int,
    page_size: int,
) -> Dict[str, Any]:
    item_cap = int(_positive_number(max_items, "max items"))
    cost_cap = _positive_number(max_cost_usd, "max cost USD")
    if poll_timeout <= 0:
        raise ProviderError("poll timeout must be greater than zero")
    _create_fresh_output(output)
    params = {"maxItems": item_cap, "maxTotalChargeUsd": "{:.4f}".format(cost_cap), "waitForFinish": 0}
    url = _query_url(APIFY_BASE + "/acts/{}/runs".format(urllib.parse.quote(actor)), params)
    body, _, _ = _json_request("POST", url, apify_headers(), dict(run_input), timeout=60)
    run = body.get("data") or {}
    run_id = run.get("id")
    dataset_id = run.get("defaultDatasetId")
    if not run_id or not dataset_id:
        raise ProviderError("Apify start response omitted run or dataset id")
    _atomic_json(output / "run.json", run)
    recovery_manifest = {
        "provider": "apify",
        "operation": "actor-run",
        "started_at": utc_now(),
        "collection_status": "started",
        "actor": actor,
        "run_id": run_id,
        "dataset_id": dataset_id,
        "max_cost_usd": cost_cap,
        "max_items": item_cap,
        "run_file": "run.json",
        "request_fingerprint": _request_fingerprint("apify", "actor-run", {"actor": actor, "input": run_input, "max_items": item_cap, "max_cost_usd": cost_cap}),
    }
    _atomic_json(output / "manifest.json", recovery_manifest)
    deadline = time.monotonic() + poll_timeout
    status = run.get("status")
    try:
        while status in ("READY", "RUNNING") and time.monotonic() < deadline:
            time.sleep(5)
            latest, _, _ = _json_request("GET", APIFY_BASE + "/actor-runs/{}".format(run_id), apify_headers())
            run = latest.get("data") or {}
            status = run.get("status")
            _atomic_json(output / "run.json", run)
    except Exception as exc:
        recovery_manifest.update({"updated_at": utc_now(), "collection_status": "partial_failed", "failure": type(exc).__name__, "run_status": status, "recoverable": True})
        _atomic_json(output / "manifest.json", recovery_manifest)
        raise
    _atomic_json(output / "run.json", run)
    if status != "SUCCEEDED":
        recovery_manifest.update({"updated_at": utc_now(), "collection_status": "partial_failed", "run_status": status, "recoverable": True})
        _atomic_json(output / "manifest.json", recovery_manifest)
        raise ProviderError("Apify run {} ended or timed out with status {}; dataset {} remains recoverable".format(run_id, status, dataset_id))
    manifest = save_apify_dataset(str(dataset_id), output / "dataset", page_size, item_cap)
    requested_source_limit = run_input.get("resultsLimit")
    hit_source_limit = isinstance(requested_source_limit, (int, float)) and len(json.loads((output / "dataset" / "items.json").read_text(encoding="utf-8"))) >= int(requested_source_limit)
    manifest.update({
        "operation": "actor-run",
        "actor": actor,
        "run_id": run_id,
        "dataset_id": dataset_id,
        "max_cost_usd": cost_cap,
        "max_items": item_cap,
        "usage_total_usd": run.get("usageTotalUsd"),
        "source_history_complete": False if hit_source_limit else None,
        "source_history_complete_reason": "actor result limit reached" if hit_source_limit else "actor returned fewer items than requested; account exhaustion was not independently verified",
        "run_file": "run.json",
        "dataset_manifest": "dataset/manifest.json",
        "request_fingerprint": _request_fingerprint("apify", "actor-run", {"actor": actor, "input": run_input, "max_items": item_cap, "max_cost_usd": cost_cap}),
    })
    _atomic_json(output / "manifest.json", manifest)
    return manifest


def parse_sse_json(text: str) -> Any:
    events: List[Any] = []
    for line in text.splitlines():
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if payload and payload != "[DONE]":
            events.append(json.loads(payload))
    if not events:
        raise ProviderError("MCP server returned an empty event stream")
    return events[-1]


def mcp_tools(url: str, token_env: Optional[str]) -> Dict[str, Any]:
    headers = {"Accept": "application/json, text/event-stream"}
    if token_env:
        headers["Authorization"] = "Bearer " + require_env(token_env)
    initialize = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "viral-provider", "version": "1"}},
    }
    initialized, response_headers, _ = _json_request("POST", url, headers, initialize)
    negotiated = ((initialized or {}).get("result") or {}).get("protocolVersion") or "2025-06-18"
    headers["MCP-Protocol-Version"] = str(negotiated)
    session_id = response_headers.get("Mcp-Session-Id") or response_headers.get("mcp-session-id")
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    _json_request("POST", url, headers, {"jsonrpc": "2.0", "method": "notifications/initialized"})
    tools: List[Any] = []
    cursor: Optional[str] = None
    request_id = 2
    while True:
        params = {"cursor": cursor} if cursor else {}
        body, _, _ = _json_request("POST", url, headers, {"jsonrpc": "2.0", "id": request_id, "method": "tools/list", "params": params})
        result = (body or {}).get("result") or {}
        tools.extend(result.get("tools") or [])
        next_cursor = result.get("nextCursor")
        if not next_cursor or next_cursor == cursor:
            return {"jsonrpc": "2.0", "result": {"tools": tools, "nextCursor": next_cursor, "protocolVersion": negotiated}}
        cursor = str(next_cursor)
        request_id += 1


def _probe_media_url(url: str, timeout: int) -> Dict[str, Any]:
    headers = {"User-Agent": "Mozilla/5.0", "Range": "bytes=0-0", "Accept": "*/*"}
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response.read(1)
            return {
                "ok": 200 <= response.status < 400,
                "status": response.status,
                "content_type": response.headers.get("Content-Type"),
                "content_length": response.headers.get("Content-Length"),
            }
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status": exc.code, "content_type": exc.headers.get("Content-Type"), "content_length": exc.headers.get("Content-Length")}
    except Exception as exc:
        return {"ok": False, "status": None, "error": type(exc).__name__}


def validate_media_urls(input_path: Path, output_path: Path, fields: Sequence[str], workers: int, timeout: int) -> Dict[str, Any]:
    records = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ProviderError("media input must be a JSON array")
    probes: List[Tuple[str, str, str]] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            continue
        record_id = str(record.get("shortCode") or record.get("id") or index)
        for field in fields:
            value = record.get(field)
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                probes.append((record_id, field, value))
    results: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, min(int(workers), 32))) as pool:
        futures = {pool.submit(_probe_media_url, url, timeout): (record_id, field, url) for record_id, field, url in probes}
        for future in as_completed(futures):
            record_id, field, url = futures[future]
            result = future.result()
            result.update({"record_id": record_id, "field": field, "url": url})
            results.append(result)
    results.sort(key=lambda item: (item["record_id"], item["field"]))
    report = {
        "checked_at": utc_now(),
        "input": str(input_path),
        "fields": list(fields),
        "urls_checked": len(results),
        "valid": sum(1 for item in results if item["ok"]),
        "invalid": sum(1 for item in results if not item["ok"]),
        "results": results,
    }
    _atomic_json(output_path, report)
    return {key: report[key] for key in ("checked_at", "fields", "urls_checked", "valid", "invalid")}


def _load_json_object(path: Path) -> Dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ProviderError("{} must contain a JSON object".format(path))
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("foreplay-usage")
    brands = sub.add_parser("foreplay-brands")
    brands.add_argument("--query", required=True)
    brands.add_argument("--limit", type=int, default=5)

    for name in ("foreplay-ads", "foreplay-brand-ads"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--out", type=Path, required=True)
        cmd.add_argument("--credit-budget", type=int, required=True)
        cmd.add_argument("--page-limit", type=int, default=50)
        cmd.add_argument("--max-pages", type=int, default=20)
        cmd.add_argument("--order", default="newest")
        if name == "foreplay-ads":
            cmd.add_argument("--query", required=True)
        else:
            cmd.add_argument("--brand-id", action="append", required=True)
        cmd.add_argument("--display-format", action="append")
        cmd.add_argument("--platform", action="append")
        cmd.add_argument("--live", choices=("true", "false"))

    sub.add_parser("apify-account")
    dataset = sub.add_parser("apify-dataset")
    dataset.add_argument("--dataset-id", required=True)
    dataset.add_argument("--out", type=Path, required=True)
    dataset.add_argument("--page-size", type=int, default=250)
    dataset.add_argument("--max-items", type=int, required=True)

    run = sub.add_parser("apify-run")
    run.add_argument("--actor", required=True)
    run.add_argument("--input", type=Path, required=True)
    run.add_argument("--out", type=Path, required=True)
    run.add_argument("--max-items", type=int, required=True)
    run.add_argument("--max-cost-usd", type=float, required=True)
    run.add_argument("--poll-timeout", type=int, default=1800)
    run.add_argument("--page-size", type=int, default=250)

    mcp = sub.add_parser("mcp-tools")
    mcp.add_argument("--url", required=True)
    mcp.add_argument("--token-env")

    media = sub.add_parser("validate-media")
    media.add_argument("--input", type=Path, required=True)
    media.add_argument("--out", type=Path, required=True)
    media.add_argument("--field", action="append", required=True)
    media.add_argument("--workers", type=int, default=8)
    media.add_argument("--timeout", type=int, default=20)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "foreplay-usage":
            result = foreplay_usage()
        elif args.command == "foreplay-brands":
            result = foreplay_search_brands(args.query, args.limit)
        elif args.command in ("foreplay-ads", "foreplay-brand-ads"):
            params: Dict[str, Any] = {"order": args.order}
            if args.command == "foreplay-ads":
                params["query"] = args.query
                operation = "ads"
            else:
                params["brand_ids"] = args.brand_id
                operation = "brand-ads"
            if args.display_format:
                params["display_format"] = args.display_format
            if args.platform:
                params["publisher_platform"] = args.platform
            if args.live is not None:
                params["live"] = args.live
            result = save_foreplay_collection(args.out, operation, params, args.credit_budget, args.page_limit, args.max_pages)
        elif args.command == "apify-account":
            result = apify_account()
        elif args.command == "apify-dataset":
            result = save_apify_dataset(args.dataset_id, args.out, args.page_size, args.max_items)
        elif args.command == "apify-run":
            result = run_apify_actor(args.actor, _load_json_object(args.input), args.out, args.max_items, args.max_cost_usd, args.poll_timeout, args.page_size)
        elif args.command == "mcp-tools":
            result = mcp_tools(args.url, args.token_env)
        elif args.command == "validate-media":
            result = validate_media_urls(args.input, args.out, args.field, args.workers, args.timeout)
        else:
            raise ProviderError("unknown command")
    except (ProviderError, OSError, ValueError) as exc:
        print("provider: {}".format(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
