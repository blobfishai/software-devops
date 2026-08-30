#!/usr/bin/env python3
"""Replace parameter variants with distinct employee jobs in the frozen catalog."""

from __future__ import annotations

import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CATALOG = HERE / "catalog.json"
WORLD_TASKS = ROOT / "world" / "tasks.json"

REPLACEMENTS = {
    "tsk_detect_payments": "tsk_rcn_checkout_error_rate",
    "tsk_checkout_v1_to_v2": "tsk_rca_payments_retry",
    "tsk_inventory_v1_to_v2": "tsk_rca_catalog_n_plus_one",
    "tsk_media_v1_to_v2": "tsk_rca_notifications_timeout",
    "tsk_notify_v1_to_v2": "tsk_rca_inventory_pool",
    "tsk_orders_v1_to_v2": "tsk_rca_inventory_migrator_security_context",
    "tsk_search_v1_to_v2": "tsk_rca_inventory_missing_role",
    "tsk_w5_attr_media_analytics_catalog": "tsk_rca_catalog_gc_thrash",
    "tsk_w5_attr_media_analytics_payments": "tsk_rca_storefront_traffic_flood",
    "tsk_w5_attr_media_api_analytics": "tsk_rca_analytics_untolerated_taint",
    "tsk_w5_attr_media_api_catalog": "tsk_rca_media_recreate_strategy",
    "tsk_w5_attr_media_api_checkout": "tsk_rca_inventory_unbound_storage",
    "tsk_w5_attr_media_api_payments": "tsk_rcn_distinct_checkout_bugs",
    "tsk_flaky_inventory_race": "tsk_w6_copy_13",
    "tsk_search_cache": "tsk_port_collect_open_issues",
    "tsk_search_shards": "tsk_port_report_customer_reports",
    "tsk_retire_metrics_endpoint": "tsk_port_count_gateway_surface",
    "tsk_payments_notify_timeout": "tsk_port_count_open_priority",
}


def bench_id(index: int, task_id: str) -> str:
    slug = task_id.removeprefix("tsk_").replace("_", "-")
    return f"dob100-{index:03d}-{slug}"


def recurate_catalog(
    catalog: dict, world: dict[str, dict]
) -> tuple[dict, list[dict[str, str]]]:
    """Apply the diversity replacements once and validate repeat runs."""

    missing = sorted(set(REPLACEMENTS.values()) - set(world))
    if missing:
        raise ValueError(f"replacement tasks are absent from the world: {missing}")

    applied: list[dict[str, str]] = []
    for old_task_id, new_task_id in REPLACEMENTS.items():
        old_rows = [
            row for row in catalog["tasks"] if str(row["task_id"]) == old_task_id
        ]
        new_rows = [
            row for row in catalog["tasks"] if str(row["task_id"]) == new_task_id
        ]
        if not old_rows:
            if len(new_rows) != 1:
                raise ValueError(
                    f"catalog has neither one replacement input nor one output for {old_task_id}"
                )
            continue
        if len(old_rows) != 1 or new_rows:
            raise ValueError(
                f"catalog replacement collision for {old_task_id} -> {new_task_id}"
            )
        row = old_rows[0]
        task = world[new_task_id]
        call_count = len(task["expected_calls"])
        row.update(
            {
                "bench_id": bench_id(int(row["index"]), new_task_id),
                "category": task["category"],
                "difficulty": task["difficulty"],
                "expected_calls": call_count,
                "rationale": [
                    task["category"],
                    task["difficulty"],
                    f"{call_count}-call-oracle",
                    "curated",
                    "human-job-diversity-replacement",
                ],
                "task_id": new_task_id,
            }
        )
        applied.append({"from": old_task_id, "to": new_task_id})

    task_ids = [str(row["task_id"]) for row in catalog["tasks"]]
    bench_ids = [str(row["bench_id"]) for row in catalog["tasks"]]
    if len(task_ids) != 100 or len(set(task_ids)) != 100 or len(set(bench_ids)) != 100:
        raise ValueError("recurated catalog must contain 100 unique jobs and benchmark IDs")

    # Source jobs can deepen without changing identity.  Keep the frozen
    # selection's executable measurements synchronized with the rebuilt world
    # instead of preserving a stale call count from an older release.
    for row in catalog["tasks"]:
        task = world[str(row["task_id"])]
        call_count = len(task["expected_calls"])
        row["category"] = task["category"]
        row["difficulty"] = task["difficulty"]
        row["expected_calls"] = call_count
        rationale = [
            item
            for item in row.get("rationale", [])
            if not str(item).endswith("-call-oracle")
        ]
        rationale.insert(2, f"{call_count}-call-oracle")
        row["rationale"] = rationale

    selection = catalog["selection_criteria"]
    selection["human_job_diversity"] = (
        "Task IDs, service names, endpoints, and alarm permutations do not count as "
        "distinct employee jobs. The release recomputes identifier-neutral semantic "
        "similarity and records the worst pair."
    )
    selection["parameter_variant_replacements"] = len(REPLACEMENTS)
    catalog["recuration"] = {
        "reason": "replace parameter variants with distinct executable employee jobs",
        "replacements": [
            {"from": old_task_id, "to": new_task_id}
            for old_task_id, new_task_id in REPLACEMENTS.items()
        ],
    }
    return catalog, applied


def main() -> int:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    world = {
        task["task_id"]: task
        for task in json.loads(WORLD_TASKS.read_text(encoding="utf-8"))
    }
    catalog, applied = recurate_catalog(catalog, world)
    CATALOG.write_text(
        json.dumps(catalog, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "applied": len(applied),
                "already_curated": len(REPLACEMENTS) - len(applied),
                "tasks": len(catalog["tasks"]),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
