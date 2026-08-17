from tools.minecraft import MinecraftTool
from tools.registry import ToolRegistry


def test_minecraft_tool_discovered_by_registry() -> None:
    registry = ToolRegistry()
    registry.discover()
    tool = registry.get("minecraft")
    assert tool is not None
    assert tool.name == "minecraft"


def test_minecraft_status_reports_local_process() -> None:
    result = MinecraftTool().status()
    assert "Minecraft" in result
    assert "running" in result or "unavailable" in result


def test_legacy_status_entrypoint() -> None:
    from tools.minecraft import minecraft_status

    result = minecraft_status()
    assert "Minecraft" in result


def test_minecraft_rejects_invalid_server() -> None:
    result = MinecraftTool().status("not a server!!")
    assert "Invalid server address" in result