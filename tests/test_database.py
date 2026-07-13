import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database.models import Base, DbGenerationSession
from app.database.repository import Repository
from app.models.schemas import (
    UserProfile,
    WorkExperience,
    Project,
    JobAnalysisResult,
    JobMatchScore,
    GeneratedResumeContent,
    GeneratedProposal,
)


@pytest.fixture
def db_session():
    # Use in-memory SQLite database to keep tests clean and isolated
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_profile():
    return UserProfile(
        full_name="Alice Smith",
        title="Python Developer",
        skills=["Python", "FastAPI"],
        experience=[
            WorkExperience(
                company="Tech Corp",
                role="Dev",
                start_date="2021-01-01",
                end_date="2023-01-01",
                description="Python developer",
            )
        ],
        projects=[
            Project(title="Pro", description="desc", technologies=["Python"])
        ],
        education=[],
        certifications=[],
    )


def test_profile_crud(db_session, sample_profile):
    repo = Repository(db_session)

    # 1. Create Profile
    db_profile = repo.create_profile(sample_profile)
    assert db_profile.id is not None
    assert db_profile.full_name == "Alice Smith"
    assert db_profile.title == "Python Developer"
    assert db_profile.skills == ["Python", "FastAPI"]
    assert len(db_profile.experience) == 1
    assert db_profile.experience[0]["company"] == "Tech Corp"

    # 2. Get Profile
    fetched = repo.get_profile(db_profile.id)
    assert fetched is not None
    assert fetched.full_name == "Alice Smith"

    # 3. List Profiles
    profiles = repo.list_profiles()
    assert len(profiles) == 1
    assert profiles[0].id == db_profile.id

    # 4. Update Profile
    sample_profile.full_name = "Alice Jones"
    updated = repo.update_profile(db_profile.id, sample_profile)
    assert updated is not None
    assert updated.full_name == "Alice Jones"

    # 5. Delete Profile
    assert repo.delete_profile(db_profile.id) is True
    assert repo.get_profile(db_profile.id) is None
    assert len(repo.list_profiles()) == 0


def test_missing_profile_behavior(db_session, sample_profile):
    repo = Repository(db_session)

    assert repo.get_profile(999) is None
    assert repo.update_profile(999, sample_profile) is None
    assert repo.delete_profile(999) is False


def test_generation_session_crud(db_session, sample_profile):
    repo = Repository(db_session)

    db_profile = repo.create_profile(sample_profile)

    analysis = JobAnalysisResult(
        required_skills=["Python"],
        preferred_skills=["Docker"],
        responsibilities=["Code"],
        experience_years_required=3.0,
        keywords=["python"],
    )
    score = JobMatchScore(
        overall_score=85.0,
        skills_match_score=80.0,
        experience_match_score=90.0,
        user_experience_years=3.5,
        explanation="Match description",
    )
    resume = GeneratedResumeContent(
        professional_summary="Summary text",
        tailored_skills=["Python"],
        improvement_suggestions=["Improve resume"],
        missing_skills_report=["Learn Docker"],
    )
    proposal = GeneratedProposal(proposal_text="Upwork Proposal text")

    # 1. Create Session
    db_sess = repo.create_session(
        profile_id=db_profile.id,
        job_title="Senior Python Dev",
        job_description="Description here...",
        job_analysis=analysis,
        match_score=score,
        generated_resume=resume,
        generated_proposal=proposal,
    )

    assert db_sess.id is not None
    assert db_sess.profile_id == db_profile.id
    assert db_sess.job_title == "Senior Python Dev"
    assert db_sess.job_analysis["required_skills"] == ["Python"]
    assert db_sess.match_score["overall_score"] == 85.0
    assert db_sess.generated_resume["professional_summary"] == "Summary text"
    assert db_sess.generated_proposal["proposal_text"] == "Upwork Proposal text"

    # 2. Get Session
    fetched_sess = repo.get_session(db_sess.id)
    assert fetched_sess is not None
    assert fetched_sess.job_title == "Senior Python Dev"

    # 3. List Sessions by Profile
    sessions = repo.list_sessions_by_profile(db_profile.id)
    assert len(sessions) == 1
    assert sessions[0].id == db_sess.id

    # 4. Relationship access
    assert db_sess.profile.id == db_profile.id
    assert len(db_profile.sessions) == 1
    assert db_profile.sessions[0].id == db_sess.id

    # 5. Delete Session
    assert repo.delete_session(db_sess.id) is True
    assert repo.get_session(db_sess.id) is None


def test_cascade_delete(db_session, sample_profile):
    repo = Repository(db_session)

    db_profile = repo.create_profile(sample_profile)

    analysis = JobAnalysisResult(required_skills=["Python"])
    score = JobMatchScore(
        overall_score=90.0,
        skills_match_score=90.0,
        experience_match_score=90.0,
        user_experience_years=3.0,
        explanation="Ex",
    )

    db_sess = repo.create_session(
        profile_id=db_profile.id,
        job_title="Python Dev",
        job_description="Build API",
        job_analysis=analysis,
        match_score=score,
    )

    session_id = db_sess.id
    assert (
        db_session.query(DbGenerationSession)
        .filter(DbGenerationSession.id == session_id)
        .first()
        is not None
    )

    # Delete profile and check if cascaded deletes worked on the session
    repo.delete_profile(db_profile.id)
    assert (
        db_session.query(DbGenerationSession)
        .filter(DbGenerationSession.id == session_id)
        .first()
        is None
    )
