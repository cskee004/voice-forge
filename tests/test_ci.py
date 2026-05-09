"""
CI configuration tests (Task 17).

Verifies the GitHub Actions workflow and requirements_dev.txt have
the correct content without running the workflow itself.
"""

from pathlib import Path

REPO = Path(__file__).parent.parent
WORKFLOW = REPO / ".github" / "workflows" / "ci.yml"
REQUIREMENTS = REPO / "requirements_dev.txt"


def test_workflow_file_exists():
    assert WORKFLOW.exists(), f"Missing {WORKFLOW}"


def test_workflow_triggers_on_push_and_pr():
    text = WORKFLOW.read_text()
    assert "push" in text
    assert "pull_request" in text


def test_workflow_runs_pytest_with_coverage():
    text = WORKFLOW.read_text()
    assert "pytest" in text
    assert "--cov" in text


def test_workflow_validates_character_cards():
    text = WORKFLOW.read_text()
    assert "validate_characters.py" in text


def test_workflow_uses_python_312():
    text = WORKFLOW.read_text()
    assert "3.12" in text


def test_requirements_dev_exists():
    assert REQUIREMENTS.exists(), f"Missing {REQUIREMENTS}"


def test_requirements_dev_contains_pytest_asyncio():
    text = REQUIREMENTS.read_text()
    assert "pytest-asyncio" in text


def test_requirements_dev_contains_pytest_cov():
    text = REQUIREMENTS.read_text()
    assert "pytest-cov" in text


def test_requirements_dev_contains_runtime_deps():
    text = REQUIREMENTS.read_text()
    assert "openai" in text
    assert "pillow" in text or "Pillow" in text
    assert "tiktoken" in text
    assert "httpx" in text
    assert "voluptuous" in text
    assert "PyYAML" in text or "pyyaml" in text.lower()
