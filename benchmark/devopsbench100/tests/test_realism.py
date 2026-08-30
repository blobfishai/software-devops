from __future__ import annotations

import difflib
import hashlib
from collections import defaultdict
from copy import deepcopy
import io
import json
from pathlib import Path
import re
import shutil
import tempfile
import unittest
import zipfile

from benchmark.devopsbench100 import builder, decision
from benchmark.devopsbench100.realism import (
    ASSET_COUNT,
    EVIDENCE_SURFACE_LABELS,
    FIXED_XLSX_ZIP_TIMESTAMP,
    MATERIAL_ASSET_COUNT,
    MATERIAL_CONTEXT_CALLS,
    MINIMUM_REFERENCE_CONTEXT_CALLS,
    MAX_PROMPT_WORDS,
    SEMANTIC_MILESTONE_WEIGHTS,
    augment_vcode,
    atomic_checks,
    case_contract,
    employee_title,
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
from benchmark.devopsbench100.recurate_human_jobs import (
    REPLACEMENTS,
    bench_id,
    recurate_catalog,
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
        self.assertLessEqual(max(words), MAX_PROMPT_WORDS)
        self.assertFalse(any(builder.PROMPT_LEAKAGE_PATTERN.search(p) for p in prompts))
        self.assertFalse(any(builder.has_repeated_leading_phrase(p) for p in prompts))

        token_sets = [set(re.findall(r"[a-z0-9]+", p.casefold())) for p in prompts]
        maximum = max(
            len(left & right) / len(left | right)
            for index, left in enumerate(token_sets)
            for right in token_sets[index + 1:]
        )
        self.assertLess(maximum, 0.72)
        for row, _source, _contract, prompt, calls, _trace in self.contracts:
            self.assertNotRegex(
                prompt,
                r"\b(?:DOB|DOC|ENG|OPS|SEC|SLO|QA|SPAN|SUP|MULTI|W6)-\d+\b|"
                r"\b(?:work item is|done when)\b",
                row["bench_id"],
            )
            named = sorted(
                {call["tool"] for call in calls if call["tool"].casefold() in prompt.casefold()}
            )
            self.assertEqual([], named, row["bench_id"])

    def test_human_job_recuration_is_idempotent(self) -> None:
        catalog = {
            "tasks": deepcopy(self.catalog),
            "selection_criteria": {},
        }
        world = self.source_tasks
        curated, applied = recurate_catalog(catalog, world)
        self.assertEqual([], applied)
        repeated, reapplied = recurate_catalog(deepcopy(curated), world)
        self.assertEqual([], reapplied)
        self.assertEqual(curated, repeated)

        old_task_id, new_task_id = next(iter(REPLACEMENTS.items()))
        pending = deepcopy(curated)
        row = next(item for item in pending["tasks"] if item["task_id"] == new_task_id)
        row["task_id"] = old_task_id
        row["bench_id"] = bench_id(int(row["index"]), old_task_id)
        migrated, newly_applied = recurate_catalog(pending, world)
        self.assertEqual(
            [{"from": old_task_id, "to": new_task_id}], newly_applied
        )
        stable, reapplied = recurate_catalog(deepcopy(migrated), world)
        self.assertEqual([], reapplied)
        self.assertEqual(migrated, stable)

    def test_raw_and_semantic_paths_are_unique_and_deep(self) -> None:
        sequences = [tuple(call["tool"] for call in item[4]) for item in self.contracts]
        graphs = [tuple(item[5]["semantic_action_graph"]) for item in self.contracts]
        profiles = [
            tuple(call["tool"] for call in item[5]["causal_evidence_profile"])
            for item in self.contracts
        ]
        reads = [item[5]["context_call_count"] for item in self.contracts]
        self.assertEqual(100, len(set(sequences)))
        self.assertEqual(100, len(set(graphs)))
        self.assertEqual(100, len(set(profiles)))
        self.assertGreaterEqual(min(map(len, profiles)), 3)
        self.assertGreaterEqual(min(reads), MINIMUM_REFERENCE_CONTEXT_CALLS)
        self.assertGreaterEqual(min(map(len, sequences)), 25)

        maximum = max(
            difflib.SequenceMatcher(a=left, b=right, autojunk=False).ratio()
            for index, left in enumerate(sequences)
            for right in sequences[index + 1:]
        )
        self.assertLess(maximum, 0.95)

        semantic_maximum = max(
            len(set(left) & set(right)) / len(set(left) | set(right))
            for index, left in enumerate(graphs)
            for right in graphs[index + 1:]
        )
        self.assertLess(semantic_maximum, 0.9)
        for row, _source, _contract, _prompt, _calls, trace in self.contracts:
            graph_text = " ".join(trace["semantic_action_graph"])
            self.assertNotRegex(graph_text, r"\b(?:dob|tsk|case)[-_]?\d+\b", row["bench_id"])
            self.assertGreaterEqual(len(trace["business_reasoning_primitives"]), 7)
            self.assertFalse(trace["identifier_or_group_permutation_used"])

    def test_repeated_source_harnesses_have_distinct_causal_evidence_profiles(self) -> None:
        families = defaultdict(list)
        for row, source, _contract, _prompt, _calls, trace in self.contracts:
            source_sequence = tuple(call["tool"] for call in source["expected_calls"])
            families[source_sequence].append((row, trace))
        for family in families.values():
            if len(family) < 2:
                continue
            profiles = [
                tuple(call["tool"] for call in trace["causal_evidence_profile"])
                for _row, trace in family
            ]
            self.assertTrue(all(profiles))
            self.assertEqual(len(profiles), len(set(profiles)))

    def test_material_evidence_is_a_causal_subset_of_the_reference_room(self) -> None:
        for row, _source, contract, _prompt, calls, trace in self.contracts:
            material, groups = material_context_calls(
                row, contract, _source, self.tools
            )
            self.assertEqual(MATERIAL_CONTEXT_CALLS, len(material), row["bench_id"])
            self.assertEqual(material, trace["required_context_calls"])
            self.assertEqual(groups, trace["material_context_groups"])
            self.assertGreaterEqual(
                trace["reference_context_call_count"],
                MINIMUM_REFERENCE_CONTEXT_CALLS,
            )
            live_selectors = [
                json.dumps(call, sort_keys=True)
                for call in groups["live_state"]
            ]
            self.assertGreaterEqual(len(live_selectors), 3)
            self.assertEqual(len(live_selectors), len(set(live_selectors)))
            self.assertEqual(5, len(groups["capacity_plan"]), row["bench_id"])
            material_selectors = [json.dumps(call, sort_keys=True) for call in material]
            self.assertEqual(
                MATERIAL_CONTEXT_CALLS,
                len(set(material_selectors)),
                row["bench_id"],
            )
            prefix = calls[: trace["reference_context_call_count"]]
            self.assertEqual(prefix, trace["reference_context_calls"])
            self.assertTrue(
                all(any(_matches(call, selector) for call in prefix) for selector in material),
                row["bench_id"],
            )
            self.assertGreaterEqual(len(trace["postwrite_readback_calls"]), 1)
            public_calls = [
                *trace["required_context_calls"],
                *trace["postwrite_readback_calls"],
            ]
            self.assertTrue(
                all(call["tool"] in EVIDENCE_SURFACE_LABELS for call in public_calls),
                row["bench_id"],
            )

    def test_semantic_rubrics_are_task_specific_and_total_one_hundred(self) -> None:
        descriptions = set()
        for row, source, contract, prompt, _calls, trace in self.contracts:
            task = {
                **source,
                "instruction": prompt,
                "vcode": augment_vcode(source["vcode"], row, contract, trace),
            }
            milestones = semantic_milestones(task, row, contract, trace)
            self.assertEqual(
                len(SEMANTIC_MILESTONE_WEIGHTS), len(milestones), row["bench_id"]
            )
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
            milestone_descriptions = tuple(item["description"] for item in milestones)
            joined = " ".join(milestone_descriptions)
            state_description = next(
                item["description"] for item in milestones if item["id"] == "state.primary"
            )
            self.assertNotRegex(state_description, r"plus \d+ related invariants")
            self.assertNotIn("task-specific source-of-truth transition", joined)
            self.assertNotIn("every authored final-state invariant", joined)
            self.assertNotIn("tests, CI, metrics, alarms, or provider records", joined)
            self.assertNotRegex(
                joined,
                r"\b(?:question_id|proposal_id|fault_detected)\b|"
                r"\bthe (?:rca|rcn|impl|ws|port|hz|judge|attr|cve)\b",
                row["bench_id"],
            )
            self.assertNotIn(contract["case_id"], joined)
            self.assertNotIn(source["task_id"], joined)
            for tool in trace["source_mutation_tools"]:
                self.assertNotIn(tool, joined, row["bench_id"])
            public_outcome = employee_title({"instruction": prompt})
            self.assertIn(public_outcome, joined)
            descriptions.add(milestone_descriptions)
        self.assertEqual(100, len(descriptions))

    def test_public_rubric_states_the_complete_business_outcome(self) -> None:
        by_id = {item[0]["bench_id"]: item for item in self.contracts}
        expected_phrases = {
            "dob100-031-impl-backoff": (
                "start at base_ms on attempt 1",
                "cap at max_ms",
                "reject attempts below 1",
            ),
            "dob100-032-impl-cachekey": (
                "stable across dictionary insertion order",
                "explicit null",
                "missing parameter",
            ),
            "dob100-033-impl-chunk": (
                "order-preserving groups",
                "one-pass iterables",
                "reject sizes below 1",
            ),
            "dob100-034-impl-ratelimit": (
                "refill continuously",
                "fractional elapsed time",
                "backward clock step",
            ),
            "dob100-064-hand-cluster-runbook": (
                "which node is unhealthy",
                "how it is unhealthy",
                "which service it affects",
                "other unhealthy node",
            ),
            "dob100-065-hand-gateway-runbook": (
                "which release introduced it",
                "what the p99 reached",
                "objective it breached",
                "rolling forward does not recover it",
            ),
            "dob100-100-ws-ledger-missing-account": (
                "zero balance for an account with no postings",
                "integer per-account accumulation",
                "double-entry balance semantics",
            ),
            "dob100-011-detect-storefront-healthy": (
                "is healthy",
                "no active objective breach",
                "no supported fault owner",
            ),
        }
        for bench_id, phrases in expected_phrases.items():
            row, source, contract, prompt, _calls, trace = by_id[bench_id]
            task = {
                **source,
                "instruction": prompt,
                "vcode": augment_vcode(source["vcode"], row, contract, trace),
            }
            criteria = semantic_milestones(task, row, contract, trace)
            state = next(
                item["description"] for item in criteria if item["id"] == "state.primary"
            )
            for phrase in phrases:
                self.assertIn(phrase, state, bench_id)

    def test_reasoning_contract_exposes_the_full_evidence_to_readback_chain(self) -> None:
        for row, source, contract, prompt, _calls, trace in self.contracts:
            task = {
                **source,
                "instruction": prompt,
                "vcode": augment_vcode(source["vcode"], row, contract, trace),
            }
            criteria = semantic_milestones(task, row, contract, trace)
            contract_story = builder.employee_reasoning_contract(criteria, prompt)
            self.assertEqual(
                {
                    "employee_outcome",
                    "investigate",
                    "decide",
                    "change_or_record",
                    "verify",
                    "deliver",
                },
                set(contract_story),
            )
            self.assertIn("first resolve the same work across", contract_story["investigate"])
            self.assertIn("effective rule over the retired shortcut", contract_story["investigate"])
            self.assertIn(
                f"All {MATERIAL_CONTEXT_CALLS} exact causal facts",
                contract_story["investigate"],
            )
            self.assertIn("healthy replicas per zone", contract_story["investigate"])
            self.assertIn("Compare three concrete", contract_story["decide"])
            self.assertIn("Coordinate the linked records", contract_story["change_or_record"])
            self.assertIn("contained to its supported records", contract_story["change_or_record"])
            self.assertIn("reopen", contract_story["verify"])
            self.assertIn("Close", contract_story["deliver"])

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
                *trace["source_execution_calls"],
                trace["decision_record_call"],
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

    def test_twelve_negative_controls_apply_to_every_task(self) -> None:
        for row, source, contract, _prompt, calls, trace in self.contracts:
            reference = {
                "expected_calls": calls,
                "source_expected_calls": source["expected_calls"],
                "trace_contract": trace,
                "case_contract": contract,
            }
            controls = negative_plans(reference)
            self.assertEqual(CONTROL_NAMES, tuple(controls), row["bench_id"])
            self.assertEqual(12, len(controls), row["bench_id"])
            self.assertFalse(controls["noop"]["calls"])
            self.assertTrue(controls["unauthorized_write"]["tamper_frozen_state"])
            wrong_answer = json.loads(
                next(
                    call
                    for call in controls["wrong_answer"]["calls"]
                    if call["tool"] == "submit_answer"
                    and call["args"].get("question_id")
                    == contract["capacity_question"]
                )["args"]["answer"]
            )
            self.assertNotEqual(
                wrong_answer["usable_replicas"],
                contract["plan"]["answer"]["usable_replicas"],
            )
            unapproved = json.loads(
                next(
                    call
                    for call in controls["unapproved_option"]["calls"]
                    if call["tool"] == "submit_answer"
                    and call["args"].get("question_id")
                    == contract["capacity_question"]
                )["args"]["answer"]
            )
            self.assertEqual(
                decision.OPTION_RELEASE, unapproved["recommended_option"]
            )

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
        row, source, contract, prompt, _calls, trace = self.contracts[0]
        with tempfile.TemporaryDirectory(prefix="dob_assets_") as temporary:
            temporary_root = Path(temporary)
            database = temporary_root / "environment.db"
            shutil.copy2(ROOT / "world" / "environment.db", database)
            shutil.copy2(
                ROOT / "world" / "tools_combined.py",
                temporary_root / "tools_combined.py",
            )
            seed_case_evidence(database, row, source, prompt, contract)
            asset_root = temporary_root / "task_files" / row["bench_id"]
            assets = write_asset_views(
                asset_root, database, prompt, row, contract, trace
            )
            self.assertEqual(ASSET_COUNT, len(assets))
            self.assertEqual(
                MATERIAL_ASSET_COUNT,
                sum(bool(asset["material"]) for asset in assets),
            )
            self.assertTrue(
                all(asset.get("material_reason") for asset in assets if asset["material"])
            )
            suffixes = {Path(asset["path"]).suffix[1:] for asset in assets}
            self.assertTrue(
                {"csv", "eml", "json", "log", "md", "pdf", "sql", "txt", "xlsx", "yaml"}
                <= suffixes
            )
            self.assertTrue(
                all(
                    validate_native_asset(path)
                    for path in asset_root.rglob("*")
                    if path.is_file()
                )
            )
            manifest = json.loads(
                (asset_root / "51-agent-visible-asset-manifest.json").read_text()
            )
            self.assertFalse(manifest["gold_included"])
            self.assertFalse(manifest["oracle_sequence_included"])
            self.assertFalse(manifest["ordering_semantics"])
            self.assertEqual(ASSET_COUNT - 1, manifest["listed_assets"])
            self.assertEqual(
                ASSET_COUNT, manifest["total_assets_including_this_manifest"]
            )
            self.assertEqual(ASSET_COUNT - 1, len(manifest["assets"]))
            for asset in manifest["assets"]:
                content = (asset_root / asset["path"]).read_bytes()
                self.assertEqual(len(content), asset["bytes"])
                self.assertEqual(hashlib.sha256(content).hexdigest(), asset["sha256"])
                self.assertNotIn("tool", asset)
            material = [asset for asset in manifest["assets"] if asset["material"]]
            self.assertEqual(MATERIAL_ASSET_COUNT, len(material))
            self.assertTrue(all(asset.get("material_reason") for asset in material))
            self.assertTrue(all("query_scope" in asset for asset in material))

    def test_capacity_plan_is_derived_from_seeded_sources_and_fully_graded(self) -> None:
        statuses: set[str] = set()
        recommendations: set[str] = set()
        for row, _source, contract, _prompt, calls, trace in self.contracts:
            plan = contract["plan"]
            answer = plan["answer"]
            self.assertEqual(
                plan["per_zone"] * plan["zones"], answer["required_replicas"]
            )
            self.assertEqual(
                plan["observed"] - plan["reserved"], answer["usable_replicas"]
            )
            self.assertEqual(
                answer["required_replicas"] - answer["usable_replicas"],
                answer["replica_gap"],
            )
            statuses.add(answer["decision_timing_status"])
            recommendations.add(answer["recommended_option"])

            options = decision.decision_options(row, contract)
            self.assertEqual(3, len(options))
            self.assertEqual(1, sum(bool(option["recommended"]) for option in options))
            self.assertEqual(
                1,
                sum(
                    option["approval"] == "ADDITIONAL_APPROVAL_REQUIRED"
                    for option in options
                ),
            )
            self.assertTrue(
                all(
                    option["completion"]
                    and isinstance(option["incremental_cost"], int)
                    and option["control_status"]
                    and option["consequence"]
                    for option in options
                )
            )

            model = decision.decision_model(row, contract, "OPS-CONTROL-2026.03")
            self.assertEqual(
                set(answer), {item["field"] for item in model["calculations"]}
            )
            self.assertEqual(answer["recommended_option"], model["selected_option"])
            self.assertEqual(
                answer,
                json.loads(decision.decision_record_call(contract)["args"]["answer"]),
            )
            for token in trace["handoff_contract"]["graded_text_contains"]:
                self.assertIn(token, trace["handoff_call"]["args"]["body"])
            decision_index = (
                trace["reference_context_call_count"]
                + len(trace["source_execution_calls"])
            )
            self.assertEqual(trace["decision_record_call"], calls[decision_index])

        self.assertEqual({"ON_TIME", "LATE"}, statuses)
        self.assertGreaterEqual(len(recommendations), 2)

    def test_native_xlsx_assets_are_byte_reproducible_and_timestamp_pinned(self) -> None:
        row, source, contract, prompt, _calls, trace = self.contracts[0]
        with tempfile.TemporaryDirectory(prefix="dob_xlsx_repro_") as temporary:
            temporary_root = Path(temporary)
            database = temporary_root / "environment.db"
            shutil.copy2(ROOT / "world" / "environment.db", database)
            shutil.copy2(
                ROOT / "world" / "tools_combined.py",
                temporary_root / "tools_combined.py",
            )
            seed_case_evidence(database, row, source, prompt, contract)
            first_root = temporary_root / "first" / row["bench_id"]
            second_root = temporary_root / "second" / row["bench_id"]
            write_asset_views(first_root, database, prompt, row, contract, trace)
            write_asset_views(second_root, database, prompt, row, contract, trace)
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
