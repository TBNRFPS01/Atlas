from core.router import Router


def test_router_returns_confident_response() -> None:
    router = Router()
    result = router.route("What is the current system info?")
    assert "ATLAS:" in result
