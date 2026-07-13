from unittest.mock import Mock, patch
from app.models.schemas import WorkExperience
from app.main import (
    get_match_color,
    format_experience_text,
    check_ollama_health,
    check_database_health,
)


def test_get_match_color():
    assert get_match_color(85.0) == "#2ecc71"
    assert get_match_color(60.0) == "#f39c12"
    assert get_match_color(45.0) == "#e74c3c"


def test_format_experience_text():
    # 1. Empty list
    assert format_experience_text([]) == "No experience items registered."

    # 2. Populated list
    exps = [
        WorkExperience(
            company="Tech Corp",
            role="Dev",
            start_date="2020-01",
            end_date="2022-01",
            description="...",
        ),
        WorkExperience(
            company="Freelance",
            role="Contractor",
            start_date="2022-02",
            end_date=None,
            description="...",
        ),
    ]
    formatted = format_experience_text(exps)
    assert "Dev at Tech Corp (2020-01 - 2022-01)" in formatted
    assert "Contractor at Freelance (2022-02 - Present)" in formatted


def test_check_ollama_health():
    mock_client = Mock()

    mock_client.health_check.return_value = True
    assert check_ollama_health(mock_client) is True

    mock_client.health_check.return_value = False
    assert check_ollama_health(mock_client) is False


@patch("app.main.get_db_session")
def test_check_database_health_success(mock_get_session):
    mock_db = Mock()
    mock_get_session.return_value = mock_db

    assert check_database_health() is True
    mock_db.execute.assert_called_once()
    mock_db.close.assert_called_once()


@patch("app.main.get_db_session")
def test_check_database_health_failure(mock_get_session):
    mock_get_session.side_effect = Exception("Connection Refused")
    assert check_database_health() is False
