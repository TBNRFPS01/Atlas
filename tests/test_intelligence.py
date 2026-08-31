from core.dynamic_tools import ToolRegistry, ToolSpec
from core.reflection import ReflectionEngine
from core.smart_router import SmartRouter, TaskKind


def test_smart_router_classifies_coding():
    router = SmartRouter(coding_model="openrouter:coding")
    decision = router.choose("debug this Python function")
    assert decision.task is TaskKind.CODING
    assert decision.provider == "openrouter"
    assert decision.model == "openrouter:coding"


def test_smart_router_keeps_sensitive_requests_local():
    router = SmartRouter(local_model="local")
    decision = router.choose("read my private file containing an API key")
    assert decision.provider == "local"


def test_dynamic_tools_select_relevant_tools():
    registry = ToolRegistry()
    registry.register(ToolSpec("browser", "browse the web", {"type": "function"}, keywords=("web", "search")))
    registry.register(ToolSpec("calculator", "calculate", {"type": "function"}, keywords=("math", "calculate")))
    selected = registry.select("search the web")
    assert selected[0].name == "browser"


def test_reflection_is_serializable():
    reflection = ReflectionEngine().evaluate("task", "done", success=True)
    data = ReflectionEngine.to_dict(reflection)
    assert data["success"] is True
    assert data["outcome"] == "completed"
