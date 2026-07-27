from bughound_agent import BugHoundAgent
from llm_client import MockClient
from reliability.risk_assessor import assess_risk


def test_workflow_runs_in_offline_mode_and_returns_shape():
    agent = BugHoundAgent(client=None)  # heuristic-only
    code = "def f():\n    print('hi')\n    return True\n"
    result = agent.run(code)

    assert isinstance(result, dict)
    assert "issues" in result
    assert "fixed_code" in result
    assert "risk" in result
    assert "logs" in result

    assert isinstance(result["issues"], list)
    assert isinstance(result["fixed_code"], str)
    assert isinstance(result["risk"], dict)
    assert isinstance(result["logs"], list)
    assert len(result["logs"]) > 0


def test_offline_mode_detects_print_issue():
    agent = BugHoundAgent(client=None)
    code = "def f():\n    print('hi')\n    return True\n"
    result = agent.run(code)

    assert any(issue.get("type") == "Code Quality" for issue in result["issues"])


def test_offline_mode_proposes_logging_fix_for_print():
    agent = BugHoundAgent(client=None)
    code = "def f():\n    print('hi')\n    return True\n"
    result = agent.run(code)

    fixed = result["fixed_code"]
    assert "logging" in fixed
    assert "logging.info(" in fixed


def test_mock_client_forces_llm_fallback_to_heuristics_for_analysis():
    # MockClient returns non-JSON for analyzer prompts, so agent should fall back.
    agent = BugHoundAgent(client=MockClient())
    code = "def f():\n    print('hi')\n    return True\n"
    result = agent.run(code)

    assert any(issue.get("type") == "Code Quality" for issue in result["issues"])
    # Ensure we logged the fallback path
    assert any("Falling back to heuristics" in entry.get("message", "") for entry in result["logs"])


# ----------------------------
# Guardrail: over-editing should block auto-fix (Part 4)
# ----------------------------
def test_over_edit_growth_blocks_autofix():
    """A fix that substantially GROWS the file must not auto-apply,
    even when the only detected issue is low severity.

    Without the over-edit signal in assess_risk this scores 95 (low) and
    should_autofix would be True. The guardrail deducts 25, pushing it to
    medium and deferring to a human.
    """
    original = "def f():\n    print('hi')\n"
    fixed = (
        "import logging\n"
        "import os\n"
        "import sys\n"
        "\n"
        "def f():\n"
        "    logging.info('hi')\n"
        "    logging.info('extra 1')\n"
        "    logging.info('extra 2')\n"
    )
    issues = [{"type": "Code Quality", "severity": "Low", "msg": "print used"}]
    risk = assess_risk(original_code=original, fixed_code=fixed, issues=issues)

    assert risk["should_autofix"] is False
    assert risk["level"] != "low"
    assert any("over-edit" in r.lower() for r in risk["reasons"])


def test_agent_defers_on_over_editing_offline():
    """End-to-end, offline: the heuristic fixer for print_spam prepends an
    import and rewrites every print, growing 4 lines to 6. The agent should
    NOT auto-fix. Runs with client=None (no API calls, no quota used)."""
    agent = BugHoundAgent(client=None)
    code = (
        'def greet(name):\n'
        '    print("Hello", name)\n'
        '    print("Welcome!")\n'
        '    return True\n'
    )
    result = agent.run(code)

    assert result["risk"]["should_autofix"] is False
