from __future__ import annotations

import difflib
import json
from pathlib import Path
import re
import shutil
import tempfile
import unittest

from benchmark.devopsbench100 import builder
from benchmark.devopsbench100.realism import (
    case_contract,
    reference_calls,
    release_prompt,
    seed_case_evidence,
    validate_native_asset,
    write_asset_views,
)
from benchmark.devopsbench100.run_suite import CONTROL_NAMES, _matches, negative_plans


ROOT = Path(__file__).resolve().parents[3]


class DevOpsRealismTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = json.loads(
            (ROOT / "benchmark" / "devopsbench100" / "catalog.json").read_text()
        )["tasks"]
        cls.source_tasks = {
            task["task_id"]: task
            for task in json.loads((ROOT / "world" / "tasks.json").read_text())
        }
        cls.tools = {
            tool["name"]: tool
            for tool in json.loads((ROOT / "world" / "tools.json").read_text())
        }
        cls.contracts = []
        for row in cls.catalog:
            source = cls.source_tasks[row["task_id"]]
            contract = case_contract(row, source)
            prompt = release_prompt(
                row, builder.employee_instruction(source, row), contract
            )
            calls, trace = reference_calls(row, source, contract, cls.tools)
            cls.contracts.append((row, source, contract, prompt, calls, trace))

    def test_high_level_prompts_are_distinct_human_requests(self) -> None:
        prompts = [item[3] for item in self.contracts]
        self.assertEqual(100, len(set(prompts)))
        words = [len(prompt.split()) for prompt in prompts]
        self.assertGreaterEqual(min(words), 45)
        self.assertLessEqual(max(words), 220)
        self.assertFalse(any(builder.PROMPT_LEAKAGE_PATTERN.search(p) for p in prompts))

        token_sets = [set(re.findall(r"[a-z0-9]+", p.casefold())) for p in prompts]
        maximum = max(
            len(left & right) / len(left | right)
            for index, left in enumerate(token_sets)
            for right in token_sets[index + 1:]
        )
        self.assertLess(maximum, 0.72)

    def test_raw_and_semantic_paths_are_unique_and_deep(self) -> None:
        sequences = [tuple(call["tool"] for call in item[4]) for item in self.contracts]
        graphs = [tuple(item[5]["semantic_action_graph"]) for item in self.contracts]
        reads = [item[5]["context_call_count"] for item in self.contracts]
        self.assertEqual(100, len(set(sequences)))
        self.assertEqual(100, len(set(graphs)))
        self.assertGreaterEqual(min(reads), 19)
        self.assertGreaterEqual(min(map(len, sequences)), 24)

        maximum = max(
            difflib.SequenceMatcher(a=left, b=right, autojunk=False).ratio()
            for index, left in enumerate(sequences)
            for right in sequences[index + 1:]
        )
        self.assertLess(maximum, 0.985)

    def test_ten_negative_controls_apply_to_every_task(self) -> None:
        for row, source, contract, _prompt, calls, trace in self.contracts:
            reference = {
                "expected_calls": calls,
                "source_expected_calls": source["expected_calls"],
                "trace_contract": trace,
            }
            controls = negative_plans(reference)
            self.assertEqual(CONTROL_NAMES, tuple(controls), row["bench_id"])
            self.assertEqual(10, len(controls), row["bench_id"])
            self.assertFalse(controls["noop"]["calls"])
            self.assertTrue(controls["unauthorized_write"]["tamper_frozen_state"])

            incomplete = controls["incomplete_read"]["calls"]
            self.assertTrue(
                any(
                    not any(_matches(call, selector) for call in incomplete)
                    for selector in trace["required_context_calls"]
                ),
                row["bench_id"],
            )
            self.assertIn(
                controls["write_before_read"]["calls"][0]["tool"],
                trace["source_mutation_tools"],
                row["bench_id"],
            )
            handoff_index = next(
                index
                for index, call in enumerate(controls["missing_readback"]["calls"])
                if _matches(call, trace["handoff_call"])
            )
            self.assertFalse(
                any(
                    _matches(call, trace["readback_call"])
                    for call in controls["missing_readback"]["calls"][handoff_index + 1:]
                ),
                row["bench_id"],
            )

    def test_native_asset_room_has_real_parseable_formats(self) -> None:
        row, source, contract, prompt, _calls, _trace = self.contracts[0]
        with tempfile.TemporaryDirectory(prefix="dob_assets_") as temporary:
            temporary_root = Path(temporary)
            database = temporary_root / "environment.db"
            shutil.copy2(ROOT / "world" / "environment.db", database)
            seed_case_evidence(database, row, source, prompt, contract)
            asset_root = temporary_root / "task_files" / row["bench_id"]
            assets = write_asset_views(asset_root, database, prompt, row, contract)
            self.assertEqual(28, len(assets))
            suffixes = {asset_root.joinpath(Path(a["path"]).name).suffix[1:] for a in assets}
            self.assertTrue(
                {"csv", "eml", "json", "log", "md", "pdf", "sql", "txt", "xlsx", "yaml"}
                <= suffixes
            )
            self.assertTrue(all(validate_native_asset(path) for path in asset_root.iterdir()))


if __name__ == "__main__":
    unittest.main()
