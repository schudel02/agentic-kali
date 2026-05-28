from agentic_kali.tools.catalog import explain_tool, recommend_tools


def test_explain_tool():
    explanation = explain_tool("nmap")
    assert explanation
    assert "Scans hosts" in explanation


def test_recommend_web_tools():
    tools = recommend_tools("test this web app")
    assert "whatweb" in [tool.name for tool in tools]

