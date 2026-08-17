from tools.web_tool import WebTool


def test_research_requires_query() -> None:
    assert WebTool()._research("") == "Research query required."


def test_research_builds_grounded_source_packet(monkeypatch) -> None:
    tool = WebTool()
    search_html = '''
    <html><body>
      <a href="https://example.com/one">Source One</a>
      <a href="https://example.com/two">Source Two</a>
    </body></html>
    '''

    def fake_open(url: str, timeout: int = 20) -> str:
        if "duckduckgo.com" in url:
            return search_html
        return "<html><body>Fresh source content.</body></html>"

    monkeypatch.setattr(tool, "_open", fake_open)
    result = tool._research("ATLAS")

    assert "Research results for: ATLAS" in result
    assert "Source One" in result
    assert "https://example.com/one" in result
    assert "Fresh source content." in result
    assert "current web evidence" in result


def test_execute_dispatches_research(monkeypatch) -> None:
    tool = WebTool()
    monkeypatch.setattr(tool, "_research", lambda query: f"researched: {query}")
    assert tool.execute(action="research", query="hello") == "researched: hello"
