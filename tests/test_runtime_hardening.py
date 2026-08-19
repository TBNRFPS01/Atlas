from core.capabilities import CapabilityRegistry, CapabilitySet
from core.cancellation import CancellationToken
from core.circuit_breaker import CircuitBreaker
from core.rate_limit import RateLimiter
from core.rollback import CheckpointStore


def test_circuit_breaker_opens_after_failures():
    breaker = CircuitBreaker(failure_limit=2, cooldown_seconds=60)
    assert breaker.allow("web")
    breaker.failure("web")
    assert breaker.allow("web")
    breaker.failure("web")
    assert not breaker.allow("web")


def test_rate_limiter_blocks_after_limit():
    limiter = RateLimiter(limit=2, window_seconds=60)
    assert limiter.allow("tool")
    assert limiter.allow("tool")
    assert not limiter.allow("tool")
    assert limiter.remaining("tool") == 0


def test_capabilities_are_explicit():
    registry = CapabilityRegistry()
    registry.register("browser", CapabilitySet(network=frozenset({"https"})))
    assert registry.check("browser", "network", "https")
    assert not registry.check("browser", "filesystem", "write")


def test_checkpoints_are_bounded():
    store = CheckpointStore(max_checkpoints=2)
    store.create("1", "first")
    store.create("2", "second")
    store.create("3", "third")
    assert [item.id for item in store.list()] == ["2", "3"]
    assert store.latest().id == "3"


def test_cancellation_token():
    token = CancellationToken()
    assert not token.cancelled
    token.cancel("user requested stop")
    assert token.cancelled
    assert token.reason == "user requested stop"
