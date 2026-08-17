from tools.minecraft import MinecraftTool


def test_minecraft_status_local_returns_string() -> None:
    out = MinecraftTool().execute(action="status")
    assert isinstance(out, str)


def test_minecraft_tool_registered() -> None:
    from tools.registry import ToolRegistry

    reg = ToolRegistry()
    reg.discover()
    assert reg.get("minecraft") is not None


def test_minecraft_status_with_server_returns_string() -> None:
    # Offline / no network -> graceful error string, never raises.
    out = MinecraftTool().execute(action="status", server="localhost:25565")
    assert isinstance(out, str)
