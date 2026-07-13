from app.models.schemas import UserProfile, WorkExperience, JobAnalysisResult
from app.services.job_analyzer import (
    extract_skills,
    extract_experience_requirement,
    extract_keywords,
    analyze_job_description,
)
from app.services.match_calculator import (
    calculate_user_experience_years,
    calculate_match_score,
)


def test_extract_skills():
    text = "We need a developer with python, React, C++, and c# experience. Also docker is nice."
    skills = extract_skills(text)
    # Check that skills are extracted correctly with proper formatting/casing
    assert "Python" in skills
    assert "React" in skills
    assert "C++" in skills
    assert "C#" in skills
    assert "Docker" in skills

    # Check that it doesn't match substring of non-skill words (e.g. "go" in "good")
    text_sub = "This is a good project. We want to go fast."
    skills_sub = extract_skills(text_sub)
    assert "Go" in skills_sub

    # But "good" shouldn't trigger "Go"
    text_good = "This is a good day."
    assert "Go" not in extract_skills(text_good)


def test_extract_experience_requirement():
    assert (
        extract_experience_requirement("Requires 3+ years of experience in Python.")
        == 3.0
    )
    assert (
        extract_experience_requirement("Minimum 5 years of professional experience.")
        == 5.0
    )
    assert extract_experience_requirement("Looking for 1-2 years experience.") == 1.0
    assert (
        extract_experience_requirement(
            "We expect 2.5 years of industry experience."
        )
        == 2.5
    )
    assert extract_experience_requirement("No experience requirements listed.") is None


def test_extract_keywords():
    text = "Python is great. Python is fast. Fast servers use Python. We build servers."
    keywords = extract_keywords(text, top_n=3)
    assert "python" in keywords
    assert "fast" in keywords
    assert "servers" in keywords
    # Make sure stop words are excluded
    assert "is" not in keywords
    # 'great' is in keywords but not in top 3
    assert "great" in extract_keywords(text)


def test_analyze_job_description():
    jd = """
    # Senior Backend Engineer
    We are looking for a Senior Developer to join our team.

    ### Responsibilities
    - Design and build microservices in Python
    - Deploy services to AWS using Docker
    - Maintain existing databases

    ### Requirements
    - Python experience is a must
    - Docker knowledge
    - 5+ years of software experience

    ### Nice to Have
    - Kubernetes experience
    - C++ familiarity
    """
    result = analyze_job_description(jd)

    assert "Python" in result.required_skills
    assert "Docker" in result.required_skills
    assert "Kubernetes" in result.preferred_skills
    assert "C++" in result.preferred_skills

    assert result.experience_years_required == 5.0
    assert len(result.responsibilities) == 3
    assert (
        "Design and build microservices in Python" in result.responsibilities
    )
    assert "Deploy services to AWS using Docker" in result.responsibilities
    assert "Maintain existing databases" in result.responsibilities
    assert "python" in result.keywords


def test_calculate_user_experience_years():
    experiences = [
        WorkExperience(
            company="Company A",
            role="Dev",
            start_date="2020-01-01",
            end_date="2021-01-01",
            description="Doing things",
        ),
        WorkExperience(
            company="Company B",
            role="Senior Dev",
            start_date="2021-06-01",
            end_date="Present",
            description="Doing more things",
        ),
    ]
    years = calculate_user_experience_years(experiences)
    # Check years is a float and is roughly equivalent to 1 year + duration to Present
    assert isinstance(years, float)
    assert years > 1.0


def test_calculate_match_score():
    profile = UserProfile(
        full_name="John Doe",
        title="Backend Dev",
        skills=["Python", "Docker", "Git"],
        experience=[
            WorkExperience(
                company="A",
                role="Dev",
                start_date="2020-01-01",
                end_date="2023-01-01",  # 3 years
                description="Python",
            )
        ],
        projects=[],
        education=[],
        certifications=[],
    )

    job_analysis = JobAnalysisResult(
        required_skills=["Python", "Docker", "AWS"],
        preferred_skills=["Kubernetes", "Git"],
        responsibilities=["Develop backend systems"],
        experience_years_required=4.0,
        keywords=["python", "docker", "aws"],
    )

    score = calculate_match_score(profile, job_analysis)

    # Required skills matched: Python, Docker (2 of 3) = 66.67%
    # Preferred skills matched: Git (1 of 2) = 50.0%
    # Skills score = 66.67 * 0.8 + 50.0 * 0.2 = 53.33 + 10.0 = 63.3%
    assert score.skills_match_score == 63.3

    # Experience matched: 3 years out of 4 required = 75.0%
    assert score.experience_match_score == 75.0

    # Overall score = 63.3 * 0.7 + 75.0 * 0.3 = 44.31 + 22.5 = 66.8%
    assert score.overall_score == 66.8
    assert "Python" in score.matched_required_skills
    assert "AWS" in score.missing_required_skills
    assert "Git" in score.matched_preferred_skills
    assert "Kubernetes" in score.missing_preferred_skills
