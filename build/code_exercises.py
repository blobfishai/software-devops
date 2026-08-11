"""Self-contained modules the world can actually execute.

Every other check in this world is a rule over declared state: a config key holds
a value, a migration precedes its deploy, an endpoint is drained before it is
retired. Those catch a great deal and they cannot catch a logic error, because
nothing runs. The coverage matrix has said "CI is a rule engine, not a compiler"
since the first draft, and this is the part that stops being true.

Each exercise is a real function with a real specification, a visible test the
agent can run, and a hidden test it cannot see. The world does not know whether
an implementation is correct until it executes it — which is the point, and is
different in kind from every other verifier here.

Design rules, learned from the rest of this world:

  * stdlib only, no imports beyond the standard library, so execution needs no
    environment and no network.
  * the trap is always a case the specification states and a plausible
    implementation gets wrong - an off-by-one, an unclamped cap, an ordering
    assumption. Never a case the spec leaves out; a hidden test for unstated
    behaviour is a trick, not a test.
  * the visible test passes for several wrong implementations. If the visible
    test were sufficient, running it would be a formality rather than evidence.
"""

EXERCISES = [
    {
        "id": "backoff",
        "service": "payments",
        "path": "src/payments/backoff.py",
        "func": "next_delay_ms",
        "spec": (
            "Implement next_delay_ms(attempt, base_ms, max_ms).\n\n"
            "Retries are numbered from 1: the delay before the FIRST retry is attempt=1.\n"
            "The delay doubles with each attempt - base_ms for attempt 1, twice that for\n"
            "attempt 2, four times for attempt 3 - and is capped at max_ms. The cap is a\n"
            "ceiling on the returned value, not on the exponent.\n\n"
            "attempt < 1 is not a retry and must raise ValueError."
        ),
        "starter": (
            '"""Backoff schedule for the payments retry path."""\n\n\n'
            "def next_delay_ms(attempt, base_ms, max_ms):\n"
            '    """Delay before retry number `attempt`, capped at max_ms."""\n'
            "    raise NotImplementedError\n"
        ),
        "reference": (
            '"""Backoff schedule for the payments retry path."""\n\n\n'
            "def next_delay_ms(attempt, base_ms, max_ms):\n"
            '    """Delay before retry number `attempt`, capped at max_ms."""\n'
            "    if attempt < 1:\n"
            "        raise ValueError('attempt must be >= 1')\n"
            "    return min(base_ms * (2 ** (attempt - 1)), max_ms)\n"
        ),
        # Deliberately silent on attempt=1 and on the cap: an implementation that
        # is off by one on `attempt`, or that never clamps, passes both of these.
        # A visible test that settles the question makes running it a formality.
        "visible_tests": [
            ("the delay doubles", "assert next_delay_ms(3, 100, 10000) == 2 * next_delay_ms(2, 100, 10000)"),
            ("delays are positive", "assert next_delay_ms(2, 100, 10000) > 0"),
        ],
        "hidden_tests": [
            ("attempt 1 is base_ms, not double",
             "assert next_delay_ms(1, 100, 10000) == 100"),
            ("the cap is a ceiling on the value",
             "assert next_delay_ms(9, 100, 5000) == 5000"),
            ("the cap applies at the boundary",
             "assert next_delay_ms(6, 100, 3200) == 3200"),
            ("attempt below 1 is not a retry",
             "try:\n    next_delay_ms(0, 100, 10000)\nexcept ValueError:\n    pass\n"
             "else:\n    raise AssertionError('attempt 0 must raise ValueError')"),
        ],
    },
    {
        "id": "chunk",
        "service": "payments",
        "path": "src/payments/chunking.py",
        "func": "chunk",
        "spec": (
            "Implement chunk(items, size) returning a list of lists.\n\n"
            "Settlement batches a day's captures so one long-tailed merchant cannot stall\n"
            "the run. Split `items` into consecutive groups of at most `size`, preserving\n"
            "order. The final group may be shorter. An empty input produces no groups at\n"
            "all - not one empty group. A size below 1 is meaningless and must raise\n"
            "ValueError."
        ),
        "starter": (
            '"""Batch chunking for nightly settlement."""\n\n\n'
            "def chunk(items, size):\n"
            '    """Split items into consecutive groups of at most `size`."""\n'
            "    raise NotImplementedError\n"
        ),
        "reference": (
            '"""Batch chunking for nightly settlement."""\n\n\n'
            "def chunk(items, size):\n"
            '    """Split items into consecutive groups of at most `size`."""\n'
            "    if size < 1:\n"
            "        raise ValueError('size must be >= 1')\n"
            "    items = list(items)\n"
            "    return [items[i:i + size] for i in range(0, len(items), size)]\n"
        ),
        "visible_tests": [
            ("splits with a remainder",
             "assert chunk([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]"),
        ],
        "hidden_tests": [
            ("empty input produces no groups", "assert chunk([], 3) == []"),
            ("an exact multiple has no trailing empty group",
             "assert chunk([1, 2, 3, 4], 2) == [[1, 2], [3, 4]]"),
            ("order is preserved",
             "assert chunk(['a', 'b', 'c'], 1) == [['a'], ['b'], ['c']]"),
            # size 0 alone is a weak test: range(0, n, 0) raises ValueError by
            # itself, so an implementation with no guard passes for the wrong
            # reason. A negative size is accepted silently by range and is only
            # rejected by a deliberate check.
            ("a size below 1 is meaningless",
             "for bad in (0, -1):\n"
             "    try:\n        chunk([1, 2], bad)\n    except ValueError:\n        pass\n"
             "    else:\n        raise AssertionError('size %r must raise ValueError' % bad)"),
            ("an iterator is accepted, not just a list",
             "assert chunk(iter([1, 2, 3]), 2) == [[1, 2], [3]]"),
        ],
    },
    {
        "id": "cachekey",
        "service": "search",
        "path": "src/search/cache_key.py",
        "func": "cache_key",
        "spec": (
            "Implement cache_key(params) returning a string.\n\n"
            "The search result cache is keyed on the query parameters. Two calls with the\n"
            "same parameters must produce the same key regardless of the order the keys\n"
            "were inserted into the dict, because callers build them in different orders\n"
            "and a mismatch silently halves the hit rate.\n\n"
            "Different parameters must produce different keys. A parameter explicitly set\n"
            "to None is not the same request as one that was never supplied. Values may be\n"
            "strings, numbers, booleans or None."
        ),
        "starter": (
            '"""Cache key derivation for the search result cache."""\n\n\n'
            "def cache_key(params):\n"
            '    """A stable key for a parameter dict."""\n'
            "    raise NotImplementedError\n"
        ),
        "reference": (
            '"""Cache key derivation for the search result cache."""\n'
            "import json\n\n\n"
            "def cache_key(params):\n"
            '    """A stable key for a parameter dict."""\n'
            "    return json.dumps(params, sort_keys=True, separators=(',', ':'),\n"
            "                      default=str)\n"
        ),
        "visible_tests": [
            ("identical dicts agree",
             "assert cache_key({'q': 'shoes', 'page': 1}) == cache_key({'q': 'shoes', 'page': 1})"),
        ],
        "hidden_tests": [
            ("insertion order does not matter",
             "a = {}\na['q'] = 'shoes'\na['page'] = 1\n"
             "b = {}\nb['page'] = 1\nb['q'] = 'shoes'\n"
             "assert cache_key(a) == cache_key(b)"),
            ("different values differ",
             "assert cache_key({'q': 'shoes'}) != cache_key({'q': 'boots'})"),
            ("an explicit None is not an absent key",
             "assert cache_key({'q': 'shoes', 'filter': None}) != cache_key({'q': 'shoes'})"),
            # 'a'+'xb' + 'b'+'' and 'a'+'x' + 'bb'+'' both concatenate to "axbb".
            # The earlier version of this test used a pair that does NOT collide,
            # so it passed for a naive implementation and proved nothing.
            ("keys and values cannot run together",
             "assert cache_key({'a': 'xb', 'b': ''}) != cache_key({'a': 'x', 'bb': ''})"),
        ],
    },
]


def as_rows():
    """(exercise_id, service, path, func, spec, starter, visible, hidden)."""
    import json as _json
    rows = []
    for i, ex in enumerate(EXERCISES, start=9401):
        rows.append((i, ex["service"], ex["path"], ex["func"], ex["spec"], ex["starter"],
                     _json.dumps(ex["visible_tests"]), _json.dumps(ex["hidden_tests"])))
    return rows
