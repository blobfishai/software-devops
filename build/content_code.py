"""Source-of-truth code content for the NovaCart simulated monorepo.

Pure data. No imports, no logic, no side effects -- ``build_world.py`` reads
``REPO_FILES`` and ``COMMITS`` and materializes them into the world database.

REPO_FILES entries:
    service  -- one of the ten NovaCart services
    path     -- path relative to that service's directory in the monorepo
    language -- python | go | java | typescript | sql
    content  -- the literal file body
    owner    -- primary maintainer (CODEOWNERS)

COMMITS entries are ordered oldest -> newest; ``day`` counts days since the
repo was created, and day 420 is "today".
"""

REPO_FILES = [
    # ------------------------------------------------------------------ payments
    {
        "service": "payments",
        "path": "src/payments/settings.py",
        "language": "python",
        "owner": "Diego Ramos",
        "content": r'''"""Typed configuration loader for the payments service.

Resolution order, first hit wins: process environment
(``NOVACART_PAYMENTS_<KEY>``), the document at ``/etc/novacart/payments.json``,
then ``_DEFAULTS``. Read once at start and cached, so changing a value needs a
deploy.
"""
from __future__ import annotations

import json
import logging
import os
import threading

log = logging.getLogger(__name__)

CONFIG_PATH = os.environ.get("NOVACART_CONFIG_PATH", "/etc/novacart/payments.json")
ENV_PREFIX = "NOVACART_PAYMENTS_"

_DEFAULTS = {
    "notifications_base_url": "http://notifications.internal:8080",
    "notifications_timeout_ms": 30000,
    # Retry policy standard says 3 for every cross-service call.
    "notifications_retry_max_attempts": 0,
    "db_pool_size": 20,
    "settlement_batch_size": 250,
    "capture_timeout_ms": 8000,
}

_lock = threading.Lock()
_cache = None


def _read_document(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        log.warning("config document %s missing; using compiled defaults", path)
        return {}
    except json.JSONDecodeError:
        log.exception("config document %s is not valid JSON; refusing to guess", path)
        raise


def load():
    """Return the frozen config mapping, reading it on first call."""
    global _cache
    with _lock:
        if _cache is not None:
            return _cache
        merged = dict(_DEFAULTS)
        merged.update(_read_document(CONFIG_PATH))
        for key, default in _DEFAULTS.items():
            raw = os.environ.get(ENV_PREFIX + key.upper())
            if raw is not None:
                merged[key] = int(raw) if isinstance(default, int) else raw
        log.info("startup config: %s",
                 " ".join("%s=%s" % (k, v) for k, v in sorted(merged.items())))
        _cache = merged
        return merged


def get(key, default=None):
    """Return one config value. Unknown keys warn and fall back to ``default``."""
    config = load()
    if key not in config:
        log.warning("config key %r is not declared in _DEFAULTS", key)
        return default
    return config[key]
''',
    },
    {
        "service": "payments",
        "path": "src/payments/notify_client.py",
        "language": "python",
        "owner": "Diego Ramos",
        "content": r'''"""Client for the notifications service.

payments calls notifications synchronously after a capture succeeds; a
permanent failure here fails the payment (see ``payments.capture``).
"""
from __future__ import annotations

import logging
import time
import uuid

import requests

from payments import settings

log = logging.getLogger(__name__)

NOTIFICATIONS_BASE_URL = settings.get("notifications_base_url")
NOTIFICATIONS_TIMEOUT_MS = settings.get("notifications_timeout_ms")

# NOTE(dramos): the tenacity retry wrapper around _post() was removed to hit the
# Q3 receipt-latency deadline -- backoff sleeps were showing up in payments p99.
# The knob stayed in config. It is 0 today, so _post() gets exactly one attempt
# and a single downstream timeout permanently fails the order.
NOTIFICATIONS_RETRY_MAX_ATTEMPTS = settings.get("notifications_retry_max_attempts")


class PaymentNotificationError(RuntimeError):
    """The receipt notification could not be delivered."""


def _post(path, payload, correlation_id):
    return requests.post(
        "%s%s" % (NOTIFICATIONS_BASE_URL, path),
        json=payload,
        timeout=NOTIFICATIONS_TIMEOUT_MS / 1000.0,
        headers={"X-Correlation-Id": correlation_id, "X-Source": "payments"},
    )


def send_receipt(order_id, customer_email, amount_cents, currency="USD"):
    """Deliver a receipt. Raises PaymentNotificationError if it cannot."""
    correlation_id = str(uuid.uuid4())
    payload = {"template": "payment_receipt", "order_id": order_id,
               "to": customer_email, "amount_cents": amount_cents,
               "currency": currency}

    attempt = 0
    while True:
        attempt += 1
        started = time.monotonic()
        try:
            response = _post("/v1/receipts", payload, correlation_id)
            response.raise_for_status()
            log.info("receipt delivered order=%s attempt=%d", order_id, attempt)
            return response.json()
        except requests.RequestException as exc:
            elapsed_ms = int((time.monotonic() - started) * 1000)
            if attempt > NOTIFICATIONS_RETRY_MAX_ATTEMPTS:
                log.error(
                    "ConnectionTimeout calling notifications after %dms - request "
                    "failed permanently (retry_max_attempts=%d, no retry attempted); "
                    "order %s marked failed", elapsed_ms,
                    NOTIFICATIONS_RETRY_MAX_ATTEMPTS, order_id)
                raise PaymentNotificationError("receipt undeliverable") from exc
            backoff = min(0.2 * (2 ** (attempt - 1)), 2.0)
            log.warning("notifications call failed (attempt %d of %d) after %dms; "
                        "retrying in %.1fs", attempt,
                        NOTIFICATIONS_RETRY_MAX_ATTEMPTS, elapsed_ms, backoff)
            time.sleep(backoff)
''',
    },
    {
        "service": "payments",
        "path": "src/payments/capture.py",
        "language": "python",
        "owner": "Diego Ramos",
        "content": r'''"""Payment capture.

Moves an authorized payment to "captured" with libpayproc, then emits the buyer
receipt. Idempotent on ``idempotency_key``: replaying a key returns the
original capture rather than charging the card twice.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import libpayproc

from payments import settings
from payments.notify_client import PaymentNotificationError, send_receipt
from payments.store import captures

log = logging.getLogger(__name__)

CAPTURE_TIMEOUT_MS = settings.get("capture_timeout_ms")


class CaptureDeclined(Exception):
    """The upstream processor refused the capture."""


@dataclass(frozen=True)
class CaptureResult:
    order_id: str
    processor_ref: str
    amount_cents: int
    currency: str
    status: str


def capture_payment(order_id, auth_token, amount_cents, currency, idempotency_key):
    replay = captures.find_by_idempotency_key(idempotency_key)
    if replay is not None:
        log.info("capture replay order=%s key=%s", order_id, idempotency_key)
        return replay

    client = libpayproc.Client(timeout_ms=CAPTURE_TIMEOUT_MS)
    try:
        upstream = client.capture(auth_token=auth_token, amount=amount_cents,
                                  currency=currency)
    except libpayproc.Declined as exc:
        log.warning("capture declined order=%s reason=%s", order_id, exc.reason)
        captures.record_failure(order_id, idempotency_key, reason=exc.reason)
        raise CaptureDeclined(exc.reason) from exc
    except libpayproc.TransportError:
        log.exception("processor transport error order=%s", order_id)
        raise

    result = CaptureResult(order_id, upstream.reference, amount_cents, currency,
                           "captured")
    captures.persist(result, idempotency_key)

    # The receipt is part of the payment contract: if we cannot tell the buyer
    # the money moved, we do not treat the payment as complete.
    try:
        send_receipt(order_id, upstream.customer_email, amount_cents, currency)
    except PaymentNotificationError:
        log.error("receipt delivery failed order=%s; marking payment failed", order_id)
        captures.mark_failed(order_id, reason="notification_undeliverable")
        raise

    log.info("captured order=%s ref=%s amount=%d %s", order_id, upstream.reference,
             amount_cents, currency)
    return result
''',
    },
    {
        "service": "payments",
        "path": "src/payments/settlement.py",
        "language": "python",
        "owner": "Lena Ortiz",
        "content": r'''"""Nightly settlement: group captured payments per merchant and push batches.

Runs from the cron at 02:15 UTC. Batches are chunked so one long-tailed
merchant cannot stall the run; each batch commits independently.
"""
from __future__ import annotations

import collections
import logging
from datetime import date, timedelta

import libpayproc

from payments import settings
from payments.store import captures, settlements

log = logging.getLogger(__name__)

BATCH_SIZE = settings.get("settlement_batch_size")


class SettlementError(RuntimeError):
    pass


def _chunk(items, size):
    for start in range(0, len(items), size):
        yield items[start:start + size]


def group_by_merchant(rows):
    grouped = collections.defaultdict(list)
    for row in rows:
        grouped[row.merchant_id].append(row)
    return grouped


def settle_day(target_day=None):
    target_day = target_day or (date.today() - timedelta(days=1))
    pending = captures.list_settlable(target_day)
    if not pending:
        log.info("nothing to settle for %s", target_day)
        return 0

    client = libpayproc.Client(timeout_ms=settings.get("capture_timeout_ms"))
    settled_total = 0

    for merchant_id, rows in sorted(group_by_merchant(pending).items()):
        for batch in _chunk(rows, BATCH_SIZE):
            amount = sum(row.amount_cents for row in batch)
            try:
                refs = [row.processor_ref for row in batch]
                receipt = client.settle_batch(merchant_id=merchant_id,
                                              references=refs, amount_cents=amount)
            except libpayproc.TransportError:
                log.exception(
                    "settlement batch failed merchant=%s size=%d; will retry tomorrow",
                    merchant_id, len(batch),
                )
                continue

            settlements.record(merchant_id, target_day, receipt.id, amount, len(batch))
            settled_total += len(batch)
            log.info(
                "settled merchant=%s batch=%d amount=%d receipt=%s",
                merchant_id, len(batch), amount, receipt.id,
            )

    log.info("settlement complete day=%s captures=%d", target_day, settled_total)
    return settled_total
''',
    },
    {
        "service": "payments",
        "path": "tests/test_capture_retries.py",
        "language": "python",
        "owner": "Diego Ramos",
        "content": r'''"""Unit coverage for capture behaviour around notification failures."""
from __future__ import annotations

from unittest import mock

import pytest

from payments import capture
from payments.notify_client import PaymentNotificationError


@pytest.fixture
def upstream_ok():
    with mock.patch("payments.capture.libpayproc.Client") as client_cls:
        client = client_cls.return_value
        client.capture.return_value = mock.Mock(
            reference="ref_9f31", customer_email="buyer@example.com"
        )
        yield client


def test_capture_persists_before_notifying(upstream_ok):
    with mock.patch("payments.capture.captures") as store, \
            mock.patch("payments.capture.send_receipt"):
        store.find_by_idempotency_key.return_value = None
        result = capture.capture_payment("ord_1", "auth_x", 4599, "USD", "idem-1")

    assert result.status == "captured"
    assert result.processor_ref == "ref_9f31"
    store.persist.assert_called_once()


def test_replay_returns_original_capture(upstream_ok):
    with mock.patch("payments.capture.captures") as store:
        store.find_by_idempotency_key.return_value = "original"
        assert capture.capture_payment("ord_1", "auth_x", 100, "USD", "idem-1") == "original"
    upstream_ok.capture.assert_not_called()


def test_undeliverable_receipt_marks_payment_failed(upstream_ok):
    with mock.patch("payments.capture.captures") as store, \
            mock.patch("payments.capture.send_receipt") as send:
        store.find_by_idempotency_key.return_value = None
        send.side_effect = PaymentNotificationError("boom")
        with pytest.raises(PaymentNotificationError):
            capture.capture_payment("ord_2", "auth_y", 1200, "USD", "idem-2")

    store.mark_failed.assert_called_once_with(
        "ord_2", reason="notification_undeliverable"
    )
''',
    },

    # ------------------------------------------------------------------ checkout
    {
        "service": "checkout",
        "path": "src/checkout/config.py",
        "language": "python",
        "owner": "Nina Kowalski",
        "content": r'''"""Static configuration for the checkout service.

Anything in here is baked at build time and needs a deploy to change. Runtime
tunables belong in the config document read by ``checkout.settings``.
"""
from __future__ import annotations

import logging
import os

log = logging.getLogger(__name__)

SERVICE_NAME = "checkout"
ENVIRONMENT = os.environ.get("NOVACART_ENV", "staging")

PAYMENT_TIMEOUT_MS = int(os.environ.get("CHECKOUT_PAYMENT_TIMEOUT_MS", "8000"))
CART_TTL_SECONDS = 60 * 60 * 24 * 3
MAX_LINE_ITEMS = 100
CURRENCY_DEFAULT = "USD"

PAYMENTS_BASE_URL = os.environ.get(
    "CHECKOUT_PAYMENTS_URL", "http://payments.internal:8080"
)
CATALOG_BASE_URL = os.environ.get(
    "CHECKOUT_CATALOG_URL", "http://catalog.internal:8080"
)

# Partner settlement API credentials.
# TODO(ENG-2178): move this to the secret manager (vault path
# novacart/checkout/partner) before partner GA. Committed inline so the staging
# box could boot on a Friday afternoon; it is the live key, not a test key.
PARTNER_API_KEY = "pk_live_9f2c4a71b8e34d05a6c7d1e8f0b3a25c"
PARTNER_API_BASE = "https://partners.novacart.io/settlement/v2"

RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})


def partner_headers():
    return {
        "Authorization": "Bearer " + PARTNER_API_KEY,
        "X-NovaCart-Service": SERVICE_NAME,
    }


def describe():
    """Log the effective config. Never log credential values."""
    log.info(
        "checkout config env=%s payment_timeout_ms=%d cart_ttl_s=%d max_items=%d "
        "partner_key=%s",
        ENVIRONMENT,
        PAYMENT_TIMEOUT_MS,
        CART_TTL_SECONDS,
        MAX_LINE_ITEMS,
        "set" if PARTNER_API_KEY else "unset",
    )
''',
    },
    {
        "service": "checkout",
        "path": "src/checkout/refunds.py",
        "language": "python",
        "owner": "Lena Ortiz",
        "content": r'''"""Refund issuance.

Two paths: ``instant_refunds`` (flag-gated pilot) settles inline while the
shopper is on the page; the legacy path records an intent and lets the async
worker settle it on the next batch run.
"""
from __future__ import annotations

import logging

from checkout import config, flags
from checkout.clients.payments import PaymentsClient
from checkout.store import refund_store

log = logging.getLogger(__name__)

payments = PaymentsClient(
    base_url=config.PAYMENTS_BASE_URL, timeout_ms=config.PAYMENT_TIMEOUT_MS
)


class RefundError(RuntimeError):
    pass


def _audit(order_id, record, actor, amount_cents):
    log.info(
        "refund audit order=%s ledger=%s actor=%s amount=%d",
        order_id, record.ledger_entry_id, actor, amount_cents,
    )


def issue_refund(order_id, amount_cents, actor):
    record = refund_store.find_by_order(order_id)

    if flags.enabled("instant_refunds"):
        # Fast path. The refund row is written by the checkout submit path, so
        # by the time we land here it is always present. (It is not present for
        # orders captured before the pilot, or when the read races the write --
        # find_by_order returns None in both cases.)
        ledger_entry_id = record.ledger_entry_id
        response = payments.refund(
            processor_ref=record.processor_ref,
            amount_cents=amount_cents,
            ledger_entry_id=ledger_entry_id,
        )
        refund_store.mark_settled(record.id, response.reference)
        _audit(order_id, record, actor, amount_cents)
        log.info("instant refund settled order=%s ref=%s", order_id, response.reference)
        return response.reference

    if record is None:
        record = refund_store.create_intent(order_id, amount_cents, actor)
        log.info("created refund intent order=%s (no prior refund row)", order_id)

    refund_store.enqueue(record.id)
    log.info("queued refund order=%s intent=%s for async settlement", order_id, record.id)
    return None


def cancel_refund(order_id, actor):
    record = refund_store.find_by_order(order_id)
    if record is None:
        raise RefundError("no refund to cancel for order %s" % order_id)
    if record.status == "settled":
        raise RefundError("refund %s already settled" % record.id)
    refund_store.cancel(record.id, actor)
    log.info("refund cancelled order=%s intent=%s actor=%s", order_id, record.id, actor)
''',
    },
    {
        "service": "checkout",
        "path": "src/checkout/cart.py",
        "language": "python",
        "owner": "Nina Kowalski",
        "content": r'''"""Cart aggregate: line items, totals, and promotion application.

Totals are computed in integer cents throughout. Rounding happens exactly once,
at tax time, using banker's rounding to match the finance ledger.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import ROUND_HALF_EVEN, Decimal

from checkout import config
from checkout.promotions import apply_promotions

log = logging.getLogger(__name__)


class CartLimitExceeded(ValueError):
    pass


@dataclass
class LineItem:
    sku: str
    quantity: int
    unit_price_cents: int

    @property
    def subtotal_cents(self):
        return self.quantity * self.unit_price_cents


@dataclass
class Cart:
    cart_id: str
    currency: str = config.CURRENCY_DEFAULT
    items: list = field(default_factory=list)
    promo_codes: list = field(default_factory=list)

    def add(self, item):
        if len(self.items) >= config.MAX_LINE_ITEMS:
            raise CartLimitExceeded("cart %s is full" % self.cart_id)
        for existing in self.items:
            if existing.sku == item.sku:
                existing.quantity += item.quantity
                return existing
        self.items.append(item)
        return item

def subtotal_cents(cart):
    return sum(item.subtotal_cents for item in cart.items)


def tax_cents(taxable_cents, rate):
    product = Decimal(taxable_cents) * Decimal(str(rate))
    return int(product.quantize(Decimal("1"), rounding=ROUND_HALF_EVEN))


def totals(cart, tax_rate=0.0, shipping_cents=0):
    gross = subtotal_cents(cart)
    discount = apply_promotions(cart, gross)
    taxable = max(gross - discount, 0)
    tax = tax_cents(taxable, tax_rate)
    total = taxable + tax + shipping_cents
    log.debug("totals cart=%s gross=%d discount=%d tax=%d total=%d",
              cart.cart_id, gross, discount, tax, total)
    return {"subtotal_cents": gross, "discount_cents": discount, "tax_cents": tax,
            "shipping_cents": shipping_cents, "total_cents": total,
            "currency": cart.currency}
''',
    },
    {
        "service": "checkout",
        "path": "src/checkout/orchestrator.py",
        "language": "python",
        "owner": "Mei Tanaka",
        "content": r'''"""Checkout submit orchestration.

Order matters and is asserted by the integration suite: reserve inventory ->
capture payment -> persist order -> commit hold. If capture fails we release
the reservation first, otherwise stock leaks for the length of the hold TTL.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from checkout import cart as cart_mod
from checkout import config
from checkout.clients.inventory import InventoryClient
from checkout.clients.payments import PaymentsClient
from checkout.store import order_store

log = logging.getLogger(__name__)

inventory = InventoryClient(timeout_ms=config.PAYMENT_TIMEOUT_MS)
payments = PaymentsClient(
    base_url=config.PAYMENTS_BASE_URL, timeout_ms=config.PAYMENT_TIMEOUT_MS
)


class CheckoutError(RuntimeError):
    pass


@dataclass(frozen=True)
class SubmitResult:
    order_id: str
    total_cents: int
    replayed: bool


def submit_order(cart, idempotency_key, tax_rate=0.0, shipping_cents=0):
    existing = order_store.find_by_idempotency_key(idempotency_key)
    if existing is not None:
        log.info("submit replay cart=%s key=%s", cart.cart_id, idempotency_key)
        return SubmitResult(existing.order_id, existing.total_cents, True)

    computed = cart_mod.totals(cart, tax_rate=tax_rate, shipping_cents=shipping_cents)
    order_id = "ord_" + uuid.uuid4().hex[:12]

    hold = inventory.reserve(
        order_id=order_id,
        lines=[(item.sku, item.quantity) for item in cart.items],
    )
    try:
        capture = payments.capture(
            order_id=order_id,
            amount_cents=computed["total_cents"],
            currency=computed["currency"],
            idempotency_key=idempotency_key,
        )
    except Exception:
        log.exception("capture failed order=%s; releasing hold %s", order_id, hold.id)
        inventory.release(hold.id)
        raise CheckoutError("payment capture failed for order %s" % order_id)

    order_store.persist(order_id=order_id, cart_id=cart.cart_id, totals=computed,
                        processor_ref=capture.processor_ref,
                        idempotency_key=idempotency_key)
    inventory.commit(hold.id)
    log.info("order submitted order=%s total=%d %s", order_id,
             computed["total_cents"], computed["currency"])
    return SubmitResult(order_id, computed["total_cents"], False)
''',
    },
    {
        "service": "checkout",
        "path": "tests/test_idempotency.py",
        "language": "python",
        "owner": "Mei Tanaka",
        "content": r'''"""Integration coverage for checkout idempotency.

Suite: integration. Tracked as flaky in CI under ENG-2401 -- reruns pass.
"""
from __future__ import annotations

import time

import pytest

from checkout.orchestrator import submit_order
from tests.helpers import make_cart, reset_orders


def build_idempotency_key(prefix="test"):
    # One key per wall-clock second is plenty: the suite never runs two cases
    # inside the same second. (CI shards this suite across four workers, so it
    # very much does, and the workers then generate identical keys.)
    return "%s-%d" % (prefix, int(time.time()))


@pytest.fixture(autouse=True)
def clean_orders():
    reset_orders()
    yield
    reset_orders()


def test_duplicate_submit_returns_same_order():
    key = build_idempotency_key()
    cart = make_cart(items=3, total_cents=4599)

    first = submit_order(cart, idempotency_key=key)
    second = submit_order(cart, idempotency_key=key)

    assert first.order_id == second.order_id
    assert second.replayed is True


def test_distinct_keys_create_distinct_orders():
    cart = make_cart(items=1, total_cents=1299)

    left = submit_order(cart, idempotency_key=build_idempotency_key("left"))
    right = submit_order(cart, idempotency_key=build_idempotency_key("right"))

    assert left.order_id != right.order_id


def test_capture_failure_releases_inventory(monkeypatch):
    cart = make_cart(items=2, total_cents=2500)
    released = []

    monkeypatch.setattr(
        "checkout.orchestrator.inventory.release", lambda hold_id: released.append(hold_id)
    )
    monkeypatch.setattr(
        "checkout.orchestrator.payments.capture",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("upstream down")),
    )

    with pytest.raises(Exception):
        submit_order(cart, idempotency_key=build_idempotency_key("fail"))

    assert len(released) == 1
''',
    },
    {
        "service": "checkout",
        "path": "db/migrations/0031_refund_ledger.sql",
        "language": "sql",
        "owner": "Lena Ortiz",
        "content": r'''-- 0031_refund_ledger.sql
-- Adds the refund ledger backing the instant_refunds pilot.
-- Forward-only: the async settlement worker keeps writing to refund_intent,
-- the inline path writes both rows in one transaction.

BEGIN;

CREATE TABLE IF NOT EXISTS refund_ledger (
    id              BIGSERIAL PRIMARY KEY,
    order_id        TEXT        NOT NULL,
    processor_ref   TEXT,
    amount_cents    BIGINT      NOT NULL CHECK (amount_cents > 0),
    currency        CHAR(3)     NOT NULL DEFAULT 'USD',
    status          TEXT        NOT NULL DEFAULT 'pending',
    actor           TEXT        NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    settled_at      TIMESTAMPTZ,
    CONSTRAINT refund_ledger_status_ck
        CHECK (status IN ('pending', 'settled', 'cancelled', 'failed'))
);

-- One open refund per order; settled/cancelled rows are kept for audit.
CREATE UNIQUE INDEX IF NOT EXISTS refund_ledger_open_order_uq
    ON refund_ledger (order_id)
    WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS refund_ledger_settled_at_idx
    ON refund_ledger (settled_at DESC)
    WHERE settled_at IS NOT NULL;

ALTER TABLE refund_intent
    ADD COLUMN IF NOT EXISTS ledger_entry_id BIGINT REFERENCES refund_ledger (id);

COMMIT;
''',
    },

    # ------------------------------------------------------------------- catalog
    {
        "service": "catalog",
        "path": "src/catalog/models.py",
        "language": "python",
        "owner": "Sam Whitfield",
        "content": r'''"""Catalog domain models.

Plain dataclasses on purpose: ORM row objects stay inside
``catalog.repository`` so listing code cannot trigger lazy loading.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Availability(str, Enum):
    IN_STOCK = "in_stock"
    BACKORDER = "backorder"
    DISCONTINUED = "discontinued"


@dataclass(frozen=True)
class Money:
    amount_cents: int
    currency: str = "USD"

    def __post_init__(self):
        if self.amount_cents < 0:
            raise ValueError("money cannot be negative: %d" % self.amount_cents)


@dataclass(frozen=True)
class Product:
    id: str
    sku: str
    title: str
    category_id: str
    availability: Availability = Availability.IN_STOCK
    attributes: dict = field(default_factory=dict)
    updated_at: datetime = None

    @property
    def is_orderable(self):
        return self.availability is not Availability.DISCONTINUED


@dataclass(frozen=True)
class PriceRow:
    product_id: str
    list_price: Money
    sale_price: Money = None
    price_tier: str = "standard"

    @property
    def effective(self):
        if self.sale_price is not None and self.sale_price.amount_cents < self.list_price.amount_cents:
            return self.sale_price
        return self.list_price


@dataclass(frozen=True)
class PricedProduct:
    product: Product
    price: PriceRow

    def to_dict(self):
        return {"id": self.product.id, "sku": self.product.sku,
                "title": self.product.title,
                "availability": self.product.availability.value,
                "price_cents": self.price.effective.amount_cents,
                "currency": self.price.effective.currency,
                "tier": self.price.price_tier}
''',
    },
    {
        "service": "catalog",
        "path": "src/catalog/repository.py",
        "language": "python",
        "owner": "Sam Whitfield",
        "content": r'''"""Database access for the catalog service.

Methods take and return domain objects from ``catalog.models``. Bulk variants
exist for the hot paths; single-row variants remain for admin tooling.
"""
from __future__ import annotations

import logging

from catalog.db import pool
from catalog.models import Availability, Money, PriceRow, Product

log = logging.getLogger(__name__)

_PRODUCT_COLUMNS = "id, sku, title, category_id, availability, attributes, updated_at"


def _to_product(row):
    return Product(id=row["id"], sku=row["sku"], title=row["title"],
                   category_id=row["category_id"],
                   availability=Availability(row["availability"]),
                   attributes=row["attributes"] or {},
                   updated_at=row["updated_at"])


def _to_price(row):
    sale = None
    if row["sale_price_cents"] is not None:
        sale = Money(row["sale_price_cents"], row["currency"])
    return PriceRow(product_id=row["product_id"],
                    list_price=Money(row["list_price_cents"], row["currency"]),
                    sale_price=sale, price_tier=row["price_tier"])


def list_products(category_id, limit=200):
    sql = ("SELECT " + _PRODUCT_COLUMNS + " FROM product WHERE category_id = %s "
           "AND availability <> 'discontinued' ORDER BY rank_hint DESC, sku ASC "
           "LIMIT %s")
    with pool.cursor() as cur:
        cur.execute(sql, (category_id, limit))
        rows = cur.fetchall()
    log.debug("list_products category=%s rows=%d", category_id, len(rows))
    return [_to_product(row) for row in rows]


def fetch_price(product_id, currency="USD"):
    """Single-row price lookup. One round trip per call."""
    sql = ("SELECT product_id, list_price_cents, sale_price_cents, currency, "
           "price_tier FROM product_price WHERE product_id = %s AND currency = %s")
    with pool.cursor() as cur:
        cur.execute(sql, (product_id, currency))
        row = cur.fetchone()
    if row is None:
        log.warning("no price row product=%s currency=%s", product_id, currency)
        return None
    return _to_price(row)


def fetch_prices_bulk(product_ids, currency="USD"):
    """Batched price lookup: one round trip for the whole page."""
    if not product_ids:
        return {}
    sql = ("SELECT product_id, list_price_cents, sale_price_cents, currency, "
           "price_tier FROM product_price WHERE currency = %s AND product_id = ANY(%s)")
    with pool.cursor() as cur:
        cur.execute(sql, (currency, list(product_ids)))
        rows = cur.fetchall()
    log.debug("fetch_prices_bulk requested=%d found=%d", len(product_ids), len(rows))
    return {row["product_id"]: _to_price(row) for row in rows}
''',
    },
    {
        "service": "catalog",
        "path": "src/catalog/pricing.py",
        "language": "python",
        "owner": "Sam Whitfield",
        "content": r'''"""Price resolution for catalog listings.

The batched path is gated behind ``batch_pricing_enabled``; ``n_plus_one_guard``
raises once a request issues more per-row lookups than ``N_PLUS_ONE_THRESHOLD``,
so the pattern cannot come back unnoticed.
"""
from __future__ import annotations

import logging
import time

from catalog import repository, settings
from catalog.models import PricedProduct

log = logging.getLogger(__name__)

BATCH_PRICING_ENABLED = settings.get("batch_pricing_enabled", False)
N_PLUS_ONE_GUARD = settings.get("n_plus_one_guard", False)
N_PLUS_ONE_THRESHOLD = settings.get("n_plus_one_threshold", 25)


class QueryFanoutError(RuntimeError):
    """Raised by the guard when a request fans out into too many queries."""


def _priced(product, price):
    if price is None:
        return None
    return PricedProduct(product=product, price=price)


def price_listing(category_id, currency="USD", limit=200):
    started = time.monotonic()
    products = repository.list_products(category_id, limit=limit)

    if BATCH_PRICING_ENABLED:
        prices = repository.fetch_prices_bulk([p.id for p in products], currency)
        priced = [_priced(p, prices.get(p.id)) for p in products]
        queries = 2
    else:
        # Legacy path: one price query per product, plus the listing query.
        # Fine when a category held a dozen SKUs; category pages now return 200.
        priced = []
        queries = 1
        for product in products:
            price = repository.fetch_price(product.id, currency)
            queries += 1
            if N_PLUS_ONE_GUARD and queries > N_PLUS_ONE_THRESHOLD:
                raise QueryFanoutError(
                    "category %s issued %d price queries" % (category_id, queries)
                )
            priced.append(_priced(product, price))

    elapsed_ms = int((time.monotonic() - started) * 1000)
    result = [item for item in priced if item is not None]
    log.info("priced listing category=%s products=%d queries=%d elapsed_ms=%d batch=%s",
             category_id, len(result), queries, elapsed_ms, BATCH_PRICING_ENABLED)
    if elapsed_ms > 400:
        log.warning("slow price_listing category=%s elapsed_ms=%d queries=%d",
                    category_id, elapsed_ms, queries)
    return result


def price_single(product_id, currency="USD"):
    price = repository.fetch_price(product_id, currency)
    if price is None:
        raise LookupError("no price for product %s in %s" % (product_id, currency))
    return price.effective
''',
    },
    {
        "service": "catalog",
        "path": "db/migrations/0012_product_price_tier_index.sql",
        "language": "sql",
        "owner": "Ravi Shah",
        "content": r'''-- 0012_product_price_tier_index.sql
-- Supports the batched price lookup (product_id = ANY($1) AND currency = $2)
-- and the tier rollups the merchandising dashboard runs every hour.
-- Built CONCURRENTLY: product_price is ~40M rows in production.

CREATE INDEX CONCURRENTLY IF NOT EXISTS product_price_currency_product_idx
    ON product_price (currency, product_id)
    INCLUDE (list_price_cents, sale_price_cents, price_tier);

CREATE INDEX CONCURRENTLY IF NOT EXISTS product_price_tier_idx
    ON product_price (price_tier)
    WHERE price_tier <> 'standard';

-- The old single-column index is fully covered by the composite above.
DROP INDEX CONCURRENTLY IF EXISTS product_price_product_idx;

-- Merchandising rolls tiers up hourly; keep a materialized count so the
-- dashboard does not sequential-scan the whole table every hour.
CREATE MATERIALIZED VIEW IF NOT EXISTS product_price_tier_counts AS
SELECT currency,
       price_tier,
       count(*)          AS product_count,
       avg(list_price_cents)::bigint AS avg_list_price_cents
FROM product_price
GROUP BY currency, price_tier;

CREATE UNIQUE INDEX IF NOT EXISTS product_price_tier_counts_uq
    ON product_price_tier_counts (currency, price_tier);

ANALYZE product_price;
''',
    },

    # -------------------------------------------------------------------- search
    {
        "service": "search",
        "path": "src/search/query.py",
        "language": "python",
        "owner": "Mei Tanaka",
        "content": r'''"""Query execution for product search.

parse -> build the index query -> execute -> rank. The query cache sits in front
of execution and normally absorbs the large majority of index load.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time

from search import ranking, settings
from search.cache import RedisCache
from search.index import IndexClient

log = logging.getLogger(__name__)

# Turned off during the index-rebuild incident so cache writes would stop
# amplifying load on the Redis cluster while we reshard. Flip back to true once
# the rebuild lands. (Rebuild landed; this never got flipped back.)
CACHE_ENABLED = settings.get("cache_enabled", False)
CACHE_TTL_S = settings.get("cache_ttl_s", 300)
INDEX_SHARDS = settings.get("index_shards", 4)

cache = RedisCache(namespace="search:q")
index = IndexClient(shards=INDEX_SHARDS)


def cache_key(term, filters, page, size):
    document = {"t": term.strip().lower(), "f": filters or {}, "p": page, "s": size}
    payload = json.dumps(document, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def search(term, filters=None, page=0, size=24, user_segment="anon"):
    started = time.monotonic()
    key = cache_key(term, filters, page, size)

    if CACHE_ENABLED:
        cached = cache.get(key)
        if cached is not None:
            log.debug("cache hit term=%r key=%s", term, key)
            return cached
    else:
        log.warning(
            "query cache disabled (cache_enabled=false); every request is hitting "
            "the primary index"
        )

    hits = index.execute(term=term, filters=filters or {}, offset=page * size, limit=size)
    results = ranking.rank(hits, term=term, user_segment=user_segment)
    payload = {"term": term, "page": page, "size": size, "total": hits.total,
               "results": [r.to_dict() for r in results]}

    if CACHE_ENABLED:
        cache.set(key, payload, ttl_s=CACHE_TTL_S)

    elapsed_ms = int((time.monotonic() - started) * 1000)
    log.info(
        "search term=%r hits=%d elapsed_ms=%d cache_enabled=%s",
        term, hits.total, elapsed_ms, CACHE_ENABLED,
    )
    return payload


def invalidate(term, filters=None, page=0, size=24):
    cache.delete(cache_key(term, filters, page, size))
''',
    },
    {
        "service": "search",
        "path": "src/search/ranking.py",
        "language": "python",
        "owner": "Jordan Blake",
        "content": r'''"""Result ranking.

Score is a weighted blend of relevance, recency decay, merchandising boost and
a per-segment term. Weights live in config; their sum is asserted at import so
scores stay comparable across deploys.
"""
from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass

from search import settings

log = logging.getLogger(__name__)

WEIGHTS = {"relevance": settings.get("rank_w_relevance", 0.55),
           "recency": settings.get("rank_w_recency", 0.15),
           "merch": settings.get("rank_w_merch", 0.20),
           "segment": settings.get("rank_w_segment", 0.10)}
RECENCY_HALFLIFE_DAYS = settings.get("rank_recency_halflife_days", 45)

if abs(sum(WEIGHTS.values()) - 1.0) > 1e-6:
    raise ValueError("ranking weights must sum to 1.0, got %r" % WEIGHTS)


@dataclass
class RankedHit:
    product_id: str
    title: str
    score: float
    components: dict

    def to_dict(self):
        return {"product_id": self.product_id, "title": self.title,
                "score": round(self.score, 5)}


def _recency(updated_at_epoch, now=None):
    now = now or time.time()
    age_days = max((now - updated_at_epoch) / 86400.0, 0.0)
    return math.exp(-age_days * math.log(2) / RECENCY_HALFLIFE_DAYS)


def _segment_boost(hit, user_segment):
    if user_segment == "anon":
        return 0.0
    affinity = hit.segment_affinity or {}
    return min(affinity.get(user_segment, 0.0), 1.0)


def rank(hits, term, user_segment="anon"):
    ranked = []
    for hit in hits:
        components = {
            "relevance": hit.relevance,
            "recency": _recency(hit.updated_at_epoch),
            "merch": hit.merch_boost,
            "segment": _segment_boost(hit, user_segment),
        }
        score = sum(WEIGHTS[name] * value for name, value in components.items())
        ranked.append(RankedHit(hit.product_id, hit.title, score, components))

    ranked.sort(key=lambda r: (-r.score, r.product_id))
    if ranked:
        log.debug("ranked term=%r top=%s score=%.4f", term, ranked[0].product_id,
                  ranked[0].score)
    return ranked
''',
    },
    {
        "service": "search",
        "path": "src/search/indexer.py",
        "language": "python",
        "owner": "Mei Tanaka",
        "content": r'''"""Incremental indexer.

Applies catalog change events to the index in bulk flushes. Deletes go before
upserts inside a flush so a delete+recreate of the same SKU ends up present.
"""
from __future__ import annotations

import logging
import signal
import time

from search import settings
from search.index import IndexClient
from search.stream import CatalogChangeStream

log = logging.getLogger(__name__)

FLUSH_SIZE = settings.get("indexer_flush_size", 500)
FLUSH_INTERVAL_S = settings.get("indexer_flush_interval_s", 5)

index = IndexClient(shards=settings.get("index_shards", 4))
_running = True


def _handle_sigterm(signum, frame):
    global _running
    log.info("SIGTERM received; draining indexer buffer")
    _running = False


signal.signal(signal.SIGTERM, _handle_sigterm)


def _flush(upserts, deletes):
    if deletes:
        index.bulk_delete(deletes)
    if upserts:
        index.bulk_upsert(upserts)
    log.info("indexer flush upserts=%d deletes=%d", len(upserts), len(deletes))


def run(stream=None):
    stream = stream or CatalogChangeStream(group="search-indexer")
    upserts, deletes = [], []
    last_flush = time.monotonic()

    for event in stream:
        if event.kind == "delete":
            deletes.append(event.product_id)
        else:
            upserts.append(event.document)

        buffered = len(upserts) + len(deletes)
        due = (time.monotonic() - last_flush) >= FLUSH_INTERVAL_S
        if buffered >= FLUSH_SIZE or (buffered and due):
            try:
                _flush(upserts, deletes)
            except Exception:
                log.exception("flush failed; buffer retained for retry")
                time.sleep(1.0)
                continue
            stream.commit(event.offset)
            upserts, deletes = [], []
            last_flush = time.monotonic()

        if not _running:
            break

    _flush(upserts, deletes)
    log.info("indexer stopped cleanly")
''',
    },
    {
        "service": "search",
        "path": "tests/test_ranking.py",
        "language": "python",
        "owner": "Jordan Blake",
        "content": r'''"""Unit coverage for ranking blend behaviour."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from search import ranking


@dataclass
class FakeHit:
    product_id: str
    title: str = "widget"
    relevance: float = 0.5
    merch_boost: float = 0.0
    updated_at_epoch: float = field(default_factory=time.time)
    segment_affinity: dict = field(default_factory=dict)


def test_higher_relevance_ranks_first():
    hits = [FakeHit("a", relevance=0.2), FakeHit("b", relevance=0.9)]
    ranked = ranking.rank(hits, term="widget")
    assert [r.product_id for r in ranked] == ["b", "a"]


def test_ties_break_on_product_id_for_stability():
    hits = [FakeHit("z", relevance=0.5), FakeHit("a", relevance=0.5)]
    ranked = ranking.rank(hits, term="widget")
    assert [r.product_id for r in ranked] == ["a", "z"]


def test_stale_documents_decay():
    fresh = FakeHit("fresh", relevance=0.5)
    stale = FakeHit("stale", relevance=0.5, updated_at_epoch=time.time() - 400 * 86400)
    ranked = ranking.rank([stale, fresh], term="widget")
    assert ranked[0].product_id == "fresh"


def test_segment_boost_ignored_for_anonymous_traffic():
    hit = FakeHit("p1", segment_affinity={"loyalty": 1.0})
    anon = ranking.rank([hit], term="widget")[0].components["segment"]
    member = ranking.rank([hit], term="widget", user_segment="loyalty")[0].components["segment"]
    assert anon == 0.0
    assert member == 1.0
''',
    },

    # --------------------------------------------------------------- api-gateway
    {
        "service": "api-gateway",
        "path": "internal/config/config.go",
        "language": "go",
        "owner": "Priya Nair",
        "content": r'''// Package config loads gateway configuration from the mounted config map and
// the process environment. Values are read once at boot; traffic weights are
// the exception and refresh from the control plane every 10 seconds.
package config

import (
	"crypto/tls"
	"encoding/json"
	"fmt"
	"os"
	"strconv"
	"sync"
	"time"
)

const defaultPath = "/etc/novacart/gateway.json"

// Gateway is the full effective configuration.
type Gateway struct {
	Env            string            `json:"env"`
	Version        string            `json:"version"`
	ListenAddr     string            `json:"listen_addr"`
	RateLimitRPS   int               `json:"rate_limit_rps"`
	UpstreamHosts  map[string]string `json:"upstream_hosts"`
	RequestTimeout time.Duration     `json:"-"`
	DebugEnabled   bool              `json:"debug_enabled"`
}

// Upstreams carries per-route transport settings.
type Upstreams struct {
	mu       sync.RWMutex
	tls      map[string]*tls.Config
	fallback *tls.Config
}

var (
	once   sync.Once
	loaded *Gateway
	loadErr error
)

// TLSFor returns the TLS config for an upstream, falling back to the shared
// default when the upstream has no dedicated entry.
func (u *Upstreams) TLSFor(upstream string) *tls.Config {
	u.mu.RLock()
	defer u.mu.RUnlock()
	if cfg, ok := u.tls[upstream]; ok {
		return cfg.Clone()
	}
	return u.fallback.Clone()
}

func envInt(key string, fallback int) int {
	if value, err := strconv.Atoi(os.Getenv(key)); err == nil {
		return value
	}
	return fallback
}

// Load reads the config document exactly once.
func Load() (*Gateway, error) {
	once.Do(func() {
		path := defaultPath
		if custom := os.Getenv("NOVACART_GATEWAY_CONFIG"); custom != "" {
			path = custom
		}
		blob, err := os.ReadFile(path)
		if err != nil {
			loadErr = fmt.Errorf("read %s: %w", path, err)
			return
		}
		cfg := &Gateway{ListenAddr: ":8080", RateLimitRPS: 500}
		if err := json.Unmarshal(blob, cfg); err != nil {
			loadErr = fmt.Errorf("parse %s: %w", path, err)
			return
		}
		cfg.RateLimitRPS = envInt("NOVACART_GATEWAY_RPS", cfg.RateLimitRPS)
		cfg.RequestTimeout = time.Duration(envInt("NOVACART_GATEWAY_TIMEOUT_MS", 5000)) * time.Millisecond
		loaded = cfg
	})
	return loaded, loadErr
}
''',
    },
    {
        "service": "api-gateway",
        "path": "internal/proxy/pool.go",
        "language": "go",
        "owner": "Priya Nair",
        "content": r'''// Package proxy manages upstream connections for the API gateway.
//
// Rewritten in v5.1.0: every route now gets its own transport so per-route TLS
// material and per-route timeouts are honoured.
package proxy

import (
	"context"
	"fmt"
	"net"
	"net/http"
	"sync/atomic"
	"time"

	"github.com/novacart/api-gateway/internal/config"
	"github.com/novacart/api-gateway/internal/log"
)

const (
	dialTimeout      = 2 * time.Second
	idleConnTimeout  = 90 * time.Second
	maxIdlePerHost   = 64
	healthCheckEvery = 15 * time.Second
)

// Conn wraps a transport dedicated to a single upstream.
type Conn struct {
	Upstream  string
	Transport *http.Transport
	client    *http.Client
	done      chan struct{}
	createdAt time.Time
}

// Pool hands out upstream connections.
type Pool struct {
	cfg      *config.Upstreams
	inFlight int64
}

func NewPool(cfg *config.Upstreams) *Pool { return &Pool{cfg: cfg} }

// Acquire builds a connection for the given upstream. Building a transport is
// cheap, so v5.1.0 does it per request rather than keeping long-lived ones.
func (p *Pool) Acquire(ctx context.Context, upstream string) (*Conn, error) {
	if upstream == "" {
		return nil, fmt.Errorf("proxy: empty upstream")
	}
	atomic.AddInt64(&p.inFlight, 1)

	transport := &http.Transport{
		DialContext:         (&net.Dialer{Timeout: dialTimeout}).DialContext,
		TLSClientConfig:     p.cfg.TLSFor(upstream),
		MaxIdleConnsPerHost: maxIdlePerHost,
		IdleConnTimeout:     idleConnTimeout,
	}

	c := &Conn{Upstream: upstream, Transport: transport, done: make(chan struct{}),
		client: &http.Client{Transport: transport}, createdAt: time.Now()}

	// Watchdog: keep probing this upstream for as long as the connection lives.
	go func() {
		ticker := time.NewTicker(healthCheckEvery)
		defer ticker.Stop()
		for {
			select {
			case <-ticker.C:
				p.probe(c)
			case <-c.done:
				return
			}
		}
	}()

	log.Debugf("acquired upstream=%s in_flight=%d", upstream, atomic.LoadInt64(&p.inFlight))
	return c, nil
}

// Release closes the transport and stops the watchdog goroutine.
//
// NOTE: the v5.1.0 rewrite dropped the call to Release from Do -- the handler
// returns as soon as it has the response. Nothing else calls it, so every
// request leaves behind an idle transport plus a live watchdog goroutine.
func (p *Pool) Release(c *Conn) {
	close(c.done)
	c.Transport.CloseIdleConnections()
	atomic.AddInt64(&p.inFlight, -1)
	log.Debugf("released upstream=%s age=%s", c.Upstream, time.Since(c.createdAt))
}

func (p *Pool) probe(c *Conn) {
	req, _ := http.NewRequest(http.MethodHead, "http://"+c.Upstream+"/healthz", nil)
	if resp, err := c.client.Do(req); err == nil {
		_ = resp.Body.Close()
	}
}

// Do proxies a single request to the named upstream.
func (p *Pool) Do(ctx context.Context, upstream string, req *http.Request) (*http.Response, error) {
	c, err := p.Acquire(ctx, upstream)
	if err != nil {
		return nil, fmt.Errorf("acquire %s: %w", upstream, err)
	}

	resp, err := c.client.Do(req.WithContext(ctx))
	if err != nil {
		log.Errorf("upstream=%s request failed: %v", upstream, err)
		return nil, err
	}
	return resp, nil
}
''',
    },
    {
        "service": "api-gateway",
        "path": "internal/router/routes.go",
        "language": "go",
        "owner": "Tom Becker",
        "content": r'''// Package router wires public API routes to their upstream services.
//
// Route table is declarative: handlers are generic proxies, and anything
// route-specific (auth requirement, traffic weight, deprecation) lives in the
// Route struct so the control plane can reason about it.
package router

import (
	"net/http"

	"github.com/novacart/api-gateway/internal/handlers"
	"github.com/novacart/api-gateway/internal/middleware"
	"github.com/novacart/api-gateway/internal/proxy"
)

// Route describes one public endpoint.
type Route struct {
	Path       string
	Methods    []string
	Upstream   string
	AuthRequired bool
	Deprecated bool
	Weight     int // percentage of traffic, resolved by the control plane
}

// Table is the canonical route list for the edge.
var Table = []Route{
	{Path: "/v1/orders", Methods: []string{"GET", "POST"}, Upstream: "checkout.internal:8080", AuthRequired: true, Weight: 100},
	{Path: "/v2/orders", Methods: []string{"GET", "POST", "PATCH"}, Upstream: "checkout.internal:8080", AuthRequired: true, Weight: 0},
	{Path: "/v1/checkout", Methods: []string{"POST"}, Upstream: "checkout.internal:8080", AuthRequired: true, Weight: 100},
	{Path: "/v1/catalog", Methods: []string{"GET"}, Upstream: "catalog.internal:8080", Weight: 100},
	{Path: "/v1/search", Methods: []string{"GET"}, Upstream: "search.internal:8080", Weight: 100},
	{Path: "/v1/media", Methods: []string{"GET"}, Upstream: "media-service.internal:8080", Weight: 100},
	{Path: "/internal/debug", Methods: []string{"GET"}, Upstream: "", Weight: 0},
}

// New builds the edge mux.
func New(pool *proxy.Pool) http.Handler {
	mux := http.NewServeMux()

	for _, route := range Table {
		r := route
		if r.Upstream == "" {
			continue
		}
		var h http.Handler = handlers.NewProxyHandler(pool, r.Upstream, r.Path)
		h = middleware.MethodFilter(r.Methods, h)
		if r.AuthRequired {
			h = middleware.RequireToken(h)
		}
		if r.Deprecated {
			h = middleware.DeprecationNotice(r.Path, h)
		}
		h = middleware.RateLimit(h)
		h = middleware.AccessLog(r.Path, h)
		mux.Handle(r.Path, h)
	}

	mux.Handle("/internal/debug", handlers.Debug())
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("ok"))
	})
	return mux
}
''',
    },
    {
        "service": "api-gateway",
        "path": "internal/handlers/debug.go",
        "language": "go",
        "owner": "Tom Becker",
        "content": r'''package handlers

import (
	"encoding/json"
	"net/http"
	"os"
	"runtime"
	"strings"

	"github.com/novacart/api-gateway/internal/config"
	"github.com/novacart/api-gateway/internal/log"
)

// Debug returns the /internal/debug handler.
//
// Intended for the platform team during rollouts: it dumps the effective
// gateway config, the full process environment and a goroutine count so we can
// tell at a glance which build a pod is running.
//
// It is mounted before the auth middleware chain in router.New, so it answers
// any caller that can reach the listener. "internal" here means "we do not
// advertise it" -- the ingress does not filter the path.
func Debug() http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		cfg, err := config.Load()
		if err != nil {
			http.Error(w, "config unavailable", http.StatusInternalServerError)
			return
		}

		env := map[string]string{}
		for _, entry := range os.Environ() {
			parts := strings.SplitN(entry, "=", 2)
			if len(parts) == 2 {
				env[parts[0]] = parts[1]
			}
		}

		payload := map[string]interface{}{
			"version":        cfg.Version,
			"env":            cfg.Env,
			"listen_addr":    cfg.ListenAddr,
			"rate_limit_rps": cfg.RateLimitRPS,
			"upstreams":      cfg.UpstreamHosts,
			"goroutines":     runtime.NumGoroutine(),
			"environment":    env,
			"remote_addr":    r.RemoteAddr,
		}

		log.Infof("debug dump served to %s", r.RemoteAddr)
		w.Header().Set("Content-Type", "application/json")
		enc := json.NewEncoder(w)
		enc.SetIndent("", "  ")
		if err := enc.Encode(payload); err != nil {
			log.Errorf("debug encode failed: %v", err)
		}
	})
}
''',
    },
    {
        "service": "api-gateway",
        "path": "internal/middleware/ratelimit.go",
        "language": "go",
        "owner": "Priya Nair",
        "content": r'''package middleware

import (
	"net"
	"net/http"
	"strconv"
	"sync"
	"time"

	"github.com/novacart/api-gateway/internal/config"
	"github.com/novacart/api-gateway/internal/log"
)

// bucket is a token bucket for one client key.
type bucket struct {
	tokens   float64
	lastSeen time.Time
}

type limiter struct {
	mu      sync.Mutex
	buckets map[string]*bucket
	rps     float64
	burst   float64
}

var shared = func() *limiter {
	cfg, err := config.Load()
	rps := 500
	if err == nil && cfg.RateLimitRPS > 0 {
		rps = cfg.RateLimitRPS
	}
	return &limiter{
		buckets: make(map[string]*bucket),
		rps:     float64(rps),
		burst:   float64(rps) * 1.5,
	}
}()

func clientKey(r *http.Request) string {
	if token := r.Header.Get("X-Api-Client"); token != "" {
		return token
	}
	if host, _, err := net.SplitHostPort(r.RemoteAddr); err == nil {
		return host
	}
	return r.RemoteAddr
}

func (l *limiter) allow(key string) bool {
	now := time.Now()
	l.mu.Lock()
	defer l.mu.Unlock()

	b, ok := l.buckets[key]
	if !ok {
		l.buckets[key] = &bucket{tokens: l.burst - 1, lastSeen: now}
		return true
	}
	b.tokens += now.Sub(b.lastSeen).Seconds() * l.rps
	if b.tokens > l.burst {
		b.tokens = l.burst
	}
	b.lastSeen = now
	if b.tokens < 1 {
		return false
	}
	b.tokens--
	return true
}

// RateLimit rejects callers over their per-client budget with a 429.
func RateLimit(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		key := clientKey(r)
		if !shared.allow(key) {
			log.Warnf("rate limited client=%s path=%s", key, r.URL.Path)
			w.Header().Set("Retry-After", strconv.Itoa(1))
			http.Error(w, "rate limit exceeded", http.StatusTooManyRequests)
			return
		}
		next.ServeHTTP(w, r)
	})
}
''',
    },

    # ----------------------------------------------------------------- inventory
    {
        "service": "inventory",
        "path": "src/main/java/com/novacart/inventory/StockRepository.java",
        "language": "java",
        "owner": "Tom Becker",
        "content": r'''package com.novacart.inventory;

import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.sql.*;
import java.util.ArrayList;
import java.util.List;

/**
 * Stock reads and writes. The pool is created here rather than injected so the
 * sizing stays visible next to the queries that depend on it.
 */
public final class StockRepository {

    private static final Logger LOG = LoggerFactory.getLogger(StockRepository.class);

    /**
     * Connection pool size. Sized during the 2-pod pilot and never revisited;
     * inventory now runs 12 pods behind the checkout reserve path, and every
     * reserve call holds a connection for the length of the upstream write.
     */
    private static final int DB_POOL_SIZE = 5;

    private static final long CONNECTION_TIMEOUT_MS = 3_000L;
    private static final String SELECT_ON_HAND =
            "SELECT sku, on_hand, reserved FROM stock_level WHERE sku = ? FOR UPDATE";
    private static final String SELECT_BATCH =
            "SELECT sku, on_hand, reserved FROM stock_level WHERE sku = ANY (?)";


    private final HikariDataSource dataSource;

    public StockRepository(String jdbcUrl, String user, String password) {
        HikariConfig config = new HikariConfig();
        config.setJdbcUrl(jdbcUrl);
        config.setUsername(user);
        config.setPassword(password);
        config.setMaximumPoolSize(DB_POOL_SIZE);
        config.setMinimumIdle(DB_POOL_SIZE);
        config.setConnectionTimeout(CONNECTION_TIMEOUT_MS);
        config.setPoolName("inventory-stock");
        this.dataSource = new HikariDataSource(config);
        LOG.info("stock pool ready db_pool_size={} connection_timeout_ms={}",
                DB_POOL_SIZE, CONNECTION_TIMEOUT_MS);
    }

    public StockLevel findForUpdate(Connection tx, String sku) throws SQLException {
        try (PreparedStatement ps = tx.prepareStatement(SELECT_ON_HAND)) {
            ps.setString(1, sku);
            try (ResultSet rs = ps.executeQuery()) {
                if (!rs.next()) {
                    LOG.warn("no stock row for sku={}", sku);
                    return null;
                }
                return new StockLevel(rs.getString("sku"), rs.getInt("on_hand"),
                        rs.getInt("reserved"));
            }
        }
    }
    public List<StockLevel> findAll(List<String> skus) {
        List<StockLevel> levels = new ArrayList<>(skus.size());
        long started = System.nanoTime();
        try (Connection conn = dataSource.getConnection();
             PreparedStatement ps = conn.prepareStatement(SELECT_BATCH)) {
            ps.setArray(1, conn.createArrayOf("text", skus.toArray()));
            try (ResultSet rs = ps.executeQuery()) {
                while (rs.next()) {
                    levels.add(new StockLevel(rs.getString("sku"), rs.getInt("on_hand"),
                            rs.getInt("reserved")));
                }
            }
        } catch (SQLException e) {
            LOG.error("stock lookup failed for {} skus (pool size {}): {}",
                    skus.size(), DB_POOL_SIZE, e.getMessage(), e);
            throw new StockUnavailableException("stock lookup failed", e);
        }
        LOG.debug("findAll skus={} took_ms={}", skus.size(),
                (System.nanoTime() - started) / 1_000_000L);
        return levels;
    }

    public Connection begin() throws SQLException {
        Connection conn = dataSource.getConnection();
        conn.setAutoCommit(false);
        return conn;
    }
}
''',
    },
    {
        "service": "inventory",
        "path": "src/main/java/com/novacart/inventory/ReservationService.java",
        "language": "java",
        "owner": "Ravi Shah",
        "content": r'''package com.novacart.inventory;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.sql.Connection;
import java.sql.SQLException;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.UUID;

/**
 * Places and releases stock holds for checkout. A hold is soft: it decrements
 * availability without moving on_hand, and expires after {@link #HOLD_TTL}.
 */
public class ReservationService {

    private static final Logger LOG = LoggerFactory.getLogger(ReservationService.class);
    private static final Duration HOLD_TTL = Duration.ofMinutes(20);

    private final StockRepository stock;
    private final HoldRepository holds;

    public ReservationService(StockRepository stock, HoldRepository holds) {
        this.stock = stock;
        this.holds = holds;
    }

    public Hold reserve(String orderId, List<ReservationLine> lines) {
        String holdId = "hold_" + UUID.randomUUID().toString().substring(0, 12);
        Instant expiresAt = Instant.now().plus(HOLD_TTL);

        Connection tx = null;
        try {
            tx = stock.begin();
            for (ReservationLine line : lines) {
                StockLevel level = stock.findForUpdate(tx, line.sku());
                if (level == null) {
                    throw new StockUnavailableException("unknown sku " + line.sku());
                }
                int available = level.onHand() - level.reserved();
                if (available < line.quantity()) {
                    LOG.warn("insufficient stock sku={} requested={} available={}",
                            line.sku(), line.quantity(), available);
                    throw new StockUnavailableException("insufficient stock: " + line.sku());
                }
                holds.appendLine(tx, holdId, line.sku(), line.quantity());
            }
            holds.create(tx, holdId, orderId, expiresAt);
            tx.commit();
            LOG.info("reserved hold={} order={} lines={}", holdId, orderId, lines.size());
            return new Hold(holdId, orderId, expiresAt);
        } catch (SQLException e) {
            rollbackQuietly(tx);
            LOG.error("reserve failed order={}: {}", orderId, e.getMessage(), e);
            throw new StockUnavailableException("reserve failed for order " + orderId, e);
        } finally {
            closeQuietly(tx);
        }
    }

    public void release(String holdId) {
        holds.release(holdId);
        LOG.info("released hold={}", holdId);
    }

    private void rollbackQuietly(Connection tx) {
        if (tx == null) {
            return;
        }
        try {
            tx.rollback();
        } catch (SQLException ignored) {
            LOG.debug("rollback failed; connection is being discarded");
        }
    }

    private void closeQuietly(Connection tx) {
        try {
            if (tx != null) {
                tx.close();
            }
        } catch (SQLException e) {
            LOG.warn("could not return connection to pool: {}", e.getMessage());
        }
    }
}
''',
    },
    {
        "service": "inventory",
        "path": "src/main/java/com/novacart/inventory/StockController.java",
        "language": "java",
        "owner": "Tom Becker",
        "content": r'''package com.novacart.inventory;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

/** HTTP surface for stock levels and holds. Called by checkout and by ops tooling. */
@RestController
@RequestMapping("/v1/stock")
public class StockController {

    private static final Logger LOG = LoggerFactory.getLogger(StockController.class);
    private static final int MAX_BATCH = 200;

    private final StockRepository stock;
    private final ReservationService reservations;

    public StockController(StockRepository stock, ReservationService reservations) {
        this.stock = stock;
        this.reservations = reservations;
    }

    @GetMapping("/levels")
    public ResponseEntity<List<StockLevel>> levels(@RequestParam List<String> sku) {
        if (sku.size() > MAX_BATCH) {
            LOG.warn("batch too large: {} skus (max {})", sku.size(), MAX_BATCH);
            return ResponseEntity.status(HttpStatus.PAYLOAD_TOO_LARGE).build();
        }
        return ResponseEntity.ok(stock.findAll(sku));
    }

    @PostMapping("/holds")
    public ResponseEntity<Map<String, Object>> reserve(@RequestBody ReserveRequest request) {
        try {
            Hold hold = reservations.reserve(request.orderId(), request.lines());
            return ResponseEntity.status(HttpStatus.CREATED).body(Map.of(
                    "hold_id", hold.id(),
                    "order_id", hold.orderId(),
                    "expires_at", hold.expiresAt().toString()));
        } catch (StockUnavailableException e) {
            LOG.info("reserve rejected order={} reason={}", request.orderId(), e.getMessage());
            return ResponseEntity.status(HttpStatus.CONFLICT)
                    .body(Map.of("error", "stock_unavailable", "detail", e.getMessage()));
        }
    }

    @PostMapping("/holds/{holdId}/release")
    public ResponseEntity<Void> release(@PathVariable String holdId) {
        reservations.release(holdId);
        return ResponseEntity.noContent().build();
    }
}
''',
    },

    # ------------------------------------------------------------- media-service
    {
        "service": "media-service",
        "path": "src/media/assets.py",
        "language": "python",
        "owner": "Jordan Blake",
        "content": r'''"""Asset delivery.

Product imagery lives in the object store, behind the CDN -- which is where
every read is meant to terminate. Origin egress is billed per GB.
"""
from __future__ import annotations

import logging
import mimetypes
import time

from media import settings
from media.store import ObjectStore

log = logging.getLogger(__name__)

# Turned off while the CDN vendor migration was in flight -- signed URLs from
# the old edge were 404ing for a slice of traffic, so we pointed reads back at
# origin "for a day or two". The migration finished; this is still false, so
# every asset request is served straight from the bucket.
CDN_ENABLED = settings.get("cdn_enabled", False)
CDN_BASE_URL = settings.get("cdn_base_url", "https://cdn.novacart.io")
SIGNED_URL_TTL_S = settings.get("signed_url_ttl_s", 900)
ORIGIN_BUCKET = settings.get("origin_bucket", "novacart-media-prod")

store = ObjectStore(bucket=ORIGIN_BUCKET)


class AssetNotFound(LookupError):
    pass


def _key(asset_id, variant):
    return "assets/%s/%s" % (asset_id, variant)


def asset_url(asset_id, variant="800w"):
    """Return the URL a client should fetch this asset from."""
    key = _key(asset_id, variant)
    if CDN_ENABLED:
        return "%s/%s" % (CDN_BASE_URL, key)
    log.debug("cdn disabled; issuing origin signed URL for %s", key)
    return store.signed_url(key, ttl_s=SIGNED_URL_TTL_S)


def serve(asset_id, variant="800w"):
    """Stream an asset body plus response headers.

    With ``cdn_enabled`` false this is on the hot path for every product image
    on every page view, so each render fans out into origin reads.
    """
    key = _key(asset_id, variant)
    started = time.monotonic()

    if CDN_ENABLED:
        return {"redirect": "%s/%s" % (CDN_BASE_URL, key), "cache": "cdn"}

    try:
        body = store.get(key)
    except store.NotFound as exc:
        log.warning("asset miss key=%s", key)
        raise AssetNotFound(key) from exc

    elapsed_ms = int((time.monotonic() - started) * 1000)
    content_type = mimetypes.guess_type(key)[0] or "application/octet-stream"
    log.info("served asset from origin key=%s bytes=%d elapsed_ms=%d cdn_enabled=%s",
             key, len(body), elapsed_ms, CDN_ENABLED)
    headers = {"Content-Type": content_type, "Cache-Control": "public, max-age=86400",
               "X-Served-By": "origin"}
    return {"body": body, "headers": headers, "cache": "origin"}
''',
    },
    {
        "service": "media-service",
        "path": "src/media/transcode.py",
        "language": "python",
        "owner": "Sam Whitfield",
        "content": r'''"""Image variant generation.

Uploads land as a single original; this module derives the responsive ladder
(``320w`` through ``1600w``) plus a WebP twin for each rung. Work is idempotent:
re-running a transcode over an existing variant is a no-op unless the source
etag changed.
"""
from __future__ import annotations

import io
import logging

from PIL import Image, UnidentifiedImageError

from media import settings
from media.store import ObjectStore

log = logging.getLogger(__name__)

LADDER = (320, 640, 800, 1200, 1600)
JPEG_QUALITY = settings.get("jpeg_quality", 82)
WEBP_QUALITY = settings.get("webp_quality", 78)
MAX_SOURCE_BYTES = settings.get("max_source_bytes", 25 * 1024 * 1024)

store = ObjectStore(bucket=settings.get("origin_bucket", "novacart-media-prod"))


class TranscodeError(RuntimeError):
    pass


def _resize(image, width):
    if image.width <= width:
        return image.copy()
    height = round(image.height * (width / image.width))
    return image.resize((width, height), Image.LANCZOS)


def _encode(image, fmt):
    buffer = io.BytesIO()
    quality = WEBP_QUALITY if fmt == "WEBP" else JPEG_QUALITY
    image.convert("RGB").save(buffer, format=fmt, quality=quality, optimize=True)
    return buffer.getvalue()


def transcode(asset_id, source_key, source_etag):
    raw = store.get(source_key)
    if len(raw) > MAX_SOURCE_BYTES:
        raise TranscodeError(
            "source %s is %d bytes, over the %d limit" % (source_key, len(raw), MAX_SOURCE_BYTES)
        )
    try:
        original = Image.open(io.BytesIO(raw))
        original.load()
    except UnidentifiedImageError as exc:
        raise TranscodeError("unreadable source %s" % source_key) from exc

    written = []
    for width in LADDER:
        resized = _resize(original, width)
        for fmt, ext in (("JPEG", "jpg"), ("WEBP", "webp")):
            key = "assets/%s/%dw.%s" % (asset_id, width, ext)
            if store.etag(key) == source_etag:
                log.debug("variant %s already current; skipping", key)
                continue
            store.put(key, _encode(resized, fmt), metadata={"source_etag": source_etag})
            written.append(key)

    log.info("transcoded asset=%s variants=%d source=%s", asset_id, len(written), source_key)
    return written
''',
    },

    # ----------------------------------------------------------- analytics-worker
    {
        "service": "analytics-worker",
        "path": "src/analytics/consumer.py",
        "language": "python",
        "owner": "Ravi Shah",
        "content": r'''"""Event queue consumer: reads events off RabbitMQ, batches them, and hands
the batches to the aggregation pipeline."""
import logging
import signal
import time

import pika

from analytics import aggregates, settings

log = logging.getLogger(__name__)

QUEUE_NAME = settings.get("queue_name", "analytics.events")
AMQP_URL = settings.get("amqp_url", "amqp://analytics:analytics@rabbit.internal:5672/%2f")
BATCH_SIZE = settings.get("batch_size", 500)
FLUSH_INTERVAL_S = settings.get("flush_interval_s", 10)

# Prefetch is the number of unacked messages the broker will push to us. Raised
# from 200 to "no limit" so a slow flush cannot stall delivery -- but 0 means
# unlimited in AMQP, so the broker streams the whole backlog into this process.
PREFETCH_COUNT = settings.get("prefetch_count", 0)

_running = True


def _stop(signum, frame):
    global _running
    log.info("signal %s received; draining consumer", signum)
    _running = False


signal.signal(signal.SIGTERM, _stop)


def run():
    params = pika.URLParameters(AMQP_URL)
    params.heartbeat = 30
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    channel.queue_declare(queue=QUEUE_NAME, durable=True)
    channel.basic_qos(prefetch_count=PREFETCH_COUNT)
    log.info("consumer attached queue=%s prefetch_count=%d batch_size=%d",
             QUEUE_NAME, PREFETCH_COUNT, BATCH_SIZE)

    buffer = []
    last_flush = time.monotonic()

    try:
        for method, _props, body in channel.consume(QUEUE_NAME, inactivity_timeout=1.0):
            if method is not None:
                buffer.append((method.delivery_tag, body))

            due = buffer and (time.monotonic() - last_flush) >= FLUSH_INTERVAL_S
            if len(buffer) >= BATCH_SIZE or due:
                tag = buffer[-1][0]
                try:
                    aggregates.ingest([payload for _, payload in buffer])
                    channel.basic_ack(delivery_tag=tag, multiple=True)
                except Exception:
                    log.exception("aggregation failed; nacking %d", len(buffer))
                    channel.basic_nack(tag, multiple=True, requeue=True)
                buffer = []
                last_flush = time.monotonic()

            if not _running:
                break
    finally:
        channel.cancel()
        connection.close()
        log.info("consumer stopped; %d messages unflushed", len(buffer))
''',
    },
    {
        "service": "analytics-worker",
        "path": "src/analytics/aggregates.py",
        "language": "python",
        "owner": "Nina Kowalski",
        "content": r'''"""Rollup pipeline.

Normalizes JSON events, folds them into per-minute counters and writes those to
the warehouse staging table. Everything is additive, so replaying a batch is
safe as long as event ids are unique (the collector guarantees that).
"""
from __future__ import annotations

import collections
import json
import logging
from datetime import datetime, timezone

from analytics import settings
from analytics.warehouse import StagingWriter

log = logging.getLogger(__name__)

KNOWN_EVENTS = frozenset({"page_view", "product_view", "add_to_cart",
                          "checkout_started", "order_placed", "search_performed",
                          "refund_issued"})
DROP_UNKNOWN = settings.get("drop_unknown_events", True)

writer = StagingWriter(table=settings.get("staging_table", "events_minute"))


def _minute_bucket(epoch_ms):
    moment = datetime.fromtimestamp(epoch_ms / 1000.0, tz=timezone.utc)
    return moment.replace(second=0, microsecond=0)


def _parse(payload):
    try:
        event = json.loads(payload)
    except (ValueError, TypeError):
        log.warning("undecodable event payload of %d bytes", len(payload or b""))
        return None
    if "type" not in event or "ts_ms" not in event:
        log.warning("event missing required fields: %s", sorted(event)[:6])
        return None
    if event["type"] not in KNOWN_EVENTS:
        if DROP_UNKNOWN:
            return None
        log.info("passing through unknown event type %s", event["type"])
    return event


def ingest(payloads):
    counters = collections.Counter()
    revenue = collections.Counter()
    dropped = 0

    for payload in payloads:
        event = _parse(payload)
        if event is None:
            dropped += 1
            continue
        bucket = _minute_bucket(event["ts_ms"])
        key = (bucket, event["type"], event.get("channel", "web"))
        counters[key] += 1
        if event["type"] == "order_placed":
            revenue[key] += int(event.get("total_cents", 0))

    rows = [{"minute": bucket.isoformat(), "event_type": event_type,
             "channel": channel, "count": count,
             "revenue_cents": revenue[(bucket, event_type, channel)]}
            for (bucket, event_type, channel), count in sorted(counters.items())]
    writer.write(rows)
    log.info("ingested events=%d rows=%d dropped=%d", len(payloads), len(rows), dropped)
    return len(rows)
''',
    },

    # ------------------------------------------------------------- notifications
    {
        "service": "notifications",
        "path": "src/notifications/sender.py",
        "language": "python",
        "owner": "Alex Osei",
        "content": r'''"""Outbound delivery.

Email goes out through the transactional provider's HTTP API; SMS and push have
their own adapters. This module owns the provider call and the delivery record.
"""
from __future__ import annotations

import logging

import requests

from notifications import settings
from notifications.store import delivery_log
from notifications.templates import render

log = logging.getLogger(__name__)

PROVIDER_URL = settings.get("provider_url", "https://mail.provider.io/v3/send")
PROVIDER_TOKEN = settings.get("provider_token", "")
SMTP_POOL = settings.get("smtp_pool", 8)

# Provider-facing socket timeout, in milliseconds. Read here so it shows up in
# the startup config dump. The requests call below does not pass it, so the
# effective timeout is whatever the OS gives us -- i.e. none.
SMTP_TIMEOUT_MS = settings.get("smtp_timeout_ms", 5000)

_session = requests.Session()
_session.headers.update({
    "Authorization": "Bearer %s" % PROVIDER_TOKEN,
    "Content-Type": "application/json",
    "User-Agent": "novacart-notifications/1.4",
})


class DeliveryError(RuntimeError):
    pass


def _payload(template, to, variables):
    subject, html, text = render(template, variables)
    return {"to": [{"email": to}], "subject": subject, "html": html, "text": text,
            "pool": "transactional-%d" % SMTP_POOL}


def send(template, to, variables, correlation_id=None):
    body = _payload(template, to, variables)
    record = delivery_log.open(template=template, to=to, correlation_id=correlation_id)

    try:
        response = _session.post(PROVIDER_URL, json=body)
    except requests.RequestException as exc:
        delivery_log.fail(record.id, reason=str(exc))
        log.error("provider call failed template=%s to=%s: %s", template, to, exc)
        raise DeliveryError("provider unreachable") from exc

    if response.status_code >= 400:
        delivery_log.fail(record.id, reason="http_%d" % response.status_code)
        log.error(
            "provider rejected message template=%s status=%d body=%s",
            template, response.status_code, response.text[:280],
        )
        raise DeliveryError("provider returned %d" % response.status_code)

    provider_id = response.json().get("message_id")
    delivery_log.succeed(record.id, provider_id=provider_id)
    log.info("delivered template=%s to=%s provider_id=%s correlation_id=%s",
             template, to, provider_id, correlation_id)
    return provider_id
''',
    },
    {
        "service": "notifications",
        "path": "src/notifications/templates.py",
        "language": "python",
        "owner": "Alex Osei",
        "content": r'''"""Template registry and rendering.

Templates are Jinja files on disk under ``templates/<name>/``; each directory
holds ``subject.txt``, ``body.html`` and ``body.txt``. Rendering is strict --
an undefined variable is an error, not an empty string, because a receipt with
a blank amount is worse than a bounced send.
"""
from __future__ import annotations

import functools
import logging
import os

from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateNotFound

from notifications import settings

log = logging.getLogger(__name__)

TEMPLATE_ROOT = settings.get("template_root", "/srv/notifications/templates")
DEFAULT_LOCALE = settings.get("default_locale", "en-US")

REQUIRED_FILES = ("subject.txt", "body.html", "body.txt")


class TemplateError(RuntimeError):
    pass


@functools.lru_cache(maxsize=1)
def _env():
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_ROOT),
        undefined=StrictUndefined,
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["money"] = lambda cents: "%d.%02d" % (cents // 100, cents % 100)
    return env


def available():
    if not os.path.isdir(TEMPLATE_ROOT):
        log.error("template root %s does not exist", TEMPLATE_ROOT)
        return []
    names = []
    for entry in sorted(os.listdir(TEMPLATE_ROOT)):
        path = os.path.join(TEMPLATE_ROOT, entry)
        if all(os.path.exists(os.path.join(path, f)) for f in REQUIRED_FILES):
            names.append(entry)
        else:
            log.warning("template %s is incomplete; skipping", entry)
    return names


def render(name, variables, locale=None):
    locale = locale or DEFAULT_LOCALE
    context = dict(variables, locale=locale)
    try:
        subject = _env().get_template("%s/subject.txt" % name).render(context).strip()
        html = _env().get_template("%s/body.html" % name).render(context)
        text = _env().get_template("%s/body.txt" % name).render(context)
    except TemplateNotFound as exc:
        log.error("template %s missing file %s", name, exc.name)
        raise TemplateError("template %s is not installed" % name) from exc

    log.debug("rendered template=%s locale=%s subject=%r", name, locale, subject)
    return subject, html, text
''',
    },
    {
        "service": "notifications",
        "path": "src/notifications/queue.py",
        "language": "python",
        "owner": "Priya Nair",
        "content": r'''"""Delivery queue.

Callers enqueue; workers pop and hand off to ``sender.send``. Failures retry
with exponential backoff up to ``MAX_ATTEMPTS``, then park on the DLQ.
"""
from __future__ import annotations

import json
import logging
import random
import time

import redis

from notifications import settings
from notifications.sender import DeliveryError, send

log = logging.getLogger(__name__)

QUEUE_KEY = "notifications:outbound"
DLQ_KEY = "notifications:dead"
MAX_ATTEMPTS = settings.get("max_attempts", 5)
BASE_BACKOFF_S = settings.get("base_backoff_s", 0.5)

client = redis.Redis.from_url(settings.get("redis_url", "redis://redis.internal:6379/2"))


def enqueue(template, to, variables, correlation_id=None):
    message = {"template": template, "to": to, "variables": variables,
               "correlation_id": correlation_id, "attempts": 0}
    client.lpush(QUEUE_KEY, json.dumps(message))
    log.debug("enqueued template=%s to=%s", template, to)


def _backoff(attempts):
    ceiling = BASE_BACKOFF_S * (2 ** attempts)
    return min(ceiling, 30.0) * (0.5 + random.random() / 2.0)


def _requeue(message):
    message["attempts"] += 1
    if message["attempts"] >= MAX_ATTEMPTS:
        client.lpush(DLQ_KEY, json.dumps(message))
        log.error("message parked on DLQ template=%s to=%s attempts=%d",
                  message["template"], message["to"], message["attempts"])
        return
    time.sleep(_backoff(message["attempts"]))
    client.lpush(QUEUE_KEY, json.dumps(message))


def work_once(timeout_s=5):
    popped = client.brpop(QUEUE_KEY, timeout=timeout_s)
    if popped is None:
        return False
    message = json.loads(popped[1])
    try:
        send(message["template"], message["to"], message["variables"],
             correlation_id=message.get("correlation_id"))
    except DeliveryError:
        log.warning("delivery failed; requeueing template=%s", message["template"])
        _requeue(message)
    return True


def run_forever():
    log.info("notification worker online queue=%s max_attempts=%d", QUEUE_KEY, MAX_ATTEMPTS)
    while True:
        work_once()
''',
    },

    # ------------------------------------------------------------ storefront-web
    {
        "service": "storefront-web",
        "path": "src/components/CartSummary.tsx",
        "language": "typescript",
        "owner": "Nina Kowalski",
        "content": r'''"use client";

import { useMemo } from "react";

import { formatMoney } from "@/lib/money";
import { useCart } from "@/lib/hooks/useCart";
import type { CartLine, CartTotals } from "@/lib/types";

interface CartSummaryProps {
  compact?: boolean;
  onCheckout?: () => void;
}

function computeTotals(lines: CartLine[], taxRate: number): CartTotals {
  const subtotalCents = lines.reduce((sum, l) => sum + l.quantity * l.unitPriceCents, 0);
  const discountCents = lines.reduce((sum, l) => sum + (l.discountCents ?? 0), 0);
  const taxableCents = Math.max(subtotalCents - discountCents, 0);
  const taxCents = Math.round(taxableCents * taxRate);
  return { subtotalCents, discountCents, taxCents, totalCents: taxableCents + taxCents };
}

export function CartSummary({ compact = false, onCheckout }: CartSummaryProps) {
  const { lines, taxRate, currency, isLoading, error } = useCart();

  // Totals are recomputed on every keystroke in the promo field otherwise.
  const totals = useMemo(() => computeTotals(lines, taxRate), [lines, taxRate]);

  if (isLoading) return <div className="cart-summary--loading" aria-busy="true" />;

  if (error) {
    return (
      <div className="cart-summary cart-summary--error" role="alert">
        We could not load your cart. Refresh the page or try again shortly.
      </div>
    );
  }

  return (
    <aside className={compact ? "cart-summary cart-summary--compact" : "cart-summary"}>
      <h2 className="cart-summary__title">Order summary</h2>
      <dl className="cart-summary__rows">
        <div>
          <dt>Subtotal</dt>
          <dd>{formatMoney(totals.subtotalCents, currency)}</dd>
        </div>
        <div>
          <dt>Estimated tax</dt>
          <dd>{formatMoney(totals.taxCents, currency)}</dd>
        </div>
      </dl>
      <p className="cart-summary__total">
        <span>Total</span>
        <strong>{formatMoney(totals.totalCents, currency)}</strong>
      </p>
      <button
        type="button"
        className="cart-summary__cta"
        onClick={onCheckout}
        disabled={lines.length === 0}
      >
        Checkout
      </button>
    </aside>
  );
}
''',
    },
    {
        "service": "storefront-web",
        "path": "src/components/ProductGrid.tsx",
        "language": "typescript",
        "owner": "Mei Tanaka",
        "content": r'''import Image from "next/image";
import Link from "next/link";

import { formatMoney } from "@/lib/money";
import type { PricedProduct } from "@/lib/types";

interface ProductGridProps {
  products: PricedProduct[];
  columns?: 2 | 3 | 4;
  emptyMessage?: string;
  priority?: number;
}

function badgeFor(product: PricedProduct): string | null {
  if (product.availability === "backorder") return "Backorder";
  if (product.salePriceCents && product.salePriceCents < product.priceCents) return "Sale";
  if (product.isNew) return "New";
  return null;
}

export function ProductGrid({
  products,
  columns = 3,
  emptyMessage = "Nothing here yet.",
  priority = 4,
}: ProductGridProps) {
  if (products.length === 0) {
    return <p className="product-grid__empty">{emptyMessage}</p>;
  }

  return (
    <ul className="product-grid" data-columns={columns}>
      {products.map((product, index) => {
        const badge = badgeFor(product);
        const effectiveCents = product.salePriceCents ?? product.priceCents;

        return (
          <li key={product.id} className="product-card">
            <Link href={`/p/${product.slug}`} className="product-card__link">
              <div className="product-card__media">
                <Image
                  src={product.imageUrl}
                  alt={product.title}
                  width={400}
                  height={400}
                  sizes="(max-width: 640px) 50vw, 25vw"
                  priority={index < priority}
                />
                {badge ? <span className="product-card__badge">{badge}</span> : null}
              </div>
              <h3 className="product-card__title">{product.title}</h3>
              <p className="product-card__price">
                {formatMoney(effectiveCents, product.currency)}
                {product.salePriceCents ? (
                  <s className="product-card__price--was">
                    {formatMoney(product.priceCents, product.currency)}
                  </s>
                ) : null}
              </p>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
''',
    },
    {
        "service": "storefront-web",
        "path": "src/app/checkout/page.tsx",
        "language": "typescript",
        "owner": "Jordan Blake",
        "content": r'''import { redirect } from "next/navigation";
import { cookies } from "next/headers";

import { CartSummary } from "@/components/CartSummary";
import { AddressForm } from "@/components/AddressForm";
import { PaymentPanel } from "@/components/PaymentPanel";
import { apiClient } from "@/lib/api-client";
import type { Cart } from "@/lib/types";

export const metadata = {
  title: "Checkout | NovaCart",
  description: "Review your order and pay.",
};

export const dynamic = "force-dynamic";

async function loadCart(cartId: string): Promise<Cart | null> {
  try {
    return await apiClient.get<Cart>(`/v1/checkout/carts/${cartId}`, {
      cache: "no-store",
    });
  } catch (error) {
    console.error("checkout: cart load failed", { cartId, error });
    return null;
  }
}

export default async function CheckoutPage() {
  const cartId = cookies().get("nc_cart")?.value;
  if (!cartId) {
    redirect("/cart?reason=missing");
  }

  const cart = await loadCart(cartId);
  if (!cart || cart.lines.length === 0) {
    redirect("/cart?reason=empty");
  }

  return (
    <main className="checkout">
      <header className="checkout__header">
        <h1>Checkout</h1>
        <p className="checkout__step">Step 2 of 3</p>
      </header>

      <div className="checkout__layout">
        <section className="checkout__forms">
          <AddressForm initialAddress={cart.shippingAddress} />
          <PaymentPanel
            cartId={cart.id}
            totalCents={cart.totals.totalCents}
            currency={cart.currency}
          />
        </section>

        <CartSummary />
      </div>
    </main>
  );
}
''',
    },
    {
        "service": "storefront-web",
        "path": "src/lib/api-client.ts",
        "language": "typescript",
        "owner": "Nina Kowalski",
        "content": r'''/**
 * Thin fetch wrapper for the public API edge: retries, correlation ids and
 * error shaping live here rather than in each caller.
 */

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE ?? "https://api.novacart.io";
const DEFAULT_TIMEOUT_MS = 6000;
const RETRYABLE = new Set([408, 429, 502, 503, 504]);

export class ApiError extends Error {
  constructor(readonly status: number, readonly path: string, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

function correlationId(): string {
  return "randomUUID" in crypto ? crypto.randomUUID() : Math.random().toString(36).slice(2);
}

async function request<T>(
  path: string,
  init: RequestInit & { attempts?: number } = {},
): Promise<T> {
  const { attempts = 3, ...rest } = init;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS);

  try {
    for (let attempt = 1; attempt <= attempts; attempt += 1) {
      const response = await fetch(`${BASE_URL}${path}`, {
        ...rest,
        signal: controller.signal,
        headers: {
          Accept: "application/json",
          "X-Correlation-Id": correlationId(),
          ...(rest.headers ?? {}),
        },
      });

      if (response.ok) {
        return (await response.json()) as T;
      }

      if (!RETRYABLE.has(response.status) || attempt === attempts) {
        throw new ApiError(response.status, path, await response.text());
      }

      const backoffMs = 150 * 2 ** (attempt - 1);
      console.warn(`api-client: retrying ${path} after ${response.status}`);
      await new Promise((resolve) => setTimeout(resolve, backoffMs));
    }
    throw new ApiError(0, path, "exhausted retries");
  } finally {
    clearTimeout(timer);
  }
}

export const apiClient = {
  get: <T>(path: string, init?: RequestInit) => request<T>(path, { ...init, method: "GET" }),
  post: <T>(path: string, body: unknown, init?: RequestInit) =>
    request<T>(path, {
      ...init,
      method: "POST",
      body: JSON.stringify(body),
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    }),
};
''',
    },
]

COMMITS = [
    # ---------------------------------------------------------- days 1-60: bootstrap
    {"sha": "3f8a1c2", "service": "api-gateway", "author": "Priya Nair", "day": 1,
     "message": "api-gateway: initial edge skeleton with healthz and access log",
     "files": "internal/router/routes.go,internal/config/config.go", "additions": 214, "deletions": 0},
    {"sha": "9d41b07", "service": "catalog", "author": "Sam Whitfield", "day": 2,
     "message": "catalog: define Product and Money value objects",
     "files": "src/catalog/models.py", "additions": 96, "deletions": 0},
    {"sha": "c72e5a9", "service": "checkout", "author": "Nina Kowalski", "day": 3,
     "message": "checkout: bootstrap service package and settings module",
     "files": "src/checkout/config.py", "additions": 74, "deletions": 0},
    {"sha": "18be6d4", "service": "payments", "author": "Diego Ramos", "day": 4,
     "message": "payments: wire libpayproc client and capture happy path",
     "files": "src/payments/capture.py", "additions": 131, "deletions": 0},
    {"sha": "a05f3e8", "service": "storefront-web", "author": "Mei Tanaka", "day": 5,
     "message": "storefront-web: scaffold app router and base layout",
     "files": "src/app/checkout/page.tsx", "additions": 88, "deletions": 0},
    {"sha": "6e2c94b", "service": "catalog", "author": "Sam Whitfield", "day": 6,
     "message": "catalog: repository layer over the product table",
     "files": "src/catalog/repository.py", "additions": 118, "deletions": 4},
    {"sha": "b3417fd", "service": "payments", "author": "Diego Ramos", "day": 8,
     "message": "payments: config loader reads /etc/novacart/payments.json",
     "files": "src/payments/settings.py", "additions": 92, "deletions": 6},
    {"sha": "5cd80a1", "service": "checkout", "author": "Lena Ortiz", "day": 9,
     "message": "checkout: cart aggregate with integer-cent arithmetic",
     "files": "src/checkout/cart.py", "additions": 143, "deletions": 2},
    {"sha": "e91d276", "service": "api-gateway", "author": "Tom Becker", "day": 10,
     "message": "api-gateway: add /v1/catalog and /v1/search passthrough routes",
     "files": "internal/router/routes.go", "additions": 22, "deletions": 3},
    {"sha": "2a7f4c6", "service": "search", "author": "Mei Tanaka", "day": 11,
     "message": "search: first cut of the index client and query parser",
     "files": "src/search/query.py", "additions": 156, "deletions": 0},
    {"sha": "d40e9b3", "service": "notifications", "author": "Alex Osei", "day": 12,
     "message": "notifications: provider adapter for transactional email",
     "files": "src/notifications/sender.py", "additions": 104, "deletions": 0},
    {"sha": "7bc153e", "service": "checkout", "author": "Nina Kowalski", "day": 13,
     "message": "checkout: reserve-then-capture orchestration",
     "files": "src/checkout/orchestrator.py", "additions": 127, "deletions": 8},
    {"sha": "f28a60d", "service": "payments", "author": "Diego Ramos", "day": 14,
     "message": "payments: notify_client posts receipts after capture",
     "files": "src/payments/notify_client.py,src/payments/capture.py", "additions": 88, "deletions": 5},
    {"sha": "31d7e4a", "service": "search", "author": "Jordan Blake", "day": 15,
     "message": "search: weighted ranking blend with recency decay",
     "files": "src/search/ranking.py", "additions": 121, "deletions": 0},
    {"sha": "8f06b95", "service": "storefront-web", "author": "Nina Kowalski", "day": 16,
     "message": "storefront-web: product grid component",
     "files": "src/components/ProductGrid.tsx", "additions": 97, "deletions": 0},
    {"sha": "c4e2170", "service": "notifications", "author": "Alex Osei", "day": 17,
     "message": "notifications: strict Jinja rendering so blank receipts fail loudly",
     "files": "src/notifications/templates.py", "additions": 86, "deletions": 12},
    {"sha": "0b5d8fa", "service": "api-gateway", "author": "Priya Nair", "day": 18,
     "message": "api-gateway: token bucket rate limiter per client key",
     "files": "internal/middleware/ratelimit.go", "additions": 134, "deletions": 0},
    {"sha": "a63f92c", "service": "catalog", "author": "Ravi Shah", "day": 19,
     "message": "catalog: initial price table migration",
     "files": "db/migrations/0012_product_price_tier_index.sql", "additions": 18, "deletions": 0},
    {"sha": "56ea3d1", "service": "payments", "author": "Lena Ortiz", "day": 21,
     "message": "payments: nightly settlement job grouped by merchant",
     "files": "src/payments/settlement.py", "additions": 148, "deletions": 0},
    {"sha": "d18c7b4", "service": "checkout", "author": "Mei Tanaka", "day": 22,
     "message": "checkout: integration suite for idempotent submits",
     "files": "tests/test_idempotency.py", "additions": 71, "deletions": 0},
    {"sha": "9a4b06e", "service": "search", "author": "Mei Tanaka", "day": 23,
     "message": "search: incremental indexer consuming catalog change events",
     "files": "src/search/indexer.py", "additions": 139, "deletions": 0},
    {"sha": "e7302fb", "service": "storefront-web", "author": "Jordan Blake", "day": 24,
     "message": "storefront-web: typed fetch wrapper with retry on 5xx",
     "files": "src/lib/api-client.ts", "additions": 112, "deletions": 0},
    {"sha": "2c9f581", "service": "payments", "author": "Diego Ramos", "day": 25,
     "message": "payments: unit tests around capture and receipt failure",
     "files": "tests/test_capture_retries.py", "additions": 64, "deletions": 0},
    {"sha": "bf5a3d7", "service": "catalog", "author": "Sam Whitfield", "day": 26,
     "message": "catalog: pricing module resolving list vs sale price",
     "files": "src/catalog/pricing.py", "additions": 93, "deletions": 0},
    {"sha": "47d0e2a", "service": "api-gateway", "author": "Tom Becker", "day": 27,
     "message": "api-gateway: require bearer token on order routes",
     "files": "internal/router/routes.go", "additions": 19, "deletions": 6},
    {"sha": "10b8c63", "service": "search", "author": "Jordan Blake", "day": 28,
     "message": "search: ranking unit tests including tie-break stability",
     "files": "tests/test_ranking.py", "additions": 58, "deletions": 0},
    {"sha": "ea67491", "service": "notifications", "author": "Priya Nair", "day": 29,
     "message": "notifications: redis-backed outbound queue with DLQ",
     "files": "src/notifications/queue.py", "additions": 117, "deletions": 3},
    {"sha": "38fc0d5", "service": "storefront-web", "author": "Nina Kowalski", "day": 30,
     "message": "storefront-web: cart summary panel",
     "files": "src/components/CartSummary.tsx", "additions": 128, "deletions": 0},
    {"sha": "7e14ab8", "service": "checkout", "author": "Lena Ortiz", "day": 31,
     "message": "checkout: cap carts at 100 line items",
     "files": "src/checkout/cart.py,src/checkout/config.py", "additions": 24, "deletions": 5},
    {"sha": "b902f6c", "service": "payments", "author": "Diego Ramos", "day": 32,
     "message": "payments: idempotency key lookup before contacting processor",
     "files": "src/payments/capture.py", "additions": 31, "deletions": 9},
    {"sha": "5d3e7a0", "service": "inventory", "author": "Tom Becker", "day": 33,
     "message": "inventory: new service, stock levels and holds",
     "files": "src/main/java/com/novacart/inventory/StockRepository.java", "additions": 187, "deletions": 0},
    {"sha": "c8a51fe", "service": "inventory", "author": "Tom Becker", "day": 34,
     "message": "inventory: reservation service with soft holds",
     "files": "src/main/java/com/novacart/inventory/ReservationService.java", "additions": 142, "deletions": 0},
    {"sha": "0f6b294", "service": "catalog", "author": "Ravi Shah", "day": 35,
     "message": "catalog: index price rows by (currency, product_id)",
     "files": "db/migrations/0012_product_price_tier_index.sql", "additions": 12, "deletions": 4},
    {"sha": "a2740db", "service": "search", "author": "Mei Tanaka", "day": 36,
     "message": "search: enable query cache in front of the index",
     "files": "src/search/query.py", "additions": 41, "deletions": 6},
    {"sha": "94ecf13", "service": "api-gateway", "author": "Priya Nair", "day": 37,
     "message": "api-gateway: structured access logs with correlation ids",
     "files": "internal/router/routes.go,internal/middleware/ratelimit.go", "additions": 47, "deletions": 12},
    {"sha": "6b18d5a", "service": "inventory", "author": "Ravi Shah", "day": 38,
     "message": "inventory: REST surface for levels and holds",
     "files": "src/main/java/com/novacart/inventory/StockController.java", "additions": 108, "deletions": 0},
    {"sha": "d7f30c6", "service": "storefront-web", "author": "Mei Tanaka", "day": 39,
     "message": "storefront-web: checkout page skeleton behind cart cookie",
     "files": "src/app/checkout/page.tsx", "additions": 63, "deletions": 21},
    {"sha": "1e59b8f", "service": "checkout", "author": "Nina Kowalski", "day": 40,
     "message": "checkout: release inventory hold when capture fails",
     "files": "src/checkout/orchestrator.py,tests/test_idempotency.py", "additions": 38, "deletions": 7},
    {"sha": "83c6a4e", "service": "media-service", "author": "Jordan Blake", "day": 41,
     "message": "media-service: object store adapter and signed URLs",
     "files": "src/media/assets.py", "additions": 96, "deletions": 0},
    {"sha": "f501d29", "service": "media-service", "author": "Sam Whitfield", "day": 42,
     "message": "media-service: responsive variant ladder on upload",
     "files": "src/media/transcode.py", "additions": 121, "deletions": 0},
    {"sha": "2db947c", "service": "analytics-worker", "author": "Ravi Shah", "day": 43,
     "message": "analytics-worker: AMQP consumer skeleton",
     "files": "src/analytics/consumer.py", "additions": 104, "deletions": 0},
    {"sha": "b6e0851", "service": "analytics-worker", "author": "Nina Kowalski", "day": 44,
     "message": "analytics-worker: per-minute rollups into warehouse staging",
     "files": "src/analytics/aggregates.py", "additions": 113, "deletions": 0},
    {"sha": "40a2f7d", "service": "payments", "author": "Lena Ortiz", "day": 45,
     "message": "payments: chunk settlement batches so one merchant cannot stall the run",
     "files": "src/payments/settlement.py", "additions": 34, "deletions": 11},
    {"sha": "cf83e16", "service": "notifications", "author": "Alex Osei", "day": 46,
     "message": "notifications: exponential backoff with jitter on requeue",
     "files": "src/notifications/queue.py", "additions": 27, "deletions": 8},
    {"sha": "79bd403", "service": "search", "author": "Jordan Blake", "day": 47,
     "message": "search: assert ranking weights sum to 1.0 at import",
     "files": "src/search/ranking.py", "additions": 9, "deletions": 1},
    {"sha": "e352cb8", "service": "catalog", "author": "Sam Whitfield", "day": 48,
     "message": "catalog: drop discontinued products from listings",
     "files": "src/catalog/repository.py", "additions": 11, "deletions": 4},
    {"sha": "05c9a71", "service": "storefront-web", "author": "Jordan Blake", "day": 49,
     "message": "storefront-web: abort in-flight requests after 6s",
     "files": "src/lib/api-client.ts", "additions": 22, "deletions": 6},
    {"sha": "ab417ef", "service": "api-gateway", "author": "Tom Becker", "day": 50,
     "message": "api-gateway: reap idle rate-limit buckets every minute",
     "files": "internal/middleware/ratelimit.go", "additions": 26, "deletions": 2},
    {"sha": "3c8e60b", "service": "checkout", "author": "Lena Ortiz", "day": 51,
     "message": "checkout: refund intents and the async settle worker",
     "files": "src/checkout/refunds.py", "additions": 132, "deletions": 0},
    {"sha": "d914072", "service": "inventory", "author": "Tom Becker", "day": 52,
     "message": "inventory: expire holds after 20 minutes",
     "files": "src/main/java/com/novacart/inventory/ReservationService.java", "additions": 29, "deletions": 6},
    {"sha": "6741bfa", "service": "payments", "author": "Diego Ramos", "day": 53,
     "message": "payments: fail the payment when the receipt is undeliverable",
     "files": "src/payments/capture.py,src/payments/notify_client.py", "additions": 42, "deletions": 9},
    {"sha": "8e0d35c", "service": "media-service", "author": "Jordan Blake", "day": 54,
     "message": "media-service: cache-control headers on origin responses",
     "files": "src/media/assets.py", "additions": 15, "deletions": 3},
    {"sha": "b25a9d8", "service": "analytics-worker", "author": "Ravi Shah", "day": 55,
     "message": "analytics-worker: ack batches with multiple=true",
     "files": "src/analytics/consumer.py", "additions": 19, "deletions": 12},
    {"sha": "17ce4b6", "service": "search", "author": "Mei Tanaka", "day": 56,
     "message": "search: shard-aware index client",
     "files": "src/search/query.py,src/search/indexer.py", "additions": 44, "deletions": 17},
    {"sha": "e6b8103", "service": "storefront-web", "author": "Nina Kowalski", "day": 57,
     "message": "storefront-web: sale badge on discounted cards",
     "files": "src/components/ProductGrid.tsx", "additions": 24, "deletions": 5},
    {"sha": "9f0a4d7", "service": "checkout", "author": "Mei Tanaka", "day": 58,
     "message": "checkout: docs for the submit ordering guarantees",
     "files": "src/checkout/orchestrator.py", "additions": 18, "deletions": 2},
    {"sha": "42fd81e", "service": "notifications", "author": "Alex Osei", "day": 59,
     "message": "notifications: park messages on the DLQ after 5 attempts",
     "files": "src/notifications/queue.py", "additions": 21, "deletions": 4},
    {"sha": "c07e5b2", "service": "api-gateway", "author": "Priya Nair", "day": 60,
     "message": "api-gateway: cut v3.0.0",
     "files": "internal/config/config.go", "additions": 3, "deletions": 3},

    # -------------------------------------------------------- days 61-140: hardening
    {"sha": "5a3b16d", "service": "payments", "author": "Diego Ramos", "day": 62,
     "message": "payments: log effective config at startup",
     "files": "src/payments/settings.py", "additions": 14, "deletions": 2},
    {"sha": "e814c90", "service": "catalog", "author": "Sam Whitfield", "day": 63,
     "message": "catalog: return None instead of raising on missing price row",
     "files": "src/catalog/repository.py,src/catalog/pricing.py", "additions": 17, "deletions": 11},
    {"sha": "76d2fa4", "service": "storefront-web", "author": "Jordan Blake", "day": 64,
     "message": "storefront-web: bump next to 14.1.3",
     "files": "src/lib/api-client.ts", "additions": 6, "deletions": 6},
    {"sha": "1bf9037", "service": "search", "author": "Jordan Blake", "day": 65,
     "message": "search: personalize ranking for logged-in segments",
     "files": "src/search/ranking.py,tests/test_ranking.py", "additions": 52, "deletions": 8},
    {"sha": "d5807ae", "service": "inventory", "author": "Ravi Shah", "day": 66,
     "message": "inventory: batch stock lookups with ANY()",
     "files": "src/main/java/com/novacart/inventory/StockRepository.java", "additions": 38, "deletions": 14},
    {"sha": "0ac6e39", "service": "checkout", "author": "Nina Kowalski", "day": 67,
     "message": "checkout: banker's rounding for tax to match the ledger",
     "files": "src/checkout/cart.py", "additions": 23, "deletions": 9},
    {"sha": "9e47b51", "service": "api-gateway", "author": "Tom Becker", "day": 68,
     "message": "api-gateway: per-route method filtering",
     "files": "internal/router/routes.go", "additions": 31, "deletions": 7},
    {"sha": "38a0dc7", "service": "notifications", "author": "Alex Osei", "day": 69,
     "message": "notifications: money filter for template amounts",
     "files": "src/notifications/templates.py", "additions": 12, "deletions": 1},
    {"sha": "b1f6e82", "service": "analytics-worker", "author": "Nina Kowalski", "day": 70,
     "message": "analytics-worker: drop unknown event types by default",
     "files": "src/analytics/aggregates.py", "additions": 26, "deletions": 6},
    {"sha": "4c2d709", "service": "media-service", "author": "Sam Whitfield", "day": 71,
     "message": "media-service: skip transcode when the variant etag matches",
     "files": "src/media/transcode.py", "additions": 21, "deletions": 5},
    {"sha": "72e5a1b", "service": "payments", "author": "Lena Ortiz", "day": 72,
     "message": "payments: record settlement receipts for reconciliation",
     "files": "src/payments/settlement.py", "additions": 29, "deletions": 6},
    {"sha": "af309d6", "service": "storefront-web", "author": "Mei Tanaka", "day": 73,
     "message": "storefront-web: prioritize the first four grid images",
     "files": "src/components/ProductGrid.tsx", "additions": 14, "deletions": 3},
    {"sha": "6d84c05", "service": "search", "author": "Mei Tanaka", "day": 74,
     "message": "search: stable cache keys from sorted JSON payloads",
     "files": "src/search/query.py", "additions": 19, "deletions": 12},
    {"sha": "c93b7e4", "service": "checkout", "author": "Lena Ortiz", "day": 75,
     "message": "checkout: cancel_refund guards already-settled refunds",
     "files": "src/checkout/refunds.py", "additions": 22, "deletions": 3},
    {"sha": "20fa68d", "service": "inventory", "author": "Tom Becker", "day": 76,
     "message": "inventory: SELECT ... FOR UPDATE while placing holds",
     "files": "src/main/java/com/novacart/inventory/StockRepository.java", "additions": 27, "deletions": 8},
    {"sha": "e5710bc", "service": "api-gateway", "author": "Priya Nair", "day": 77,
     "message": "api-gateway: read rate limit from config instead of a const",
     "files": "internal/middleware/ratelimit.go,internal/config/config.go", "additions": 33, "deletions": 14},
    {"sha": "8b4e0f3", "service": "catalog", "author": "Ravi Shah", "day": 78,
     "message": "catalog: ANALYZE after building the price index",
     "files": "db/migrations/0012_product_price_tier_index.sql", "additions": 4, "deletions": 0},
    {"sha": "31c9d7a", "service": "payments", "author": "Diego Ramos", "day": 79,
     "message": "payments: surface processor decline reasons to callers",
     "files": "src/payments/capture.py,tests/test_capture_retries.py", "additions": 36, "deletions": 11},
    {"sha": "f7a2065", "service": "analytics-worker", "author": "Ravi Shah", "day": 80,
     "message": "analytics-worker: heartbeat every 30s to survive slow flushes",
     "files": "src/analytics/consumer.py", "additions": 11, "deletions": 3},
    {"sha": "594be18", "service": "storefront-web", "author": "Nina Kowalski", "day": 81,
     "message": "storefront-web: memoize cart totals selector",
     "files": "src/components/CartSummary.tsx", "additions": 17, "deletions": 9},
    {"sha": "ad0637f", "service": "notifications", "author": "Priya Nair", "day": 82,
     "message": "notifications: reuse one requests.Session across sends",
     "files": "src/notifications/sender.py", "additions": 18, "deletions": 7},
    {"sha": "6ef1c94", "service": "search", "author": "Jordan Blake", "day": 83,
     "message": "search: cap segment affinity at 1.0",
     "files": "src/search/ranking.py", "additions": 5, "deletions": 2},
    {"sha": "c26805d", "service": "checkout", "author": "Mei Tanaka", "day": 84,
     "message": "checkout: helper fixtures for the integration suite",
     "files": "tests/test_idempotency.py", "additions": 29, "deletions": 6},
    {"sha": "13f9ea7", "service": "media-service", "author": "Jordan Blake", "day": 85,
     "message": "media-service: reject sources over 25MB",
     "files": "src/media/transcode.py", "additions": 13, "deletions": 2},
    {"sha": "7052bd1", "service": "inventory", "author": "Ravi Shah", "day": 86,
     "message": "inventory: reject stock batches larger than 200 SKUs",
     "files": "src/main/java/com/novacart/inventory/StockController.java", "additions": 15, "deletions": 3},
    {"sha": "b8d43a6", "service": "api-gateway", "author": "Tom Becker", "day": 87,
     "message": "api-gateway: /v2/orders route registered dark at weight 0",
     "files": "internal/router/routes.go", "additions": 8, "deletions": 1},
    {"sha": "2f60c8e", "service": "catalog", "author": "Sam Whitfield", "day": 88,
     "message": "catalog: typed availability enum replaces string literals",
     "files": "src/catalog/models.py,src/catalog/repository.py", "additions": 41, "deletions": 23},
    {"sha": "94ab125", "service": "payments", "author": "Lena Ortiz", "day": 89,
     "message": "payments: skip settlement when there is nothing to settle",
     "files": "src/payments/settlement.py", "additions": 9, "deletions": 2},
    {"sha": "e0c7f38", "service": "storefront-web", "author": "Jordan Blake", "day": 90,
     "message": "storefront-web: shape API errors into a typed ApiError",
     "files": "src/lib/api-client.ts", "additions": 34, "deletions": 12},
    {"sha": "5b198da", "service": "search", "author": "Mei Tanaka", "day": 91,
     "message": "search: flush the indexer buffer on SIGTERM",
     "files": "src/search/indexer.py", "additions": 24, "deletions": 5},
    {"sha": "df3620c", "service": "notifications", "author": "Alex Osei", "day": 92,
     "message": "notifications: log provider rejections with a truncated body",
     "files": "src/notifications/sender.py", "additions": 12, "deletions": 4},
    {"sha": "a7e4593", "service": "checkout", "author": "Nina Kowalski", "day": 93,
     "message": "checkout: never log the partner credential value",
     "files": "src/checkout/config.py", "additions": 8, "deletions": 3},
    {"sha": "6c05b7f", "service": "analytics-worker", "author": "Nina Kowalski", "day": 94,
     "message": "analytics-worker: revenue counters alongside event counts",
     "files": "src/analytics/aggregates.py", "additions": 23, "deletions": 7},
    {"sha": "84fa2e1", "service": "api-gateway", "author": "Priya Nair", "day": 95,
     "message": "api-gateway: cut v3.4.0",
     "files": "internal/config/config.go", "additions": 3, "deletions": 3},
    {"sha": "10d9c46", "service": "inventory", "author": "Tom Becker", "day": 96,
     "message": "inventory: return 409 rather than 500 on insufficient stock",
     "files": "src/main/java/com/novacart/inventory/StockController.java", "additions": 19, "deletions": 8},
    {"sha": "cb7031a", "service": "catalog", "author": "Sam Whitfield", "day": 97,
     "message": "catalog: pricing returns dictionaries the API can serialize",
     "files": "src/catalog/models.py", "additions": 21, "deletions": 4},
    {"sha": "3e58f0b", "service": "payments", "author": "Diego Ramos", "day": 98,
     "message": "payments: correlation id header on every notifications call",
     "files": "src/payments/notify_client.py", "additions": 14, "deletions": 3},
    {"sha": "97b2e6d", "service": "storefront-web", "author": "Mei Tanaka", "day": 99,
     "message": "storefront-web: redirect empty carts away from checkout",
     "files": "src/app/checkout/page.tsx", "additions": 16, "deletions": 4},
    {"sha": "42c1a80", "service": "search", "author": "Jordan Blake", "day": 100,
     "message": "search: docs on the ranking weight contract",
     "files": "src/search/ranking.py", "additions": 15, "deletions": 2},
    {"sha": "d6e937f", "service": "checkout", "author": "Lena Ortiz", "day": 101,
     "message": "checkout: promotion stacking rules",
     "files": "src/checkout/cart.py", "additions": 37, "deletions": 12},
    {"sha": "0847bce", "service": "media-service", "author": "Sam Whitfield", "day": 102,
     "message": "media-service: WebP twin for every ladder rung",
     "files": "src/media/transcode.py", "additions": 26, "deletions": 9},
    {"sha": "b53d19e", "service": "notifications", "author": "Priya Nair", "day": 103,
     "message": "notifications: warn on incomplete template directories",
     "files": "src/notifications/templates.py", "additions": 17, "deletions": 5},
    {"sha": "7fa4025", "service": "api-gateway", "author": "Tom Becker", "day": 104,
     "message": "api-gateway: deprecation-notice middleware",
     "files": "internal/router/routes.go", "additions": 22, "deletions": 3},
    {"sha": "ec1904b", "service": "analytics-worker", "author": "Ravi Shah", "day": 105,
     "message": "analytics-worker: prefetch 200 to bound consumer memory",
     "files": "src/analytics/consumer.py", "additions": 8, "deletions": 3},
    {"sha": "58b7d3c", "service": "payments", "author": "Lena Ortiz", "day": 106,
     "message": "payments: batch settlement retries by merchant",
     "files": "src/payments/settlement.py", "additions": 31, "deletions": 14},
    {"sha": "a4f0e26", "service": "inventory", "author": "Ravi Shah", "day": 107,
     "message": "inventory: quiet rollback helper to stop leaking connections",
     "files": "src/main/java/com/novacart/inventory/ReservationService.java", "additions": 34, "deletions": 11},
    {"sha": "2d6ba95", "service": "catalog", "author": "Ravi Shah", "day": 108,
     "message": "catalog: partial index on non-standard price tiers",
     "files": "db/migrations/0012_product_price_tier_index.sql", "additions": 7, "deletions": 1},
    {"sha": "f918c04", "service": "storefront-web", "author": "Nina Kowalski", "day": 109,
     "message": "storefront-web: loading and error states for the cart panel",
     "files": "src/components/CartSummary.tsx", "additions": 28, "deletions": 6},
    {"sha": "63ce7a8", "service": "search", "author": "Mei Tanaka", "day": 110,
     "message": "search: apply deletes before upserts inside a flush",
     "files": "src/search/indexer.py", "additions": 18, "deletions": 9},
    {"sha": "8a5f21d", "service": "checkout", "author": "Mei Tanaka", "day": 111,
     "message": "checkout: assert hold release on capture failure",
     "files": "tests/test_idempotency.py", "additions": 24, "deletions": 2},
    {"sha": "10e4b7c", "service": "notifications", "author": "Alex Osei", "day": 112,
     "message": "notifications: delivery log records provider message ids",
     "files": "src/notifications/sender.py", "additions": 21, "deletions": 6},
    {"sha": "cd2903f", "service": "api-gateway", "author": "Priya Nair", "day": 113,
     "message": "api-gateway: bump go to 1.22",
     "files": "internal/config/config.go", "additions": 4, "deletions": 4},
    {"sha": "7b3e6a1", "service": "payments", "author": "Diego Ramos", "day": 114,
     "message": "payments: retry receipts up to 3 times with backoff",
     "files": "src/payments/notify_client.py,src/payments/settings.py", "additions": 43, "deletions": 12},
    {"sha": "e6047db", "service": "media-service", "author": "Jordan Blake", "day": 115,
     "message": "media-service: point reads at the CDN edge",
     "files": "src/media/assets.py", "additions": 27, "deletions": 8},
    {"sha": "35a8c92", "service": "analytics-worker", "author": "Nina Kowalski", "day": 116,
     "message": "analytics-worker: nack the whole batch when aggregation throws",
     "files": "src/analytics/consumer.py", "additions": 16, "deletions": 7},
    {"sha": "b0f75e3", "service": "catalog", "author": "Sam Whitfield", "day": 117,
     "message": "catalog: log slow listings over 400ms",
     "files": "src/catalog/pricing.py", "additions": 13, "deletions": 2},
    {"sha": "94d1c67", "service": "storefront-web", "author": "Jordan Blake", "day": 118,
     "message": "storefront-web: retry only on 408/429/5xx",
     "files": "src/lib/api-client.ts", "additions": 11, "deletions": 5},
    {"sha": "2ea590b", "service": "inventory", "author": "Tom Becker", "day": 119,
     "message": "inventory: name the Hikari pool so metrics are attributable",
     "files": "src/main/java/com/novacart/inventory/StockRepository.java", "additions": 6, "deletions": 1},
    {"sha": "f43b8d0", "service": "search", "author": "Jordan Blake", "day": 120,
     "message": "search: round scores in API responses",
     "files": "src/search/ranking.py", "additions": 4, "deletions": 2},
    {"sha": "5c17e49", "service": "checkout", "author": "Nina Kowalski", "day": 121,
     "message": "checkout: read payment timeout from the environment",
     "files": "src/checkout/config.py", "additions": 9, "deletions": 3},
    {"sha": "a980f2e", "service": "notifications", "author": "Priya Nair", "day": 122,
     "message": "notifications: worker loop entrypoint",
     "files": "src/notifications/queue.py", "additions": 14, "deletions": 1},
    {"sha": "d3ba605", "service": "api-gateway", "author": "Tom Becker", "day": 123,
     "message": "api-gateway: chain middleware in a fixed, documented order",
     "files": "internal/router/routes.go", "additions": 26, "deletions": 18},
    {"sha": "76e2109", "service": "payments", "author": "Diego Ramos", "day": 124,
     "message": "payments: cover the undeliverable-receipt path in tests",
     "files": "tests/test_capture_retries.py", "additions": 27, "deletions": 4},
    {"sha": "1fc48ab", "service": "analytics-worker", "author": "Ravi Shah", "day": 125,
     "message": "analytics-worker: flush on a 10s timer as well as on size",
     "files": "src/analytics/consumer.py", "additions": 19, "deletions": 8},
    {"sha": "8d5b03c", "service": "media-service", "author": "Sam Whitfield", "day": 126,
     "message": "media-service: LANCZOS resampling for downscales",
     "files": "src/media/transcode.py", "additions": 8, "deletions": 4},
    {"sha": "e7c1946", "service": "catalog", "author": "Ravi Shah", "day": 127,
     "message": "catalog: build the price index CONCURRENTLY",
     "files": "db/migrations/0012_product_price_tier_index.sql", "additions": 6, "deletions": 6},
    {"sha": "3b0af78", "service": "storefront-web", "author": "Mei Tanaka", "day": 128,
     "message": "storefront-web: cut v2.9.0",
     "files": "src/lib/api-client.ts", "additions": 2, "deletions": 2},
    {"sha": "c50e832", "service": "search", "author": "Mei Tanaka", "day": 129,
     "message": "search: 300s TTL on cached query payloads",
     "files": "src/search/query.py", "additions": 12, "deletions": 4},
    {"sha": "9147fed", "service": "checkout", "author": "Lena Ortiz", "day": 130,
     "message": "checkout: refund ledger migration",
     "files": "db/migrations/0031_refund_ledger.sql", "additions": 34, "deletions": 0},
    {"sha": "62d70b4", "service": "inventory", "author": "Ravi Shah", "day": 131,
     "message": "inventory: log hold placement with line counts",
     "files": "src/main/java/com/novacart/inventory/ReservationService.java", "additions": 9, "deletions": 2},
    {"sha": "af6b153", "service": "notifications", "author": "Alex Osei", "day": 132,
     "message": "notifications: cache the Jinja environment",
     "files": "src/notifications/templates.py", "additions": 11, "deletions": 6},
    {"sha": "0e93da7", "service": "api-gateway", "author": "Priya Nair", "day": 133,
     "message": "api-gateway: keepalive tuning on upstream dials",
     "files": "internal/proxy/pool.go", "additions": 96, "deletions": 0},
    {"sha": "d81c40e", "service": "payments", "author": "Lena Ortiz", "day": 134,
     "message": "payments: settle yesterday by default in the cron entrypoint",
     "files": "src/payments/settlement.py", "additions": 12, "deletions": 5},
    {"sha": "5fa2c68", "service": "storefront-web", "author": "Nina Kowalski", "day": 135,
     "message": "storefront-web: disable the CTA on empty carts",
     "files": "src/components/CartSummary.tsx", "additions": 7, "deletions": 2},
    {"sha": "b6407e9", "service": "analytics-worker", "author": "Nina Kowalski", "day": 136,
     "message": "analytics-worker: docs on replay safety",
     "files": "src/analytics/aggregates.py", "additions": 14, "deletions": 1},
    {"sha": "27e8b1d", "service": "catalog", "author": "Sam Whitfield", "day": 137,
     "message": "catalog: guard against negative money values",
     "files": "src/catalog/models.py", "additions": 8, "deletions": 1},
    {"sha": "ca396f2", "service": "search", "author": "Jordan Blake", "day": 138,
     "message": "search: test that stale documents decay below fresh ones",
     "files": "tests/test_ranking.py", "additions": 13, "deletions": 2},
    {"sha": "704be5a", "service": "checkout", "author": "Mei Tanaka", "day": 139,
     "message": "checkout: cut v1.8.0",
     "files": "src/checkout/config.py", "additions": 2, "deletions": 2},
    {"sha": "e2d7f81", "service": "inventory", "author": "Tom Becker", "day": 140,
     "message": "inventory: cut v0.9.0",
     "files": "src/main/java/com/novacart/inventory/StockController.java", "additions": 3, "deletions": 3},

    # ------------------------------------------------- days 141-260: growth + scale
    {"sha": "39fb2c7", "service": "search", "author": "Mei Tanaka", "day": 141,
     "message": "search: warm the cache for the top 500 head terms on boot",
     "files": "src/search/query.py", "additions": 46, "deletions": 7},
    {"sha": "8ce0451", "service": "checkout", "author": "Lena Ortiz", "day": 142,
     "message": "checkout: link refund intents to ledger entries",
     "files": "db/migrations/0031_refund_ledger.sql,src/checkout/refunds.py", "additions": 41, "deletions": 13},
    {"sha": "b74d9e0", "service": "api-gateway", "author": "Priya Nair", "day": 143,
     "message": "api-gateway: pool health probes every 15s",
     "files": "internal/proxy/pool.go", "additions": 38, "deletions": 6},
    {"sha": "1a6c83f", "service": "payments", "author": "Diego Ramos", "day": 144,
     "message": "payments: ENG-1804 record failure reason on declines",
     "files": "src/payments/capture.py", "additions": 18, "deletions": 6},
    {"sha": "6205ade", "service": "storefront-web", "author": "Jordan Blake", "day": 145,
     "message": "storefront-web: track checkout_started from the summary CTA",
     "files": "src/components/CartSummary.tsx", "additions": 15, "deletions": 3},
    {"sha": "d0b4917", "service": "catalog", "author": "Sam Whitfield", "day": 146,
     "message": "catalog: rank_hint ordering for category listings",
     "files": "src/catalog/repository.py", "additions": 12, "deletions": 6},
    {"sha": "4e8f16c", "service": "inventory", "author": "Ravi Shah", "day": 147,
     "message": "inventory: sweeper releases expired holds",
     "files": "src/main/java/com/novacart/inventory/ReservationService.java", "additions": 44, "deletions": 9},
    {"sha": "97ca3b5", "service": "notifications", "author": "Alex Osei", "day": 148,
     "message": "notifications: raise smtp pool to 8 connections",
     "files": "src/notifications/sender.py", "additions": 5, "deletions": 5},
    {"sha": "f31de84", "service": "analytics-worker", "author": "Ravi Shah", "day": 149,
     "message": "analytics-worker: bump pika to 1.3.2",
     "files": "src/analytics/consumer.py", "additions": 3, "deletions": 3},
    {"sha": "5d92016", "service": "media-service", "author": "Jordan Blake", "day": 150,
     "message": "media-service: 15 minute TTL on signed origin URLs",
     "files": "src/media/assets.py", "additions": 10, "deletions": 4},
    {"sha": "ae470f3", "service": "checkout", "author": "Nina Kowalski", "day": 151,
     "message": "checkout: extract promotion application from totals()",
     "files": "src/checkout/cart.py", "additions": 33, "deletions": 27},
    {"sha": "c8b1652", "service": "search", "author": "Jordan Blake", "day": 152,
     "message": "search: merchandising boost term in the blend",
     "files": "src/search/ranking.py,tests/test_ranking.py", "additions": 39, "deletions": 14},
    {"sha": "20e6fd9", "service": "api-gateway", "author": "Tom Becker", "day": 153,
     "message": "api-gateway: fall back to remote addr when X-Api-Client is absent",
     "files": "internal/middleware/ratelimit.go", "additions": 17, "deletions": 5},
    {"sha": "b3f7048", "service": "payments", "author": "Lena Ortiz", "day": 154,
     "message": "payments: settlement batch size configurable at 250",
     "files": "src/payments/settings.py,src/payments/settlement.py", "additions": 14, "deletions": 7},
    {"sha": "76d05ca", "service": "storefront-web", "author": "Mei Tanaka", "day": 155,
     "message": "storefront-web: responsive sizes attribute on grid images",
     "files": "src/components/ProductGrid.tsx", "additions": 9, "deletions": 3},
    {"sha": "e41c983", "service": "inventory", "author": "Tom Becker", "day": 156,
     "message": "inventory: bump HikariCP to 5.1.0",
     "files": "src/main/java/com/novacart/inventory/StockRepository.java", "additions": 4, "deletions": 4},
    {"sha": "0af5b27", "service": "catalog", "author": "Ravi Shah", "day": 157,
     "message": "catalog: drop the superseded single-column price index",
     "files": "db/migrations/0012_product_price_tier_index.sql", "additions": 3, "deletions": 1},
    {"sha": "d6820ec", "service": "notifications", "author": "Priya Nair", "day": 158,
     "message": "notifications: bound DLQ replays behind an admin command",
     "files": "src/notifications/queue.py", "additions": 26, "deletions": 8},
    {"sha": "958ea31", "service": "analytics-worker", "author": "Nina Kowalski", "day": 159,
     "message": "analytics-worker: channel dimension on rollups",
     "files": "src/analytics/aggregates.py", "additions": 22, "deletions": 11},
    {"sha": "3c74b6f", "service": "checkout", "author": "Mei Tanaka", "day": 160,
     "message": "checkout: docs for refund path selection",
     "files": "src/checkout/refunds.py", "additions": 17, "deletions": 3},
    {"sha": "e09d5a8", "service": "search", "author": "Mei Tanaka", "day": 161,
     "message": "search: commit stream offsets only after a successful flush",
     "files": "src/search/indexer.py", "additions": 21, "deletions": 12},
    {"sha": "127c4be", "service": "api-gateway", "author": "Priya Nair", "day": 162,
     "message": "api-gateway: cut v4.0.0",
     "files": "internal/config/config.go", "additions": 3, "deletions": 3},
    {"sha": "84fb90d", "service": "payments", "author": "Diego Ramos", "day": 163,
     "message": "payments: freeze CaptureResult as a dataclass",
     "files": "src/payments/capture.py", "additions": 24, "deletions": 16},
    {"sha": "b1e6273", "service": "media-service", "author": "Sam Whitfield", "day": 164,
     "message": "media-service: quality knobs for JPEG and WebP encodes",
     "files": "src/media/transcode.py", "additions": 16, "deletions": 6},
    {"sha": "5a03fc9", "service": "storefront-web", "author": "Nina Kowalski", "day": 165,
     "message": "storefront-web: aria-busy on the loading cart skeleton",
     "files": "src/components/CartSummary.tsx", "additions": 6, "deletions": 2},
    {"sha": "de1478b", "service": "inventory", "author": "Ravi Shah", "day": 166,
     "message": "inventory: surface hold expiry in the create response",
     "files": "src/main/java/com/novacart/inventory/StockController.java", "additions": 12, "deletions": 4},
    {"sha": "6fb2091", "service": "catalog", "author": "Sam Whitfield", "day": 167,
     "message": "catalog: bulk price lookup for the category page rewrite",
     "files": "src/catalog/repository.py,src/catalog/pricing.py", "additions": 58, "deletions": 9},
    {"sha": "9d5083a", "service": "notifications", "author": "Alex Osei", "day": 168,
     "message": "notifications: locale passthrough to templates",
     "files": "src/notifications/templates.py", "additions": 18, "deletions": 7},
    {"sha": "42a7ec6", "service": "search", "author": "Jordan Blake", "day": 169,
     "message": "search: retune recency halflife to 45 days",
     "files": "src/search/ranking.py", "additions": 4, "deletions": 4},
    {"sha": "c07b48f", "service": "checkout", "author": "Lena Ortiz", "day": 170,
     "message": "checkout: partial unique index on open refunds",
     "files": "db/migrations/0031_refund_ledger.sql", "additions": 9, "deletions": 2},
    {"sha": "31ed970", "service": "analytics-worker", "author": "Ravi Shah", "day": 171,
     "message": "analytics-worker: drain cleanly on SIGTERM",
     "files": "src/analytics/consumer.py", "additions": 23, "deletions": 6},
    {"sha": "7b6c2d4", "service": "api-gateway", "author": "Tom Becker", "day": 172,
     "message": "api-gateway: document the route table fields",
     "files": "internal/router/routes.go", "additions": 19, "deletions": 4},
    {"sha": "ea38516", "service": "payments", "author": "Lena Ortiz", "day": 173,
     "message": "payments: keep settling other merchants when one batch fails",
     "files": "src/payments/settlement.py", "additions": 17, "deletions": 9},
    {"sha": "58c9f02", "service": "storefront-web", "author": "Jordan Blake", "day": 174,
     "message": "storefront-web: correlation id header on every request",
     "files": "src/lib/api-client.ts", "additions": 14, "deletions": 3},
    {"sha": "0d4a7be", "service": "media-service", "author": "Jordan Blake", "day": 175,
     "message": "media-service: raise AssetNotFound instead of returning empty bodies",
     "files": "src/media/assets.py", "additions": 15, "deletions": 8},
    {"sha": "b8250ea", "service": "inventory", "author": "Tom Becker", "day": 176,
     "message": "inventory: cut v1.0.0",
     "files": "src/main/java/com/novacart/inventory/StockRepository.java", "additions": 3, "deletions": 3},
    {"sha": "f6013cd", "service": "catalog", "author": "Ravi Shah", "day": 177,
     "message": "catalog: INCLUDE price columns to make the index covering",
     "files": "db/migrations/0012_product_price_tier_index.sql", "additions": 5, "deletions": 3},
    {"sha": "295e7ab", "service": "checkout", "author": "Nina Kowalski", "day": 178,
     "message": "checkout: reuse one PaymentsClient per process",
     "files": "src/checkout/orchestrator.py,src/checkout/refunds.py", "additions": 19, "deletions": 14},
    {"sha": "cb64f38", "service": "search", "author": "Mei Tanaka", "day": 179,
     "message": "search: invalidate helper for admin-triggered reindex",
     "files": "src/search/query.py", "additions": 11, "deletions": 1},
    {"sha": "7a1e05d", "service": "notifications", "author": "Priya Nair", "day": 180,
     "message": "notifications: cut v1.2.0",
     "files": "src/notifications/sender.py", "additions": 2, "deletions": 2},
    {"sha": "e5cb241", "service": "analytics-worker", "author": "Nina Kowalski", "day": 181,
     "message": "analytics-worker: tolerate undecodable payloads",
     "files": "src/analytics/aggregates.py", "additions": 17, "deletions": 5},
    {"sha": "40f8b96", "service": "api-gateway", "author": "Priya Nair", "day": 182,
     "message": "api-gateway: expose in-flight connection count",
     "files": "internal/proxy/pool.go", "additions": 13, "deletions": 2},
    {"sha": "9e207ca", "service": "payments", "author": "Diego Ramos", "day": 183,
     "message": "payments: bump requests to 2.32.3",
     "files": "src/payments/notify_client.py", "additions": 3, "deletions": 3},
    {"sha": "163bd50", "service": "storefront-web", "author": "Mei Tanaka", "day": 184,
     "message": "storefront-web: backorder badge on out-of-stock cards",
     "files": "src/components/ProductGrid.tsx", "additions": 11, "deletions": 3},
    {"sha": "8d4e7f1", "service": "checkout", "author": "Mei Tanaka", "day": 185,
     "message": "checkout: reset order fixtures between integration cases",
     "files": "tests/test_idempotency.py", "additions": 16, "deletions": 4},
    {"sha": "c1a9603", "service": "catalog", "author": "Sam Whitfield", "day": 186,
     "message": "catalog: log query counts per listing request",
     "files": "src/catalog/pricing.py", "additions": 14, "deletions": 4},
    {"sha": "36b8ed2", "service": "inventory", "author": "Ravi Shah", "day": 187,
     "message": "inventory: 3s connection timeout on the stock pool",
     "files": "src/main/java/com/novacart/inventory/StockRepository.java", "additions": 7, "deletions": 2},
    {"sha": "b027a5e", "service": "search", "author": "Jordan Blake", "day": 188,
     "message": "search: revert 'personalize anonymous traffic by geo'",
     "files": "src/search/ranking.py", "additions": 6, "deletions": 34},
    {"sha": "5f30ce8", "service": "media-service", "author": "Sam Whitfield", "day": 189,
     "message": "media-service: bump pillow to 10.3.0",
     "files": "src/media/transcode.py", "additions": 3, "deletions": 3},
    {"sha": "e94d16b", "service": "notifications", "author": "Alex Osei", "day": 190,
     "message": "notifications: template inventory endpoint for support tooling",
     "files": "src/notifications/templates.py", "additions": 23, "deletions": 6},
    {"sha": "72c58a0", "service": "api-gateway", "author": "Tom Becker", "day": 191,
     "message": "api-gateway: mount /v1/media route",
     "files": "internal/router/routes.go", "additions": 6, "deletions": 1},
    {"sha": "af169d3", "service": "payments", "author": "Lena Ortiz", "day": 192,
     "message": "payments: reconciliation notes in the settlement docstring",
     "files": "src/payments/settlement.py", "additions": 15, "deletions": 3},
    {"sha": "0b7e4c9", "service": "analytics-worker", "author": "Ravi Shah", "day": 193,
     "message": "analytics-worker: log how many messages stay unflushed on exit",
     "files": "src/analytics/consumer.py", "additions": 8, "deletions": 2},
    {"sha": "d5836fe", "service": "storefront-web", "author": "Nina Kowalski", "day": 194,
     "message": "storefront-web: discount row hidden when there is no discount",
     "files": "src/components/CartSummary.tsx", "additions": 12, "deletions": 6},
    {"sha": "3ea061c", "service": "checkout", "author": "Lena Ortiz", "day": 195,
     "message": "checkout: audit trail on every refund action",
     "files": "src/checkout/refunds.py", "additions": 20, "deletions": 5},
    {"sha": "94b7f25", "service": "search", "author": "Mei Tanaka", "day": 196,
     "message": "search: cut v2.4.0",
     "files": "src/search/query.py", "additions": 2, "deletions": 2},
    {"sha": "6c0da81", "service": "inventory", "author": "Tom Becker", "day": 197,
     "message": "inventory: reject reserve calls for unknown SKUs early",
     "files": "src/main/java/com/novacart/inventory/ReservationService.java", "additions": 13, "deletions": 4},
    {"sha": "e836b04", "service": "catalog", "author": "Sam Whitfield", "day": 198,
     "message": "catalog: cut v1.5.0",
     "files": "src/catalog/models.py", "additions": 2, "deletions": 2},
    {"sha": "17fa5d6", "service": "api-gateway", "author": "Priya Nair", "day": 199,
     "message": "api-gateway: OPS-204 alert when in-flight connections exceed 5k",
     "files": "internal/proxy/pool.go", "additions": 21, "deletions": 3},
    {"sha": "b40e9c7", "service": "payments", "author": "Diego Ramos", "day": 200,
     "message": "payments: cut v2.2.0",
     "files": "src/payments/settings.py", "additions": 2, "deletions": 2},
    {"sha": "58d1af3", "service": "storefront-web", "author": "Jordan Blake", "day": 201,
     "message": "storefront-web: force-dynamic on the checkout route",
     "files": "src/app/checkout/page.tsx", "additions": 5, "deletions": 1},
    {"sha": "c9740eb", "service": "notifications", "author": "Priya Nair", "day": 202,
     "message": "notifications: jittered backoff to stop retry stampedes",
     "files": "src/notifications/queue.py", "additions": 13, "deletions": 6},
    {"sha": "2b05e18", "service": "analytics-worker", "author": "Nina Kowalski", "day": 203,
     "message": "analytics-worker: sort rollup rows for deterministic writes",
     "files": "src/analytics/aggregates.py", "additions": 9, "deletions": 4},
    {"sha": "70e3fdc", "service": "checkout", "author": "Nina Kowalski", "day": 204,
     "message": "checkout: reject carts over the line item cap with a typed error",
     "files": "src/checkout/cart.py", "additions": 14, "deletions": 6},
    {"sha": "e6152ba", "service": "media-service", "author": "Jordan Blake", "day": 205,
     "message": "media-service: X-Served-By header for edge debugging",
     "files": "src/media/assets.py", "additions": 7, "deletions": 2},
    {"sha": "4a8d039", "service": "search", "author": "Jordan Blake", "day": 206,
     "message": "search: benchmark harness for the ranking blend",
     "files": "tests/test_ranking.py", "additions": 26, "deletions": 3},
    {"sha": "d1cb576", "service": "api-gateway", "author": "Tom Becker", "day": 207,
     "message": "api-gateway: Retry-After on 429 responses",
     "files": "internal/middleware/ratelimit.go", "additions": 9, "deletions": 2},
    {"sha": "836f0e2", "service": "inventory", "author": "Ravi Shah", "day": 208,
     "message": "inventory: structured logging via slf4j placeholders",
     "files": "src/main/java/com/novacart/inventory/StockController.java", "additions": 18, "deletions": 12},
    {"sha": "0972ecb", "service": "payments", "author": "Lena Ortiz", "day": 209,
     "message": "payments: guard against zero-amount settlement batches",
     "files": "src/payments/settlement.py", "additions": 11, "deletions": 3},
    {"sha": "bf6a341", "service": "catalog", "author": "Ravi Shah", "day": 210,
     "message": "catalog: connection pool sizing notes",
     "files": "src/catalog/repository.py", "additions": 13, "deletions": 2},
    {"sha": "35e7c80", "service": "storefront-web", "author": "Mei Tanaka", "day": 211,
     "message": "storefront-web: empty-state copy for filtered grids",
     "files": "src/components/ProductGrid.tsx", "additions": 10, "deletions": 4},
    {"sha": "e0b48f6", "service": "checkout", "author": "Mei Tanaka", "day": 212,
     "message": "checkout: ENG-1990 stop double-charging on rapid resubmits",
     "files": "src/checkout/orchestrator.py,tests/test_idempotency.py", "additions": 31, "deletions": 12},
    {"sha": "7cd2019", "service": "notifications", "author": "Alex Osei", "day": 213,
     "message": "notifications: fail closed when a template is missing a file",
     "files": "src/notifications/templates.py", "additions": 15, "deletions": 5},
    {"sha": "9384bd7", "service": "search", "author": "Mei Tanaka", "day": 214,
     "message": "search: batch flush size raised to 500 documents",
     "files": "src/search/indexer.py", "additions": 6, "deletions": 4},
    {"sha": "1ea6f5c", "service": "analytics-worker", "author": "Ravi Shah", "day": 215,
     "message": "analytics-worker: cut v0.7.0",
     "files": "src/analytics/consumer.py", "additions": 2, "deletions": 2},
    {"sha": "c47b028", "service": "api-gateway", "author": "Priya Nair", "day": 216,
     "message": "api-gateway: per-upstream TLS material in config",
     "files": "internal/config/config.go", "additions": 42, "deletions": 8},
    {"sha": "6d0f8a4", "service": "payments", "author": "Diego Ramos", "day": 217,
     "message": "payments: bump libpayproc to 2.3.1",
     "files": "src/payments/capture.py", "additions": 3, "deletions": 3},
    {"sha": "b859ed1", "service": "media-service", "author": "Sam Whitfield", "day": 218,
     "message": "media-service: skip variants when the source is already smaller",
     "files": "src/media/transcode.py", "additions": 12, "deletions": 5},
    {"sha": "3f6c07e", "service": "inventory", "author": "Tom Becker", "day": 219,
     "message": "inventory: fail fast when the pool cannot hand out a connection",
     "files": "src/main/java/com/novacart/inventory/StockRepository.java", "additions": 16, "deletions": 6},
    {"sha": "a02de95", "service": "checkout", "author": "Lena Ortiz", "day": 220,
     "message": "checkout: cut v2.0.0",
     "files": "src/checkout/config.py", "additions": 2, "deletions": 2},
    {"sha": "58fb1d3", "service": "storefront-web", "author": "Nina Kowalski", "day": 221,
     "message": "storefront-web: extract computeTotals for testability",
     "files": "src/components/CartSummary.tsx", "additions": 27, "deletions": 19},
    {"sha": "d73e802", "service": "catalog", "author": "Sam Whitfield", "day": 222,
     "message": "catalog: price_single helper for the admin console",
     "files": "src/catalog/pricing.py", "additions": 14, "deletions": 2},
    {"sha": "9c15b6a", "service": "search", "author": "Jordan Blake", "day": 223,
     "message": "search: doc the segment boost contract",
     "files": "src/search/ranking.py", "additions": 11, "deletions": 2},
    {"sha": "40a7e6f", "service": "notifications", "author": "Priya Nair", "day": 224,
     "message": "notifications: bump redis client to 5.0.4",
     "files": "src/notifications/queue.py", "additions": 3, "deletions": 3},
    {"sha": "e51c983", "service": "analytics-worker", "author": "Nina Kowalski", "day": 225,
     "message": "analytics-worker: warehouse staging writer batches by minute",
     "files": "src/analytics/aggregates.py", "additions": 24, "deletions": 9},
    {"sha": "27b0da6", "service": "api-gateway", "author": "Tom Becker", "day": 226,
     "message": "api-gateway: mount /internal/debug for rollout inspection",
     "files": "internal/handlers/debug.go,internal/router/routes.go", "additions": 64, "deletions": 2},
    {"sha": "b6ea410", "service": "payments", "author": "Lena Ortiz", "day": 227,
     "message": "payments: cut v2.4.0",
     "files": "src/payments/settlement.py", "additions": 2, "deletions": 2},
    {"sha": "704f2ce", "service": "checkout", "author": "Nina Kowalski", "day": 228,
     "message": "checkout: describe() logs whether the partner key is set",
     "files": "src/checkout/config.py", "additions": 12, "deletions": 4},
    {"sha": "1c58ea9", "service": "inventory", "author": "Ravi Shah", "day": 229,
     "message": "inventory: hold ids prefixed for log greppability",
     "files": "src/main/java/com/novacart/inventory/ReservationService.java", "additions": 6, "deletions": 3},
    {"sha": "f9037b2", "service": "storefront-web", "author": "Jordan Blake", "day": 230,
     "message": "storefront-web: log cart load failures with the cart id",
     "files": "src/app/checkout/page.tsx", "additions": 9, "deletions": 3},
    {"sha": "8ba4e07", "service": "media-service", "author": "Jordan Blake", "day": 231,
     "message": "media-service: cut v0.6.0",
     "files": "src/media/assets.py", "additions": 2, "deletions": 2},
    {"sha": "d2e6153", "service": "search", "author": "Mei Tanaka", "day": 232,
     "message": "search: retry a failed flush without dropping the buffer",
     "files": "src/search/indexer.py", "additions": 18, "deletions": 7},
    {"sha": "60c19fa", "service": "catalog", "author": "Ravi Shah", "day": 233,
     "message": "catalog: chore: tidy imports across the package",
     "files": "src/catalog/repository.py,src/catalog/models.py", "additions": 12, "deletions": 18},
    {"sha": "a4157be", "service": "api-gateway", "author": "Priya Nair", "day": 234,
     "message": "api-gateway: cut v4.6.0",
     "files": "internal/config/config.go", "additions": 3, "deletions": 3},
    {"sha": "7e39c05", "service": "payments", "author": "Diego Ramos", "day": 235,
     "message": "payments: mock libpayproc in the capture tests",
     "files": "tests/test_capture_retries.py", "additions": 22, "deletions": 11},
    {"sha": "cf8b230", "service": "notifications", "author": "Alex Osei", "day": 236,
     "message": "notifications: honour provider 429s before retrying",
     "files": "src/notifications/sender.py", "additions": 17, "deletions": 6},
    {"sha": "39d604e", "service": "analytics-worker", "author": "Ravi Shah", "day": 237,
     "message": "analytics-worker: OPS-241 dashboards for consumer lag",
     "files": "src/analytics/consumer.py", "additions": 14, "deletions": 3},
    {"sha": "5b7ea82", "service": "checkout", "author": "Mei Tanaka", "day": 238,
     "message": "checkout: quarantine flake watch on test_idempotency",
     "files": "tests/test_idempotency.py", "additions": 8, "deletions": 2},
    {"sha": "e1408cd", "service": "storefront-web", "author": "Mei Tanaka", "day": 239,
     "message": "storefront-web: cut v3.0.0",
     "files": "src/lib/api-client.ts", "additions": 2, "deletions": 2},
    {"sha": "94ec617", "service": "inventory", "author": "Tom Becker", "day": 240,
     "message": "inventory: expose pool metrics on /actuator",
     "files": "src/main/java/com/novacart/inventory/StockRepository.java", "additions": 19, "deletions": 4},
    {"sha": "0d3ba58", "service": "search", "author": "Jordan Blake", "day": 241,
     "message": "search: ignore segment affinity for anonymous sessions",
     "files": "src/search/ranking.py,tests/test_ranking.py", "additions": 17, "deletions": 8},
    {"sha": "b52907f", "service": "payments", "author": "Lena Ortiz", "day": 242,
     "message": "payments: settle in merchant id order for reproducible runs",
     "files": "src/payments/settlement.py", "additions": 7, "deletions": 4},
    {"sha": "6ac8de1", "service": "catalog", "author": "Sam Whitfield", "day": 243,
     "message": "catalog: effective price prefers sale when it is lower",
     "files": "src/catalog/models.py", "additions": 13, "deletions": 5},
    {"sha": "f70e2b4", "service": "api-gateway", "author": "Tom Becker", "day": 244,
     "message": "api-gateway: include goroutine count in the debug dump",
     "files": "internal/handlers/debug.go", "additions": 8, "deletions": 2},
    {"sha": "285cb90", "service": "notifications", "author": "Priya Nair", "day": 245,
     "message": "notifications: cut v1.4.0",
     "files": "src/notifications/queue.py", "additions": 2, "deletions": 2},
    {"sha": "c3f1a76", "service": "storefront-web", "author": "Nina Kowalski", "day": 246,
     "message": "storefront-web: compact variant of the cart summary for mobile",
     "files": "src/components/CartSummary.tsx", "additions": 21, "deletions": 7},
    {"sha": "40b9e53", "service": "analytics-worker", "author": "Nina Kowalski", "day": 247,
     "message": "analytics-worker: bump warehouse driver to 3.9.1",
     "files": "src/analytics/aggregates.py", "additions": 3, "deletions": 3},
    {"sha": "d867fa2", "service": "checkout", "author": "Lena Ortiz", "day": 248,
     "message": "checkout: settled refunds keep an audit row",
     "files": "db/migrations/0031_refund_ledger.sql,src/checkout/refunds.py", "additions": 26, "deletions": 9},
    {"sha": "1fb5074", "service": "media-service", "author": "Sam Whitfield", "day": 249,
     "message": "media-service: guard against unreadable image sources",
     "files": "src/media/transcode.py", "additions": 14, "deletions": 4},
    {"sha": "9e6d38b", "service": "inventory", "author": "Ravi Shah", "day": 250,
     "message": "inventory: cut v1.3.0",
     "files": "src/main/java/com/novacart/inventory/StockController.java", "additions": 3, "deletions": 3},
    {"sha": "72a04ef", "service": "search", "author": "Mei Tanaka", "day": 251,
     "message": "search: cache hit/miss counters for the dashboard",
     "files": "src/search/query.py", "additions": 16, "deletions": 4},
    {"sha": "b19c805", "service": "payments", "author": "Diego Ramos", "day": 252,
     "message": "payments: docs on the capture-then-receipt contract",
     "files": "src/payments/capture.py", "additions": 16, "deletions": 3},
    {"sha": "e4823da", "service": "api-gateway", "author": "Priya Nair", "day": 253,
     "message": "api-gateway: env override for the request timeout",
     "files": "internal/config/config.go", "additions": 11, "deletions": 3},
    {"sha": "50cd671", "service": "catalog", "author": "Ravi Shah", "day": 254,
     "message": "catalog: cut v1.7.0",
     "files": "src/catalog/pricing.py", "additions": 2, "deletions": 2},
    {"sha": "af2e79c", "service": "storefront-web", "author": "Jordan Blake", "day": 255,
     "message": "storefront-web: exponential backoff between fetch retries",
     "files": "src/lib/api-client.ts", "additions": 13, "deletions": 5},
    {"sha": "836be14", "service": "notifications", "author": "Alex Osei", "day": 256,
     "message": "notifications: pool name derived from smtp_pool config",
     "files": "src/notifications/sender.py", "additions": 8, "deletions": 3},
    {"sha": "c065d29", "service": "checkout", "author": "Nina Kowalski", "day": 257,
     "message": "checkout: shipping cost added after tax, not before",
     "files": "src/checkout/cart.py", "additions": 12, "deletions": 8},
    {"sha": "3d7f0a6", "service": "analytics-worker", "author": "Ravi Shah", "day": 258,
     "message": "analytics-worker: queue name configurable per environment",
     "files": "src/analytics/consumer.py", "additions": 9, "deletions": 4},
    {"sha": "7bd4e91", "service": "inventory", "author": "Tom Becker", "day": 259,
     "message": "inventory: close the datasource on shutdown",
     "files": "src/main/java/com/novacart/inventory/StockRepository.java", "additions": 8, "deletions": 1},
    {"sha": "e137c40", "service": "search", "author": "Jordan Blake", "day": 260,
     "message": "search: cut v2.9.0",
     "files": "src/search/ranking.py", "additions": 2, "deletions": 2},

    # ------------------------------------------- days 261-350: platform + pilots
    {"sha": "5a0eb37", "service": "checkout", "author": "Lena Ortiz", "day": 261,
     "message": "checkout: instant_refunds flag scaffolding, disabled everywhere",
     "files": "src/checkout/refunds.py,src/checkout/config.py", "additions": 38, "deletions": 6},
    {"sha": "c8f4126", "service": "storefront-web", "author": "Nina Kowalski", "day": 262,
     "message": "storefront-web: money formatting helper shared by cart and grid",
     "files": "src/components/CartSummary.tsx,src/components/ProductGrid.tsx", "additions": 24, "deletions": 21},
    {"sha": "907dbe5", "service": "payments", "author": "Diego Ramos", "day": 263,
     "message": "payments: raise notifications timeout to 30s for the EU region",
     "files": "src/payments/settings.py", "additions": 4, "deletions": 4},
    {"sha": "34e6b8a", "service": "api-gateway", "author": "Tom Becker", "day": 264,
     "message": "api-gateway: keep /internal/debug out of the public route table docs",
     "files": "internal/router/routes.go", "additions": 5, "deletions": 2},
    {"sha": "b7d1e60", "service": "search", "author": "Mei Tanaka", "day": 265,
     "message": "search: short-circuit empty search terms before hitting the index",
     "files": "src/search/query.py", "additions": 13, "deletions": 4},
    {"sha": "e05c2f9", "service": "catalog", "author": "Sam Whitfield", "day": 266,
     "message": "catalog: fetch_prices_bulk returns a dict keyed by product id",
     "files": "src/catalog/repository.py", "additions": 15, "deletions": 9},
    {"sha": "16fa4b8", "service": "notifications", "author": "Priya Nair", "day": 267,
     "message": "notifications: correlation ids threaded through the queue",
     "files": "src/notifications/queue.py,src/notifications/sender.py", "additions": 22, "deletions": 8},
    {"sha": "d9036ce", "service": "inventory", "author": "Ravi Shah", "day": 268,
     "message": "inventory: bump spring boot to 3.2.5",
     "files": "src/main/java/com/novacart/inventory/StockController.java", "additions": 5, "deletions": 5},
    {"sha": "72be015", "service": "analytics-worker", "author": "Nina Kowalski", "day": 269,
     "message": "analytics-worker: refund_issued added to the known event set",
     "files": "src/analytics/aggregates.py", "additions": 6, "deletions": 2},
    {"sha": "af38d64", "service": "media-service", "author": "Jordan Blake", "day": 270,
     "message": "media-service: mimetype detection from the object key",
     "files": "src/media/assets.py", "additions": 11, "deletions": 4},
    {"sha": "0c751ea", "service": "checkout", "author": "Mei Tanaka", "day": 271,
     "message": "checkout: split submit tests from refund tests",
     "files": "tests/test_idempotency.py", "additions": 19, "deletions": 14},
    {"sha": "e4b8907", "service": "payments", "author": "Lena Ortiz", "day": 272,
     "message": "payments: cut v2.6.0",
     "files": "src/payments/settlement.py", "additions": 2, "deletions": 2},
    {"sha": "63cd0a2", "service": "api-gateway", "author": "Priya Nair", "day": 273,
     "message": "api-gateway: close idle upstream connections on release",
     "files": "internal/proxy/pool.go", "additions": 17, "deletions": 5},
    {"sha": "8f2a071", "service": "search", "author": "Jordan Blake", "day": 274,
     "message": "search: expose ranking components in debug responses",
     "files": "src/search/ranking.py", "additions": 13, "deletions": 4},
    {"sha": "d40ba69", "service": "storefront-web", "author": "Mei Tanaka", "day": 275,
     "message": "storefront-web: prefetch the checkout route from the cart page",
     "files": "src/app/checkout/page.tsx", "additions": 8, "deletions": 2},
    {"sha": "1b96e2f", "service": "catalog", "author": "Ravi Shah", "day": 276,
     "message": "catalog: vacuum settings note for the price table",
     "files": "db/migrations/0012_product_price_tier_index.sql", "additions": 5, "deletions": 1},
    {"sha": "cea7304", "service": "notifications", "author": "Alex Osei", "day": 277,
     "message": "notifications: autoescape on by default in the Jinja env",
     "files": "src/notifications/templates.py", "additions": 6, "deletions": 2},
    {"sha": "47f0d81", "service": "inventory", "author": "Tom Becker", "day": 278,
     "message": "inventory: separate read and write paths in the repository",
     "files": "src/main/java/com/novacart/inventory/StockRepository.java", "additions": 41, "deletions": 26},
    {"sha": "b3e52ca", "service": "analytics-worker", "author": "Ravi Shah", "day": 279,
     "message": "analytics-worker: cut v0.9.0",
     "files": "src/analytics/consumer.py", "additions": 2, "deletions": 2},
    {"sha": "95d7016", "service": "checkout", "author": "Nina Kowalski", "day": 280,
     "message": "checkout: merge duplicate SKUs when adding to cart",
     "files": "src/checkout/cart.py", "additions": 17, "deletions": 6},
    {"sha": "f0a4e68", "service": "payments", "author": "Diego Ramos", "day": 281,
     "message": "payments: SEC-812 stop logging the auth token on decline",
     "files": "src/payments/capture.py", "additions": 7, "deletions": 5},
    {"sha": "2c8b53d", "service": "api-gateway", "author": "Tom Becker", "day": 282,
     "message": "api-gateway: v2 orders accepts PATCH",
     "files": "internal/router/routes.go", "additions": 4, "deletions": 2},
    {"sha": "8e17ba0", "service": "media-service", "author": "Sam Whitfield", "day": 283,
     "message": "media-service: record the source etag on every variant",
     "files": "src/media/transcode.py", "additions": 12, "deletions": 5},
    {"sha": "6da039e", "service": "search", "author": "Mei Tanaka", "day": 284,
     "message": "search: normalize terms before hashing the cache key",
     "files": "src/search/query.py", "additions": 9, "deletions": 4},
    {"sha": "b41c07f", "service": "storefront-web", "author": "Jordan Blake", "day": 285,
     "message": "storefront-web: bump react to 18.3.1",
     "files": "src/lib/api-client.ts", "additions": 4, "deletions": 4},
    {"sha": "3079eac", "service": "catalog", "author": "Sam Whitfield", "day": 286,
     "message": "catalog: cut v1.8.0",
     "files": "src/catalog/models.py", "additions": 2, "deletions": 2},
    {"sha": "de6285b", "service": "notifications", "author": "Priya Nair", "day": 287,
     "message": "notifications: cap backoff at 30 seconds",
     "files": "src/notifications/queue.py", "additions": 5, "deletions": 3},
    {"sha": "70fb4c1", "service": "inventory", "author": "Ravi Shah", "day": 288,
     "message": "inventory: reservation lines recorded inside the same transaction",
     "files": "src/main/java/com/novacart/inventory/ReservationService.java", "additions": 23, "deletions": 11},
    {"sha": "c92d80a", "service": "checkout", "author": "Lena Ortiz", "day": 289,
     "message": "checkout: refund store lookups keyed by order id",
     "files": "src/checkout/refunds.py", "additions": 16, "deletions": 7},
    {"sha": "05a7e34", "service": "analytics-worker", "author": "Nina Kowalski", "day": 290,
     "message": "analytics-worker: minute buckets computed in UTC",
     "files": "src/analytics/aggregates.py", "additions": 11, "deletions": 6},
    {"sha": "e6103fb", "service": "payments", "author": "Lena Ortiz", "day": 291,
     "message": "payments: chore: drop the unused settlement dry-run flag",
     "files": "src/payments/settlement.py", "additions": 3, "deletions": 21},
    {"sha": "4b8f507", "service": "api-gateway", "author": "Priya Nair", "day": 292,
     "message": "api-gateway: cut v4.9.0",
     "files": "internal/config/config.go", "additions": 3, "deletions": 3},
    {"sha": "9ca6e21", "service": "search", "author": "Jordan Blake", "day": 293,
     "message": "search: ranking regression fixtures from production samples",
     "files": "tests/test_ranking.py", "additions": 31, "deletions": 5},
    {"sha": "17edb08", "service": "storefront-web", "author": "Nina Kowalski", "day": 294,
     "message": "storefront-web: alert role on the cart error state",
     "files": "src/components/CartSummary.tsx", "additions": 6, "deletions": 2},
    {"sha": "d3592af", "service": "media-service", "author": "Jordan Blake", "day": 295,
     "message": "media-service: cut v0.8.0",
     "files": "src/media/assets.py", "additions": 2, "deletions": 2},
    {"sha": "8407c6e", "service": "checkout", "author": "Mei Tanaka", "day": 296,
     "message": "checkout: ENG-2050 keep hold release idempotent on retry",
     "files": "src/checkout/orchestrator.py", "additions": 18, "deletions": 7},
    {"sha": "62be9d1", "service": "catalog", "author": "Ravi Shah", "day": 297,
     "message": "catalog: explain-analyze notes for the listing query",
     "files": "src/catalog/repository.py", "additions": 16, "deletions": 2},
    {"sha": "af0d715", "service": "inventory", "author": "Tom Becker", "day": 298,
     "message": "inventory: cut v1.6.0",
     "files": "src/main/java/com/novacart/inventory/StockRepository.java", "additions": 3, "deletions": 3},
    {"sha": "50e2c93", "service": "notifications", "author": "Alex Osei", "day": 299,
     "message": "notifications: SMS adapter split out of sender",
     "files": "src/notifications/sender.py", "additions": 27, "deletions": 34},
    {"sha": "b8a1d46", "service": "payments", "author": "Diego Ramos", "day": 300,
     "message": "payments: cut v2.6.5",
     "files": "src/payments/settings.py", "additions": 2, "deletions": 2},
    {"sha": "3e7fb52", "service": "storefront-web", "author": "Mei Tanaka", "day": 301,
     "message": "storefront-web: skeleton grid while products stream in",
     "files": "src/components/ProductGrid.tsx", "additions": 22, "deletions": 6},
    {"sha": "c40968d", "service": "analytics-worker", "author": "Ravi Shah", "day": 302,
     "message": "analytics-worker: consumer inactivity timeout so shutdown is prompt",
     "files": "src/analytics/consumer.py", "additions": 10, "deletions": 5},
    {"sha": "1d605ea", "service": "search", "author": "Mei Tanaka", "day": 303,
     "message": "search: index shard count read from config",
     "files": "src/search/indexer.py,src/search/query.py", "additions": 14, "deletions": 8},
    {"sha": "76fb381", "service": "api-gateway", "author": "Tom Becker", "day": 304,
     "message": "api-gateway: reject empty upstream names in the pool",
     "files": "internal/proxy/pool.go", "additions": 9, "deletions": 2},
    {"sha": "e928c07", "service": "checkout", "author": "Nina Kowalski", "day": 305,
     "message": "checkout: retryable status set shared with the partner client",
     "files": "src/checkout/config.py", "additions": 8, "deletions": 3},
    {"sha": "a05be64", "service": "catalog", "author": "Sam Whitfield", "day": 306,
     "message": "catalog: revert 'inline price lookup in the listing query'",
     "files": "src/catalog/pricing.py,src/catalog/repository.py", "additions": 21, "deletions": 47},
    {"sha": "9b3d017", "service": "inventory", "author": "Ravi Shah", "day": 307,
     "message": "inventory: batch endpoint returns 413 over the cap",
     "files": "src/main/java/com/novacart/inventory/StockController.java", "additions": 9, "deletions": 4},
    {"sha": "f1ca285", "service": "notifications", "author": "Priya Nair", "day": 308,
     "message": "notifications: cut v1.4.6",
     "files": "src/notifications/queue.py", "additions": 2, "deletions": 2},
    {"sha": "27e50bd", "service": "payments", "author": "Lena Ortiz", "day": 309,
     "message": "payments: settlement metrics per merchant",
     "files": "src/payments/settlement.py", "additions": 19, "deletions": 5},
    {"sha": "b06e4f8", "service": "media-service", "author": "Sam Whitfield", "day": 310,
     "message": "media-service: transcode returns the list of written keys",
     "files": "src/media/transcode.py", "additions": 10, "deletions": 4},
    {"sha": "48f7013", "service": "storefront-web", "author": "Jordan Blake", "day": 311,
     "message": "storefront-web: cut v3.1.0",
     "files": "src/lib/api-client.ts", "additions": 2, "deletions": 2},
    {"sha": "d5b029c", "service": "search", "author": "Jordan Blake", "day": 312,
     "message": "search: OPS-288 alert on cache hit rate below 60%",
     "files": "src/search/query.py", "additions": 15, "deletions": 3},
    {"sha": "70a3ce6", "service": "checkout", "author": "Lena Ortiz", "day": 313,
     "message": "checkout: refund worker claims intents in FIFO order",
     "files": "src/checkout/refunds.py", "additions": 14, "deletions": 6},
    {"sha": "e2fc849", "service": "api-gateway", "author": "Priya Nair", "day": 314,
     "message": "api-gateway: shared transport reused across all routes",
     "files": "internal/proxy/pool.go", "additions": 33, "deletions": 18},
    {"sha": "8c604b1", "service": "analytics-worker", "author": "Nina Kowalski", "day": 315,
     "message": "analytics-worker: staging table name configurable",
     "files": "src/analytics/aggregates.py", "additions": 7, "deletions": 3},
    {"sha": "31de07a", "service": "inventory", "author": "Tom Becker", "day": 316,
     "message": "inventory: log connection return failures instead of swallowing them",
     "files": "src/main/java/com/novacart/inventory/ReservationService.java", "additions": 12, "deletions": 5},
    {"sha": "b7495ea", "service": "catalog", "author": "Ravi Shah", "day": 317,
     "message": "catalog: cut v1.9.0",
     "files": "src/catalog/repository.py", "additions": 2, "deletions": 2},
    {"sha": "5f18d20", "service": "notifications", "author": "Alex Osei", "day": 318,
     "message": "notifications: doc the strict-undefined rendering choice",
     "files": "src/notifications/templates.py", "additions": 13, "deletions": 2},
    {"sha": "c937e05", "service": "payments", "author": "Diego Ramos", "day": 319,
     "message": "payments: assert receipt retries in the unit suite",
     "files": "tests/test_capture_retries.py", "additions": 24, "deletions": 6},
    {"sha": "0a6bf34", "service": "storefront-web", "author": "Nina Kowalski", "day": 320,
     "message": "storefront-web: keyboard focus ring on the checkout CTA",
     "files": "src/components/CartSummary.tsx", "additions": 9, "deletions": 3},
    {"sha": "e470c19", "service": "search", "author": "Mei Tanaka", "day": 321,
     "message": "search: cut v3.0.0",
     "files": "src/search/query.py", "additions": 2, "deletions": 2},
    {"sha": "24bd7f6", "service": "checkout", "author": "Mei Tanaka", "day": 322,
     "message": "checkout: pytest markers separating unit and integration",
     "files": "tests/test_idempotency.py", "additions": 11, "deletions": 4},
    {"sha": "9e05a83", "service": "api-gateway", "author": "Tom Becker", "day": 323,
     "message": "api-gateway: traffic weights refreshed from the control plane",
     "files": "internal/router/routes.go,internal/config/config.go", "additions": 37, "deletions": 11},
    {"sha": "f3068ce", "service": "media-service", "author": "Jordan Blake", "day": 324,
     "message": "media-service: origin bucket name read from config",
     "files": "src/media/assets.py", "additions": 8, "deletions": 4},
    {"sha": "b1d5027", "service": "inventory", "author": "Ravi Shah", "day": 325,
     "message": "inventory: hold TTL raised to 20 minutes for slow payment flows",
     "files": "src/main/java/com/novacart/inventory/ReservationService.java", "additions": 5, "deletions": 5},
    {"sha": "5807ade", "service": "analytics-worker", "author": "Ravi Shah", "day": 326,
     "message": "analytics-worker: cut v1.0.0",
     "files": "src/analytics/consumer.py", "additions": 2, "deletions": 2},
    {"sha": "cd108b6", "service": "catalog", "author": "Sam Whitfield", "day": 327,
     "message": "catalog: skip products with no price row instead of returning nulls",
     "files": "src/catalog/pricing.py", "additions": 15, "deletions": 7},
    {"sha": "7ea3c48", "service": "payments", "author": "Lena Ortiz", "day": 328,
     "message": "payments: nightly settlement moved to 02:15 UTC",
     "files": "src/payments/settlement.py", "additions": 6, "deletions": 4},
    {"sha": "e5c9016", "service": "notifications", "author": "Priya Nair", "day": 329,
     "message": "notifications: chore: prune unused template helpers",
     "files": "src/notifications/templates.py", "additions": 2, "deletions": 19},
    {"sha": "40fbd92", "service": "storefront-web", "author": "Mei Tanaka", "day": 330,
     "message": "storefront-web: product card badges cover new arrivals",
     "files": "src/components/ProductGrid.tsx", "additions": 13, "deletions": 5},
    {"sha": "83a0e17", "service": "checkout", "author": "Nina Kowalski", "day": 331,
     "message": "checkout: cut v2.3.0",
     "files": "src/checkout/config.py", "additions": 2, "deletions": 2},
    {"sha": "d6b74fc", "service": "search", "author": "Jordan Blake", "day": 332,
     "message": "search: drop the unused geo boost helper",
     "files": "src/search/ranking.py", "additions": 1, "deletions": 23},
    {"sha": "1c58f03", "service": "api-gateway", "author": "Priya Nair", "day": 333,
     "message": "api-gateway: cut v5.0.0",
     "files": "internal/config/config.go", "additions": 3, "deletions": 3},
    {"sha": "b0e2d75", "service": "inventory", "author": "Tom Becker", "day": 334,
     "message": "inventory: stock controller returns typed error bodies",
     "files": "src/main/java/com/novacart/inventory/StockController.java", "additions": 16, "deletions": 8},
    {"sha": "947fb63", "service": "payments", "author": "Diego Ramos", "day": 335,
     "message": "payments: log correlation ids on successful receipts too",
     "files": "src/payments/notify_client.py", "additions": 7, "deletions": 3},
    {"sha": "3ed081a", "service": "analytics-worker", "author": "Nina Kowalski", "day": 336,
     "message": "analytics-worker: docs on the rollup schema",
     "files": "src/analytics/aggregates.py", "additions": 18, "deletions": 2},
    {"sha": "c62a904", "service": "catalog", "author": "Sam Whitfield", "day": 337,
     "message": "catalog: batch pricing enabled in staging for parity testing",
     "files": "src/catalog/pricing.py", "additions": 12, "deletions": 6},
    {"sha": "78be150", "service": "media-service", "author": "Sam Whitfield", "day": 338,
     "message": "media-service: cut v1.0.0",
     "files": "src/media/transcode.py", "additions": 2, "deletions": 2},
    {"sha": "e0f4b29", "service": "storefront-web", "author": "Jordan Blake", "day": 339,
     "message": "storefront-web: surface partial cart failures without blanking the page",
     "files": "src/app/checkout/page.tsx", "additions": 17, "deletions": 6},
    {"sha": "5b90d1e", "service": "checkout", "author": "Lena Ortiz", "day": 340,
     "message": "checkout: refund ledger status constraint",
     "files": "db/migrations/0031_refund_ledger.sql", "additions": 8, "deletions": 2},
    {"sha": "a4715ce", "service": "search", "author": "Mei Tanaka", "day": 341,
     "message": "search: cut v3.0.4",
     "files": "src/search/indexer.py", "additions": 2, "deletions": 2},
    {"sha": "20cd8b7", "service": "api-gateway", "author": "Tom Becker", "day": 342,
     "message": "api-gateway: /v1/orders marked as the default order route",
     "files": "internal/router/routes.go", "additions": 5, "deletions": 3},
    {"sha": "e83f605", "service": "notifications", "author": "Alex Osei", "day": 343,
     "message": "notifications: cut v1.4.8",
     "files": "src/notifications/sender.py", "additions": 2, "deletions": 2},
    {"sha": "97b0e5d", "service": "inventory", "author": "Ravi Shah", "day": 344,
     "message": "inventory: pgbouncer in front of the stock database",
     "files": "src/main/java/com/novacart/inventory/StockRepository.java", "additions": 21, "deletions": 9},
    {"sha": "f60a3d8", "service": "payments", "author": "Lena Ortiz", "day": 345,
     "message": "payments: cut v2.7.0",
     "files": "src/payments/settlement.py", "additions": 2, "deletions": 2},
    {"sha": "3b2ce07", "service": "storefront-web", "author": "Nina Kowalski", "day": 346,
     "message": "storefront-web: cut v3.2.0",
     "files": "src/components/CartSummary.tsx", "additions": 2, "deletions": 2},
    {"sha": "d5e7014", "service": "analytics-worker", "author": "Ravi Shah", "day": 347,
     "message": "analytics-worker: backlog grew 4x after the clickstream migration",
     "files": "src/analytics/consumer.py", "additions": 13, "deletions": 6},
    {"sha": "6ad91cb", "service": "catalog", "author": "Ravi Shah", "day": 348,
     "message": "catalog: cut v1.9.2",
     "files": "src/catalog/models.py", "additions": 2, "deletions": 2},
    {"sha": "b4708ea", "service": "checkout", "author": "Mei Tanaka", "day": 349,
     "message": "checkout: integration suite sharded across four CI workers",
     "files": "tests/test_idempotency.py", "additions": 14, "deletions": 5},
    {"sha": "029ecf7", "service": "search", "author": "Jordan Blake", "day": 350,
     "message": "search: docs: how to interpret ranking components",
     "files": "src/search/ranking.py", "additions": 21, "deletions": 3},

    # ---------------------------------------- days 351-420: the regressions land
    {"sha": "e17c6b0", "service": "media-service", "author": "Jordan Blake", "day": 352,
     "message": "media-service: CDN vendor migration, dual-write signed URLs",
     "files": "src/media/assets.py", "additions": 34, "deletions": 12},
    {"sha": "84fa1d9", "service": "inventory", "author": "Tom Becker", "day": 353,
     "message": "inventory: reservation sweeper runs every minute",
     "files": "src/main/java/com/novacart/inventory/ReservationService.java", "additions": 17, "deletions": 6},
    {"sha": "5c093ba", "service": "api-gateway", "author": "Priya Nair", "day": 354,
     "message": "api-gateway: per-route TLS material plumbed into config",
     "files": "internal/config/config.go", "additions": 46, "deletions": 9},
    {"sha": "b70e438", "service": "payments", "author": "Diego Ramos", "day": 355,
     "message": "payments: receipt latency is now the top contributor to capture p99",
     "files": "src/payments/notify_client.py", "additions": 11, "deletions": 4},
    {"sha": "31ea065", "service": "storefront-web", "author": "Mei Tanaka", "day": 356,
     "message": "storefront-web: cut v3.2.4",
     "files": "src/lib/api-client.ts", "additions": 2, "deletions": 2},
    {"sha": "cf8207e", "service": "notifications", "author": "Priya Nair", "day": 357,
     "message": "notifications: session refactor, one provider session per worker",
     "files": "src/notifications/sender.py", "additions": 29, "deletions": 18},
    {"sha": "6b3d5a1", "service": "analytics-worker", "author": "Ravi Shah", "day": 358,
     "message": "analytics-worker: consumers stalling behind slow warehouse flushes",
     "files": "src/analytics/consumer.py", "additions": 16, "deletions": 7},
    {"sha": "0e4c97b", "service": "catalog", "author": "Sam Whitfield", "day": 359,
     "message": "catalog: parity harness comparing batched and per-row pricing",
     "files": "src/catalog/pricing.py", "additions": 31, "deletions": 8},
    {"sha": "d9a5f30", "service": "search", "author": "Mei Tanaka", "day": 360,
     "message": "search: index reshard from 4 to 8 shards, staged",
     "files": "src/search/indexer.py,src/search/query.py", "additions": 27, "deletions": 13},
    {"sha": "72fe018", "service": "checkout", "author": "Nina Kowalski", "day": 361,
     "message": "checkout: partner settlement client for the merchant pilot",
     "files": "src/checkout/config.py", "additions": 26, "deletions": 4},
    {"sha": "a3610eb", "service": "storefront-web", "author": "Jordan Blake", "day": 362,
     "message": "storefront-web: lazy-load below-the-fold product imagery",
     "files": "src/components/ProductGrid.tsx", "additions": 12, "deletions": 5},
    {"sha": "5d84fc2", "service": "payments", "author": "Lena Ortiz", "day": 363,
     "message": "payments: settlement receipts reconciled against the ledger export",
     "files": "src/payments/settlement.py", "additions": 22, "deletions": 8},
    {"sha": "e096b47", "service": "inventory", "author": "Ravi Shah", "day": 364,
     "message": "inventory: connection-wait timings added to the slow-query log",
     "files": "src/main/java/com/novacart/inventory/StockRepository.java", "additions": 14, "deletions": 4},
    {"sha": "b52ea08", "service": "api-gateway", "author": "Tom Becker", "day": 365,
     "message": "api-gateway: cut v5.0.9",
     "files": "internal/config/config.go", "additions": 3, "deletions": 3},
    {"sha": "1f7c930", "service": "notifications", "author": "Alex Osei", "day": 366,
     "message": "notifications: delivery log retention trimmed to 90 days",
     "files": "src/notifications/queue.py", "additions": 9, "deletions": 3},
    {"sha": "8ba0e46", "service": "analytics-worker", "author": "Nina Kowalski", "day": 367,
     "message": "analytics-worker: revenue rollups exclude refunded orders",
     "files": "src/analytics/aggregates.py", "additions": 18, "deletions": 6},
    {"sha": "3ce7d81", "service": "inventory", "author": "Tom Becker", "day": 368,
     "message": "inventory: pin the stock pool to 5 connections after the pgbouncer move",
     "files": "src/main/java/com/novacart/inventory/StockRepository.java", "additions": 9, "deletions": 7},
    {"sha": "cb4501f", "service": "search", "author": "Jordan Blake", "day": 369,
     "message": "search: relevance weight nudged to 0.55 after the A/B readout",
     "files": "src/search/ranking.py", "additions": 5, "deletions": 5},
    {"sha": "70d3e6a", "service": "checkout", "author": "Mei Tanaka", "day": 370,
     "message": "checkout: refund fixtures for the instant path",
     "files": "tests/test_idempotency.py", "additions": 16, "deletions": 3},
    {"sha": "e8f10c5", "service": "api-gateway", "author": "Tom Becker", "day": 371,
     "message": "api-gateway: mount /internal/debug ahead of the auth chain so rollout checks work",
     "files": "internal/handlers/debug.go,internal/router/routes.go", "additions": 23, "deletions": 9},
    {"sha": "45b9027", "service": "payments", "author": "Diego Ramos", "day": 372,
     "message": "payments: split notify_client tests from capture tests",
     "files": "tests/test_capture_retries.py", "additions": 19, "deletions": 12},
    {"sha": "d0e738b", "service": "storefront-web", "author": "Nina Kowalski", "day": 373,
     "message": "storefront-web: cart panel handles a missing tax rate",
     "files": "src/components/CartSummary.tsx", "additions": 11, "deletions": 4},
    {"sha": "9741ac6", "service": "catalog", "author": "Ravi Shah", "day": 374,
     "message": "catalog: reindex price table after the tier backfill",
     "files": "db/migrations/0012_product_price_tier_index.sql", "additions": 7, "deletions": 2},
    {"sha": "2b6ce03", "service": "media-service", "author": "Jordan Blake", "day": 375,
     "message": "media-service: signed URLs from the new edge 404 for a slice of traffic",
     "files": "src/media/assets.py", "additions": 14, "deletions": 6},
    {"sha": "f38b0d7", "service": "media-service", "author": "Jordan Blake", "day": 376,
     "message": "media-service: serve reads from origin while the CDN migration settles",
     "files": "src/media/assets.py", "additions": 8, "deletions": 11},
    {"sha": "c5107ea", "service": "inventory", "author": "Ravi Shah", "day": 377,
     "message": "inventory: cut v2.0.0",
     "files": "src/main/java/com/novacart/inventory/StockController.java", "additions": 3, "deletions": 3},
    {"sha": "6e29d40", "service": "search", "author": "Mei Tanaka", "day": 378,
     "message": "search: reshard doubled write amplification on the cache cluster",
     "files": "src/search/query.py", "additions": 12, "deletions": 5},
    {"sha": "80fa4b1", "service": "notifications", "author": "Priya Nair", "day": 379,
     "message": "notifications: cut v1.4.8-1",
     "files": "src/notifications/templates.py", "additions": 2, "deletions": 2},
    {"sha": "13ed82c", "service": "analytics-worker", "author": "Ravi Shah", "day": 380,
     "message": "analytics-worker: measure prefetch impact on consumer throughput",
     "files": "src/analytics/consumer.py", "additions": 15, "deletions": 4},
    {"sha": "a7c0be9", "service": "analytics-worker", "author": "Ravi Shah", "day": 381,
     "message": "analytics-worker: remove the prefetch ceiling so delivery never stalls",
     "files": "src/analytics/consumer.py", "additions": 7, "deletions": 9},
    {"sha": "e6430fd", "service": "checkout", "author": "Lena Ortiz", "day": 382,
     "message": "checkout: refund store returns None for orders without a refund row",
     "files": "src/checkout/refunds.py", "additions": 13, "deletions": 6},
    {"sha": "5fb1c07", "service": "storefront-web", "author": "Mei Tanaka", "day": 383,
     "message": "storefront-web: bump next to 14.2.3",
     "files": "src/app/checkout/page.tsx", "additions": 5, "deletions": 5},
    {"sha": "b0947ce", "service": "payments", "author": "Lena Ortiz", "day": 384,
     "message": "payments: settlement batch retries capped at one pass per night",
     "files": "src/payments/settlement.py", "additions": 11, "deletions": 7},
    {"sha": "27ca5e8", "service": "catalog", "author": "Sam Whitfield", "day": 385,
     "message": "catalog: parity harness found a rounding gap in batched pricing",
     "files": "src/catalog/pricing.py", "additions": 14, "deletions": 6},
    {"sha": "d1730be", "service": "notifications", "author": "Alex Osei", "day": 386,
     "message": "notifications: simplify the provider call now that the session owns config",
     "files": "src/notifications/sender.py", "additions": 6, "deletions": 10},
    {"sha": "9e5407a", "service": "api-gateway", "author": "Priya Nair", "day": 387,
     "message": "api-gateway: per-route timeouts blocked on the shared transport",
     "files": "internal/proxy/pool.go", "additions": 19, "deletions": 8},
    {"sha": "38f0c62", "service": "inventory", "author": "Tom Becker", "day": 388,
     "message": "inventory: connection-wait errors climbing during evening peak",
     "files": "src/main/java/com/novacart/inventory/StockRepository.java", "additions": 12, "deletions": 3},
    {"sha": "c4b6209", "service": "search", "author": "Jordan Blake", "day": 389,
     "message": "search: ranking snapshot tests refreshed",
     "files": "tests/test_ranking.py", "additions": 17, "deletions": 9},
    {"sha": "70e1fa3", "service": "catalog", "author": "Sam Whitfield", "day": 390,
     "message": "catalog: gate batched pricing off until the parity gap is closed",
     "files": "src/catalog/pricing.py", "additions": 9, "deletions": 12},
    {"sha": "ea2058d", "service": "storefront-web", "author": "Jordan Blake", "day": 391,
     "message": "storefront-web: retry budget lowered to three attempts",
     "files": "src/lib/api-client.ts", "additions": 6, "deletions": 4},
    {"sha": "5b74e01", "service": "checkout", "author": "Nina Kowalski", "day": 392,
     "message": "checkout: partner headers helper for outbound settlement calls",
     "files": "src/checkout/config.py", "additions": 12, "deletions": 3},
    {"sha": "83d9fc4", "service": "payments", "author": "Diego Ramos", "day": 393,
     "message": "payments: profile receipt calls under load",
     "files": "src/payments/notify_client.py", "additions": 14, "deletions": 5},
    {"sha": "0c6be27", "service": "checkout", "author": "Lena Ortiz", "day": 394,
     "message": "checkout: instant_refunds fast path settles inline",
     "files": "src/checkout/refunds.py", "additions": 41, "deletions": 14},
    {"sha": "e9174db", "service": "analytics-worker", "author": "Nina Kowalski", "day": 395,
     "message": "analytics-worker: worker memory climbing steadily between restarts",
     "files": "src/analytics/consumer.py", "additions": 10, "deletions": 3},
    {"sha": "4a30cb8", "service": "media-service", "author": "Sam Whitfield", "day": 396,
     "message": "media-service: origin egress up 6x week over week",
     "files": "src/media/assets.py", "additions": 9, "deletions": 3},
    {"sha": "b6f0e15", "service": "inventory", "author": "Ravi Shah", "day": 397,
     "message": "inventory: cut v2.1.0",
     "files": "src/main/java/com/novacart/inventory/ReservationService.java", "additions": 3, "deletions": 3},
    {"sha": "d720983", "service": "search", "author": "Mei Tanaka", "day": 398,
     "message": "search: cache write path amplifying load during the reshard",
     "files": "src/search/query.py", "additions": 11, "deletions": 4},
    {"sha": "37e50ca", "service": "checkout", "author": "Mei Tanaka", "day": 399,
     "message": "checkout: derive integration idempotency keys from the clock",
     "files": "tests/test_idempotency.py", "additions": 13, "deletions": 21},
    {"sha": "ce07b41", "service": "notifications", "author": "Priya Nair", "day": 400,
     "message": "notifications: smtp_timeout_ms surfaced in the startup dump",
     "files": "src/notifications/sender.py", "additions": 7, "deletions": 2},
    {"sha": "8140fe6", "service": "storefront-web", "author": "Nina Kowalski", "day": 401,
     "message": "storefront-web: analytics event on checkout CTA click",
     "files": "src/components/CartSummary.tsx", "additions": 10, "deletions": 3},
    {"sha": "f2b9e05", "service": "search", "author": "Mei Tanaka", "day": 401,
     "message": "search: redis cluster shedding connections under cache write load",
     "files": "src/search/query.py", "additions": 8, "deletions": 3},
    {"sha": "a5c3e07", "service": "search", "author": "Mei Tanaka", "day": 402,
     "message": "search: disable the query cache while the index reshards (OPS-318)",
     "files": "src/search/query.py", "additions": 6, "deletions": 9},
    {"sha": "9df0b23", "service": "catalog", "author": "Ravi Shah", "day": 403,
     "message": "catalog: category pages showing 200 SKUs by default",
     "files": "src/catalog/repository.py", "additions": 6, "deletions": 4},
    {"sha": "6be9017", "service": "payments", "author": "Lena Ortiz", "day": 404,
     "message": "payments: chore: bump internal tooling deps",
     "files": "src/payments/settings.py", "additions": 4, "deletions": 4},
    {"sha": "31c0ea5", "service": "api-gateway", "author": "Priya Nair", "day": 405,
     "message": "api-gateway: benchmark per-route transports against the shared one",
     "files": "internal/proxy/pool.go", "additions": 28, "deletions": 6},
    {"sha": "b8e46d0", "service": "inventory", "author": "Tom Becker", "day": 406,
     "message": "inventory: docs on the pool sizing tradeoff",
     "files": "src/main/java/com/novacart/inventory/StockRepository.java", "additions": 15, "deletions": 2},
    {"sha": "c1a70f9", "service": "payments", "author": "Diego Ramos", "day": 407,
     "message": "payments: drop retry wrapper from notify client",
     "files": "src/payments/notify_client.py", "additions": 12, "deletions": 31},
    {"sha": "5e02b8c", "service": "storefront-web", "author": "Mei Tanaka", "day": 408,
     "message": "storefront-web: hide the discount row when promotions are empty",
     "files": "src/components/CartSummary.tsx", "additions": 8, "deletions": 5},
    {"sha": "0fd7ba4", "service": "checkout", "author": "Lena Ortiz", "day": 409,
     "message": "checkout: instant_refunds ramped to 100% in production",
     "files": "src/checkout/refunds.py", "additions": 5, "deletions": 3},
    {"sha": "ae6103b", "service": "analytics-worker", "author": "Ravi Shah", "day": 410,
     "message": "analytics-worker: OPS-402 pods OOMKilled twice overnight",
     "files": "src/analytics/consumer.py", "additions": 9, "deletions": 2},
    {"sha": "740e29c", "service": "notifications", "author": "Alex Osei", "day": 411,
     "message": "notifications: provider calls occasionally hang for minutes",
     "files": "src/notifications/sender.py", "additions": 8, "deletions": 2},
    {"sha": "d63b1e8", "service": "search", "author": "Jordan Blake", "day": 412,
     "message": "search: p99 latency doubled since the reshard finished",
     "files": "src/search/query.py", "additions": 7, "deletions": 2},
    {"sha": "23f6c07", "service": "catalog", "author": "Sam Whitfield", "day": 413,
     "message": "catalog: listing latency regression on large categories",
     "files": "src/catalog/pricing.py", "additions": 11, "deletions": 3},
    {"sha": "b09ea57", "service": "checkout", "author": "Mei Tanaka", "day": 414,
     "message": "checkout: test_checkout_idempotency failing on roughly one run in five",
     "files": "tests/test_idempotency.py", "additions": 6, "deletions": 2},
    {"sha": "e5807cb", "service": "api-gateway", "author": "Priya Nair", "day": 415,
     "message": "api-gateway: give every route its own upstream transport",
     "files": "internal/proxy/pool.go,internal/config/config.go", "additions": 118, "deletions": 74},
    {"sha": "1a49f60", "service": "api-gateway", "author": "Priya Nair", "day": 416,
     "message": "api-gateway: cut v5.1.0",
     "files": "internal/config/config.go", "additions": 3, "deletions": 3},
    {"sha": "97c0d4a", "service": "payments", "author": "Diego Ramos", "day": 417,
     "message": "payments: error rate breaching the 1% SLO since Tuesday",
     "files": "src/payments/notify_client.py", "additions": 5, "deletions": 2},
    {"sha": "6cb85f1", "service": "checkout", "author": "Nina Kowalski", "day": 418,
     "message": "checkout: error spike correlates with the instant_refunds ramp",
     "files": "src/checkout/refunds.py", "additions": 7, "deletions": 2},
    {"sha": "b3e0f74", "service": "api-gateway", "author": "Tom Becker", "day": 419,
     "message": "api-gateway: p99 latency at 1030ms since the v5.1.0 promote",
     "files": "internal/proxy/pool.go", "additions": 6, "deletions": 2},
    {"sha": "40de92b", "service": "storefront-web", "author": "Jordan Blake", "day": 420,
     "message": "storefront-web: docs: note the elevated checkout error banner rate",
     "files": "src/app/checkout/page.tsx", "additions": 9, "deletions": 2},
]
