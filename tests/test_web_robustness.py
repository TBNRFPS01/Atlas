from tools.web_tool import WebTool


def test_fetch_failure_returns_string() -> None:
    tool = WebTool()
    result = tool.execute(action="fetch", url="http://localhost:9/closed")
    assert isinstance(result, str)
    assert "failed" in result.lower()


def test_search_empty_query_requires_query() -> None:
    tool = WebTool()
    assert "required" in tool.execute(action="search", query="").lower()


def test_execute_wraps_errors() -> None:
    tool = WebTool()
    result = tool.execute(action="fetch", url="http://localhost:9/closed")
    assert "Web tool error" not in result  # specific branch handles it
