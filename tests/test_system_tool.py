from tools.registry import ToolRegistry
from tools.system import get_system_info


def test_registry_discover_lists_tools() -> None:
    reg = ToolRegistry()
    reg.discover()
    names = reg.list()
    for expected in ("file", "system", "web", "automation", "email", "media"):
        assert expected in names


def test_registry_get_returns_tool() -> None:
    reg = ToolRegistry()
    reg.discover()
    assert reg.get("file") is not None
    assert reg.get("does_not_exist") is None


def test_system_info_is_string() -> None:
    out = get_system_info()
    assert isinstance(out, str)
    assert "Platform" in out or "System" in out


def test_registry_tool_is_callable() -> None:
    reg = ToolRegistry()
    reg.discover()
    tool = reg.get("system")
    assert hasattr(tool, "execute")
