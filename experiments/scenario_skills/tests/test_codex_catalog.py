"""Metadata discovery is independent of model turns and production tool calls."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from experiments.scenario_skills.codex_catalog import capture, discover, original_catalog
from experiments.scenario_skills.common import digest, read, write


def status():
    tool = {"name": "synthetic_read", "title": "Read fixture", "description": "Unmodified original text",
            "inputSchema": {"type": "object", "required": ["id"], "properties": {"id": {"type": "integer"}}},
            "outputSchema": {"type": "object", "additionalProperties": True},
            "annotations": {"readOnlyHint": True}, "_meta": {"revision": "synthetic"}}
    return {"id": 1, "result": {"data": [{"name": "cekura", "httpOrigin": "https://api.cekura.ai",
        "authStatus": "oAuth", "serverInfo": {"name": "Cekura API", "version": "synthetic"},
        "tools": {tool["name"]: tool}}], "nextCursor": None}}


class CodexCatalogTests(unittest.TestCase):
    def test_preserves_full_original_objects_and_records_zero_turns(self):
        raw = status()
        before = copy.deepcopy(raw)
        catalog, _ = original_catalog(raw)
        self.assertEqual(catalog, list(raw["result"]["data"][0]["tools"].values()))
        self.assertEqual(raw, before)
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            write(directory / "status.json", raw)
            output = capture(directory / "export", status_path=directory / "status.json")
            self.assertEqual(read(output), catalog)
            provenance = read(output.parent / "catalog-provenance.json")
            self.assertEqual(provenance["catalog_sha256"], digest(catalog))
            self.assertEqual(provenance["model_turns"], 0)
            self.assertEqual(provenance["tool_calls"], 0)

    def test_rejects_wrong_origin_errors_pagination_and_inferred_names(self):
        mutations = []
        value = status(); value["result"]["nextCursor"] = "more"; mutations.append(value)
        value = status(); value["error"] = {"message": "failed"}; mutations.append(value)
        value = status(); value["result"]["data"] *= 2; mutations.append(value)
        value = status(); value["result"]["data"][0]["httpOrigin"] = "https://example.org"; mutations.append(value)
        value = status(); value["result"]["data"][0]["toolsError"] = "partial"; mutations.append(value)
        value = status(); value["result"]["data"][0]["tools"] = {}; mutations.append(value)
        value = status(); value["result"]["data"][0]["tools"]["synthetic_read"]["name"] = "mcp__cekura__synthetic_read"; mutations.append(value)
        value = status(); del value["result"]["data"][0]["tools"]["synthetic_read"]["inputSchema"]; mutations.append(value)
        mutations += [None, {}, {"result": {"data": [None]}}]
        for value in mutations:
            with self.subTest(value=value), self.assertRaises(ValueError):
                original_catalog(value)

    def test_app_server_receives_only_metadata_methods_and_exits(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            binary = directory / "scripted-codex"
            binary.write_text('''#!/usr/bin/python3
import json,sys,pathlib
if "--version" in sys.argv:
    print("codex synthetic")
    sys.exit(0)
assert sys.argv[1:]==["app-server","--listen","stdio://"]
methods=[]
for line in sys.stdin:
    message=json.loads(line)
    methods.append(message["method"])
    if message["method"]=="initialize":
        print(json.dumps({"id":0,"result":{}}),flush=True)
    elif message["method"]=="mcpServerStatus/list":
        print(json.dumps(STATUS),flush=True)
pathlib.Path("methods.json").write_text(json.dumps(methods))
'''.replace("STATUS", repr(status())))
            binary.chmod(0o755)
            discovered, version = discover(directory / "work", binary=str(binary))
            self.assertEqual(discovered, status())
            self.assertEqual(version, "codex synthetic")
            self.assertEqual(read(directory / "work/methods.json"),
                             ["initialize", "initialized", "mcpServerStatus/list"])


if __name__ == "__main__":
    unittest.main()
