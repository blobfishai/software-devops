from __future__ import annotations

import difflib
import io
import json
from pathlib import Path
import re
import shutil
import tempfile
import unittest
import zipfile

from benchmark.devopsbench100 import builder
from benchmark.devopsbench100.realism import (
    FIXED_XLSX_ZIP_TIMESTAMP,
    augment_vcode,
    atomic_checks,
    case_contract,
    material_context_calls,
    reference_calls,
    release_prompt,
    seed_case_evidence,
    semantic_milestones,
    validate_native_asset,
    write_asset_views,
)
from benchmark.devopsbench100.run_suite import (
    CONTROL_NAMES,
    _matches,
    execute,
    negative_plans,
    stable_trace_value,
)


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

    def test_public_trace_normalizes_ephemeral_tool_directories(self) -> None:
        first = {
            "stderr": 'File "/private/var/folders/a/T/ws_first123/check.py"',
            "nested": ["/tmp/exercise_random456/runner.py"],
        }
        second = {
            "stderr": 'File "/private/var/folders/b/T/ws_second789/check.py"',
            "nested": ["/tmp/exercise_other012/runner.py"],
        }
        self.assertEqual(stable_trace_value(first), stable_trace_value(second))
        self.assertEqual(
            {
                "stderr": 'File "<task-workspace>/check.py"',
                "nested": ["<task-workspace>/runner.py"],
            },
            stable_trace_value(first),
        )

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

    def test_material_evidence_is_a_causal_subset_of_the_reference_room(self) -> None:
        for row, _source, contract, _prompt, calls, trace in self.contracts:
            material, groups = material_context_calls(row, contract)
            self.assertEqual(13, len(material), row["bench_id"])
            self.assertEqual(material, trace["required_context_calls"])
            self.assertEqual(groups, trace["material_context_groups"])
            self.assertGreaterEqual(trace["reference_context_call_count"], 19)
            self.assertGreaterEqual(
                trace["reference_context_call_count"] - len(material),
                6,
                row["bench_id"],
            )
            prefix = calls[: trace["reference_context_call_count"]]
            self.assertEqual(prefix, trace["reference_context_calls"])
            self.assertTrue(
                all(any(_matches(call, selector) for call in prefix) for selector in material),
                row["bench_id"],
            )
            self.assertGreaterEqual(len(trace["postwrite_readback_calls"]), 1)

    def test_semantic_rubrics_are_task_specific_and_total_one_hundred(self) -> None:
        descriptions = set()
        for row, source, contract, prompt, _calls, trace in self.contracts:
            task = {
                **source,
                "instruction": prompt,
                "vcode": augment_vcode(source["vcode"], row, contract, trace),
            }
            milestones = semantic_milestones(task, row, contract, trace)
            self.assertEqual(14, len(milestones), row["bench_id"])
            self.assertEqual(100, sum(item["weight"] for item in milestones))
            self.assertTrue(all(item["atomic_checks"] for item in milestones))
            assigned = [
                check["id"]
                for milestone in milestones
                for check in milestone["atomic_checks"]
            ]
            self.assertEqual(len(assigned), len(set(assigned)), row["bench_id"])
            self.assertEqual(
                sorted(check["id"] for check in atomic_checks(task["vcode"])),
                sorted(assigned),
                row["bench_id"],
            )
            descriptions.add(tuple(item["description"] for item in milestones))
        self.assertEqual(100, len(descriptions))

    def test_selector_matching_allows_safe_optional_arguments(self) -> None:
        selector = {
            "tool": "list_deployments",
            "args": {"service": "payments"},
        }
        self.assertTrue(
            _matches(
                {
                    "tool": "list_deployments",
                    "args": {
                        "service": "payments",
                        "environment": "production",
                        "limit": 50,
                    },
                },
                selector,
            )
        )
        self.assertFalse(
            _matches(
                {"tool": "list_deployments", "args": {"service": "search"}},
                selector,
            )
        )

    def test_runtime_skips_context_and_recovers_only_from_failed_reads(self) -> None:
        with tempfile.TemporaryDirectory(prefix="dob_semantic_runtime_") as temporary:
            release = Path(temporary) / "devopsbench-100"
            builder.build(release)
            row, source, _contract, _prompt, _calls, trace = self.contracts[0]
            pack = release / "harbor" / "tasks" / row["bench_id"]
            reference = json.loads((pack / "solution" / "reference.json").read_text())
            minimal_calls = [
                *trace["required_context_calls"],
                *source["expected_calls"],
                *trace["postwrite_readback_calls"],
                trace["handoff_call"],
                trace["readback_call"],
            ]
            skipped = trace["reference_context_call_count"] - len(
                trace["required_context_calls"]
            )
            self.assertGreaterEqual(skipped, 6)

            minimal, _ = execute(pack, minimal_calls, source["task_id"])
            self.assertTrue(minimal["passed"])
            self.assertEqual(1.0, minimal["reward"])

            recovered, _ = execute(
                pack,
                [{"tool": "jira_get_issue", "args": {}}, *minimal_calls],
                source["task_id"],
            )
            self.assertTrue(recovered["passed"])
            self.assertEqual(1, recovered["failed_tool_calls"])

            rejected_tool = next(
                call["tool"]
                for call in source["expected_calls"]
                if self.tools[call["tool"]].get("write_tables")
                and any(
                    parameter.get("required")
                    for parameter in self.tools[call["tool"]].get("parameters", [])
                )
            )
            rejected, _ = execute(
                pack,
                [{"tool": rejected_tool, "args": {}}, *minimal_calls],
                source["task_id"],
            )
            self.assertFalse(rejected["passed"])
            self.assertEqual(1, rejected["failed_tool_calls"])
            failed = {
                milestone["id"]
                for milestone in rejected["milestones"]
                if not milestone["passed"]
            }
            self.assertIn("execution.efficiency", failed)

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
            self.assertTrue(
                all(
                    not any(_matches(call, selector) for call in controls["missing_readback"]["calls"][handoff_index + 1:])
                    for selector in trace["postwrite_readback_calls"]
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
            self.assertEqual(12, sum(bool(asset["material"]) for asset in assets))
            suffixes = {asset_root.joinpath(Path(a["path"]).name).suffix[1:] for a in assets}
            self.assertTrue(
                {"csv", "eml", "json", "log", "md", "pdf", "sql", "txt", "xlsx", "yaml"}
                <= suffixes
            )
            self.assertTrue(all(validate_native_asset(path) for path in asset_root.iterdir()))

    def test_native_xlsx_assets_are_byte_reproducible_and_timestamp_pinned(self) -> None:
        row, source, contract, prompt, _calls, _trace = self.contracts[0]
        with tempfile.TemporaryDirectory(prefix="dob_xlsx_repro_") as temporary:
            temporary_root = Path(temporary)
            database = temporary_root / "environment.db"
            shutil.copy2(ROOT / "world" / "environment.db", database)
            seed_case_evidence(database, row, source, prompt, contract)
            first_root = temporary_root / "first" / row["bench_id"]
            second_root = temporary_root / "second" / row["bench_id"]
            write_asset_views(first_root, database, prompt, row, contract)
            write_asset_views(second_root, database, prompt, row, contract)
            first_xlsx = {
                path.name: path.read_bytes()
                for path in first_root.glob("*.xlsx")
            }
            second_xlsx = {
                path.name: path.read_bytes()
                for path in second_root.glob("*.xlsx")
            }
            self.assertEqual(first_xlsx, second_xlsx)
            self.assertEqual(len(first_xlsx), 2)
            for content in first_xlsx.values():
                with zipfile.ZipFile(io.BytesIO(content)) as archive:
                    self.assertTrue(archive.infolist())
                    self.assertTrue(
                        all(
                            member.date_time == FIXED_XLSX_ZIP_TIMESTAMP
                            for member in archive.infolist()
                        )
                    )


if __name__ == "__main__":
    unittest.main()
