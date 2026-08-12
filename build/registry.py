"""The one place every task in this world is registered.

The repo is a single world, but its tasks have three authors: written by hand in
task_specs.py, generated from the built database by waves.py, and expanded from
templates by tasks_def.py. They converged on a bare list that anything could
append to, which meant nothing owned the id namespace and nothing compared a new
task against the ones already there. waves.py deduplicated within itself, and
that was the entire defence.

This module owns both. Every task registers here, so there is one place to read
what the world contains; and the build asks here whether a task grades something
no other task already grades, so a duplicate fails the build instead of shipping
and inflating the count.

What counts as a duplicate is the VERIFIER, not the prose. Two tasks can read
completely differently - one framed as a CVE triage, one as a latency complaint -
and assert the identical thing about the identical scope. The instruction is the
story; the verifier is the task.
"""

SPECS = []
_ORIGIN = {}


class DuplicateTask(Exception):
    """A task id was registered twice, or a task grades what another already does."""


def register(spec, origin):
    """Add one task spec. The id must be new."""
    tid = spec.get("id")
    if not tid:
        raise DuplicateTask("%s registered a spec with no id" % origin)
    if tid in _ORIGIN:
        raise DuplicateTask(
            "task id %r registered twice: first by %s, again by %s. Ids are the "
            "world's namespace and two tasks cannot share one."
            % (tid, _ORIGIN[tid], origin))
    _ORIGIN[tid] = origin
    SPECS.append(spec)
    return spec


def register_all(specs, origin):
    for s in specs:
        register(s, origin)
    return specs


def all_specs():
    return list(SPECS)


def origins():
    """task id -> which author registered it."""
    return dict(_ORIGIN)


def correctness_assertions(task):
    """What a task grades, ignoring how it is worded."""
    return tuple(sorted(" ".join(line.split())
                        for line in task.get("vcode", "").splitlines()
                        if '_c("correctness"' in line))


# Tasks that already grade the same thing as another task, grandfathered BY NAME
# so that any new duplicate fails the build. Named rather than counted, because a
# count lets one duplicate be swapped for another and still pass.
#
# Almost all of these are aiops_detection, and the cause is structural. That
# verifier asserts only that a fault was reported in a scope, so a CVE triage, a
# latency complaint and an error-rate alarm on the same service are identical to
# it. Fixing them means asserting the fault type, which changes what the category
# measures - a design decision rather than a cleanup, so they are recorded here
# instead of being quietly tolerated.
KNOWN_DUPLICATE_GROUPS = (
    frozenset({
        "tsk_detect_checkout_errors",
        "tsk_w1_cve_cve_2026_40881",
        "tsk_w1_detect_checkout_errors",
        "tsk_w1_detect_checkout_latency",
        "tsk_w1_triage_test_checkout_idempotency",
    }),
    frozenset({
        "tsk_detect_payments",
        "tsk_w1_cve_cve_2026_31337",
        "tsk_w1_cve_cve_2026_51002",
        "tsk_w1_detect_payments_errors",
    }),
    frozenset({
        "tsk_detect_inventory",
        "tsk_w1_detect_inventory_errors",
        "tsk_w1_triage_test_reservation_race",
    }),
    frozenset({
        "tsk_detect_storefront_healthy",
        "tsk_w1_detect_storefront_web_latency",
        "tsk_w1_triage_test_cart_selector",
    }),
    frozenset({
        "tsk_localize_analytics_crashloop",
        "tsk_localize_analytics_errors",
    }),
    frozenset({
        "tsk_attr_three_at_once",
        "tsk_w5_attr_media_api_checkout",
    }),
    frozenset({
        "tsk_w1_detect_analytics_worker_errors",
        "tsk_w1_triage_test_rollup_window",
    }),
    frozenset({
        "tsk_w1_detect_api_gateway_latency",
        "tsk_w1_triage_test_upstream_timeout",
    }),
    frozenset({
        "tsk_w1_detect_catalog_latency",
        "tsk_w1_triage_test_price_rounding",
    }),
    frozenset({
        "tsk_w1_detect_payments_latency",
        "tsk_w1_triage_test_capture_retries",
    }),
    frozenset({
        "tsk_w1_detect_search_latency",
        "tsk_w1_triage_test_index_refresh",
    }),
)

_GRANDFATHERED = frozenset().union(*KNOWN_DUPLICATE_GROUPS)


def assert_no_new_duplicates(tasks):
    """Raise if a task grades exactly what another task already grades.

    Called by the build with the fully generated tasks, because a spec cannot be
    compared before its verifier exists.
    """
    by = {}
    for t in tasks:
        by.setdefault(correctness_assertions(t), []).append(t["task_id"])
    offenders = []
    for ids in by.values():
        if len(ids) < 2:
            continue
        group = frozenset(ids)
        if any(group <= known for known in KNOWN_DUPLICATE_GROUPS):
            continue
        offenders.append(sorted(set(ids) - _GRANDFATHERED) or sorted(ids))
    if offenders:
        raise DuplicateTask(
            "%d task group(s) grade what another task already grades: %s. A task "
            "whose verifier already exists adds a row to the count and nothing to "
            "the measurement. Give it a distinct assertion, or drop it."
            % (len(offenders), offenders))
