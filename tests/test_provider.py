import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "skills" / "viral-research" / "scripts" / "provider.py"
SPEC = importlib.util.spec_from_file_location("viral_provider", MODULE_PATH)
PROVIDER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(PROVIDER)


class ForeplayTests(unittest.TestCase):
    def test_pagination_replays_cursor_and_stops_at_credit_budget(self):
        calls = []

        def fake_request(method, url, headers=None, body=None, timeout=30):
            calls.append(url)
            if "cursor=next" in url:
                return {"data": [{"id": "3"}], "metadata": {"cursor": None}}, {}, 200
            return {"data": [{"id": "1"}, {"id": "2"}], "metadata": {"cursor": "next"}}, {}, 200

        with mock.patch.object(PROVIDER, "_json_request", side_effect=fake_request), mock.patch.dict(os.environ, {"FOREPLAY_API_KEY": "test-key"}):
            items, pages, cursor = PROVIDER.foreplay_paginate("/api/discovery/ads", {"query": "x"}, 3, 2, 10)
        self.assertEqual(["1", "2", "3"], [item["id"] for item in items])
        self.assertEqual(2, len(pages))
        self.assertIsNone(cursor)
        self.assertIn("limit=1", calls[1])

    def test_saved_manifest_contains_no_credential(self):
        pages = [{"page": 1, "request": {"query": "x"}, "response": {"data": [{"id": "1"}], "metadata": {"cursor": None}}}]
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(PROVIDER, "foreplay_paginate", return_value=([{"id": "1"}], pages, None)):
            manifest = PROVIDER.save_foreplay_collection(Path(directory) / "fresh", "ads", {"query": "x"}, 5, 5, 1)
            encoded = json.dumps(manifest)
            self.assertNotIn("Authorization", encoded)
            self.assertNotIn("API_KEY", encoded)
            self.assertEqual(1, manifest["items_retrieved"])

    def test_existing_output_stops_before_paid_request(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(PROVIDER, "foreplay_paginate") as paginate:
            with self.assertRaisesRegex(PROVIDER.ProviderError, "output path already exists"):
                PROVIDER.save_foreplay_collection(Path(directory), "ads", {"query": "x"}, 5, 5, 1)
            paginate.assert_not_called()

    def test_successful_page_is_persisted_when_later_page_fails(self):
        calls = 0

        def fake_request(method, url, headers=None, body=None, timeout=30):
            nonlocal calls
            calls += 1
            if calls == 1:
                return {"data": [{"id": "1"}], "metadata": {"cursor": "next"}}, {}, 200
            raise PROVIDER.ProviderError("provider returned HTTP 503")

        with tempfile.TemporaryDirectory() as directory, mock.patch.object(PROVIDER, "_json_request", side_effect=fake_request), mock.patch.dict(os.environ, {"FOREPLAY_API_KEY": "secret"}):
            out = Path(directory) / "fresh"
            with self.assertRaises(PROVIDER.ProviderError):
                PROVIDER.save_foreplay_collection(out, "ads", {"query": "x"}, 5, 1, 5)
            self.assertEqual([{"id": "1"}], json.loads((out / "items.json").read_text()))
            manifest = json.loads((out / "manifest.json").read_text())
            self.assertEqual("partial_failed", manifest["collection_status"])
            self.assertEqual(1, manifest["pages_retrieved"])


class ApifyTests(unittest.TestCase):
    def test_dataset_pagination_preserves_raw_pages_and_reports_cap(self):
        def fake_request(method, url, headers=None, body=None, timeout=30):
            query = dict(PROVIDER.urllib.parse.parse_qsl(PROVIDER.urllib.parse.urlsplit(url).query))
            offset = int(query.get("offset", 0))
            if offset == 0:
                return [{"id": 1}, {"id": 2}], {"X-Apify-Pagination-Total": "5"}, 200
            return [{"id": 3}], {"X-Apify-Pagination-Total": "5"}, 200

        with tempfile.TemporaryDirectory() as directory, mock.patch.object(PROVIDER, "_json_request", side_effect=fake_request), mock.patch.dict(os.environ, {"APIFY_TOKEN": "test-token"}):
            manifest = PROVIDER.save_apify_dataset("dataset", Path(directory) / "fresh", 2, 3)
            self.assertEqual(3, manifest["items_retrieved"])
            self.assertFalse(manifest["dataset_complete"])
            self.assertNotIn("complete_under_query", manifest)
            self.assertEqual(3, manifest["next_offset"])
            self.assertTrue((Path(directory) / "fresh" / "raw" / "page-0002.json").exists())

    def test_actor_start_requires_and_transmits_provider_caps(self):
        calls = []

        def fake_request(method, url, headers=None, body=None, timeout=30):
            calls.append((method, url, body))
            if method == "POST":
                return {"data": {"id": "run1", "defaultDatasetId": "data1", "status": "SUCCEEDED", "usageTotalUsd": 0.03}}, {}, 201
            raise AssertionError("unexpected poll")

        with tempfile.TemporaryDirectory() as directory, mock.patch.object(PROVIDER, "_json_request", side_effect=fake_request), mock.patch.object(PROVIDER, "save_apify_dataset", return_value={"items_retrieved": 2}), mock.patch.dict(os.environ, {"APIFY_TOKEN": "test-token"}):
            manifest = PROVIDER.run_apify_actor("actor", {"x": 1}, Path(directory) / "fresh", 10, 0.25, 60, 10)
            query = dict(PROVIDER.urllib.parse.parse_qsl(PROVIDER.urllib.parse.urlsplit(calls[0][1]).query))
            self.assertEqual("10", query["maxItems"])
            self.assertEqual("0.2500", query["maxTotalChargeUsd"])
            self.assertEqual("run1", manifest["run_id"])

    def test_actor_poll_failure_preserves_recovery_ids(self):
        def fake_request(method, url, headers=None, body=None, timeout=30):
            if method == "POST":
                return {"data": {"id": "run1", "defaultDatasetId": "data1", "status": "RUNNING"}}, {}, 201
            raise PROVIDER.ProviderError("provider request unavailable")

        with tempfile.TemporaryDirectory() as directory, mock.patch.object(PROVIDER, "_json_request", side_effect=fake_request), mock.patch.object(PROVIDER.time, "sleep"), mock.patch.dict(os.environ, {"APIFY_TOKEN": "test-token"}):
            out = Path(directory) / "fresh"
            with self.assertRaises(PROVIDER.ProviderError):
                PROVIDER.run_apify_actor("actor", {"x": 1}, out, 10, 0.25, 60, 10)
            manifest = json.loads((out / "manifest.json").read_text())
            self.assertEqual("run1", manifest["run_id"])
            self.assertEqual("data1", manifest["dataset_id"])
            self.assertEqual("partial_failed", manifest["collection_status"])
            self.assertTrue(manifest["recoverable"])


class McpTests(unittest.TestCase):
    def test_sse_parser_returns_last_json_event(self):
        text = "event: message\ndata: {\"jsonrpc\":\"2.0\",\"result\":{\"tools\":[]}}\n\n"
        self.assertEqual([], PROVIDER.parse_sse_json(text)["result"]["tools"])

    def test_missing_credential_names_variable_without_value(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(PROVIDER.ProviderError, "APIFY_TOKEN is not configured"):
                PROVIDER.apify_headers()

    def test_tools_list_handles_empty_notification_and_paginates(self):
        calls = []

        def fake_request(method, url, headers=None, body=None, timeout=30):
            calls.append((dict(headers or {}), body))
            if body["method"] == "initialize":
                return {"result": {"protocolVersion": "2025-06-18"}}, {"Mcp-Session-Id": "session"}, 200
            if body["method"] == "notifications/initialized":
                return None, {}, 202
            if body["params"] == {}:
                return {"result": {"tools": [{"name": "one"}], "nextCursor": "next"}}, {}, 200
            return {"result": {"tools": [{"name": "two"}]}}, {}, 200

        with mock.patch.object(PROVIDER, "_json_request", side_effect=fake_request):
            result = PROVIDER.mcp_tools("https://mcp.example", None)
        self.assertEqual(["one", "two"], [item["name"] for item in result["result"]["tools"]])
        self.assertEqual("next", calls[-1][1]["params"]["cursor"])
        self.assertEqual("2025-06-18", calls[-1][0]["MCP-Protocol-Version"])

    def test_json_request_accepts_empty_202_response(self):
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.status = 202
        response.headers = {}
        response.read.return_value = b""
        with mock.patch.object(PROVIDER.urllib.request, "urlopen", return_value=response):
            body, _, status = PROVIDER._json_request("POST", "https://mcp.example", body={"jsonrpc": "2.0"})
        self.assertIsNone(body)
        self.assertEqual(202, status)


class ValidationTests(unittest.TestCase):
    def test_positive_number_rejects_non_finite_values(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value), self.assertRaises(PROVIDER.ProviderError):
                PROVIDER._positive_number(value, "budget")


if __name__ == "__main__":
    unittest.main()
