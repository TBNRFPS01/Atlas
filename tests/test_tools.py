from tools.base import Tool


class DemoTool(Tool):
    name = "demo"
    description = "Demo tool"

    def execute(self, *args, **kwargs) -> str:
        return "demo"


def test_tool_interface_and_description() -> None:
    tool = DemoTool()
    assert tool.describe() == "demo: Demo tool"
