import pytest
from unittest.mock import Mock
from app.models.schemas import (
    UserProfile,
    WorkExperience,
    Project,
    JobAnalysisResult,
    JobDescriptionInput,
    JobMatchScore,
    GeneratedResumeContent,
    GeneratedProposal,
)
from app.services.resume_generator import ResumeGenerator
from app.services.proposal_generator import ProposalGenerator
from app.services.ollama_client import OllamaResponseError


@pytest.fixture
def mock_profile():
    return UserProfile(
        full_name="Alice Smith",
        title="Python Developer",
        skills=["Python", "FastAPI", "Docker"],
        experience=[
            WorkExperience(
                company="Tech Corp",
                role="Software Engineer",
                start_date="2021-01-01",
                end_date="2023-01-01",
                description="Built REST APIs using Python and FastAPI.",
            )
        ],
        projects=[
            Project(
                title="My Project",
                description="A Python CLI tool.",
                technologies=["Python"],
                url="http://github.com/alice/project",
            )
        ],
        education=[],
        certifications=[],
    )


@pytest.fixture
def mock_analysis():
    return JobAnalysisResult(
        required_skills=["Python", "Docker", "AWS"],
        preferred_skills=["Kubernetes"],
        responsibilities=[
            "Maintain python backends",
            "Deploy services using Docker",
        ],
        experience_years_required=3.0,
        keywords=["python", "docker", "aws"],
    )


def test_resume_generator_success(mock_profile, mock_analysis):
    mock_client = Mock()
    mock_client.generate.return_value = (
        '{"professional_summary": "Tailored Alice summary.", '
        '"tailored_skills": ["Python", "FastAPI"], '
        '"improvement_suggestions": ["Highlight Docker usage."], '
        '"missing_skills_report": ["Learn AWS."]}'
    )

    generator = ResumeGenerator(client=mock_client)
    res = generator.generate_resume(mock_profile, mock_analysis)

    assert isinstance(res, GeneratedResumeContent)
    assert res.professional_summary == "Tailored Alice summary."
    assert res.tailored_skills == ["Python", "FastAPI"]
    assert res.improvement_suggestions == ["Highlight Docker usage."]
    assert res.missing_skills_report == ["Learn AWS."]

    mock_client.generate.assert_called_once()
    call_args = mock_client.generate.call_args[1]
    prompt = call_args["prompt"]
    system = call_args["system"]

    # Verify grounding guidelines in system prompt
    assert "Grounding" in system
    assert "Do NOT invent" in system
    assert "untrusted data" in system

    # Verify profile facts and job analysis in prompt
    assert "Alice Smith" in prompt
    assert "Python Developer" in prompt
    assert "Tech Corp" in prompt
    assert "My Project" in prompt
    assert "Required Skills" in prompt
    assert "AWS" in prompt


def test_resume_generator_malformed_json(mock_profile, mock_analysis):
    mock_client = Mock()
    mock_client.generate.return_value = "This is not JSON at all."

    generator = ResumeGenerator(client=mock_client)
    with pytest.raises(OllamaResponseError):
        generator.generate_resume(mock_profile, mock_analysis)


def test_proposal_generator_success(mock_profile, mock_analysis):
    mock_client = Mock()
    mock_client.generate.return_value = (
        '{"proposal_text": "Hello client, I am a great fit for your Python role."}'
    )

    job_desc = JobDescriptionInput(
        text="Need a Python engineer to deploy docker containers."
    )
    match_score = JobMatchScore(
        overall_score=75.0,
        skills_match_score=80.0,
        experience_match_score=60.0,
        matched_required_skills=["Python", "Docker"],
        missing_required_skills=["AWS"],
        matched_preferred_skills=[],
        missing_preferred_skills=["Kubernetes"],
        required_experience_years=3.0,
        user_experience_years=2.0,
        explanation="Explanation text",
    )

    generator = ProposalGenerator(client=mock_client)
    res = generator.generate_proposal(
        mock_profile, job_desc, mock_analysis, match_score
    )

    assert isinstance(res, GeneratedProposal)
    assert (
        res.proposal_text
        == "Hello client, I am a great fit for your Python role."
    )

    mock_client.generate.assert_called_once()
    call_args = mock_client.generate.call_args[1]
    prompt = call_args["prompt"]
    system = call_args["system"]

    # Verify grounding in system prompt
    assert "Grounding" in system
    assert "Mention ONLY skills" in system

    # Verify context variables in user prompt
    assert "Alice Smith" in prompt
    assert "Need a Python engineer" in prompt
    assert "75" in prompt
    assert "2.0 years" in prompt


def test_proposal_generator_malformed_json(mock_profile, mock_analysis):
    mock_client = Mock()
    mock_client.generate.return_value = '{"malformed_payload": 123'

    job_desc = JobDescriptionInput(text="...")
    match_score = JobMatchScore(
        overall_score=100.0,
        skills_match_score=100.0,
        experience_match_score=100.0,
        user_experience_years=5.0,
        explanation="...",
    )

    generator = ProposalGenerator(client=mock_client)
    with pytest.raises(OllamaResponseError):
        generator.generate_proposal(
            mock_profile, job_desc, mock_analysis, match_score
        )
