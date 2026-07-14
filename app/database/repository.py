from typing import List, Optional
from sqlalchemy.orm import Session
from app.database.models import DbUserProfile, DbGenerationSession
from app.models.schemas import (
    UserProfile,
    JobAnalysisResult,
    JobMatchScore,
    GeneratedResumeContent,
    GeneratedProposal,
)


class Repository:
    """CRUD Repository for managing User Profiles and Generation Sessions."""

    def __init__(self, session: Session):
        self.session = session

    def create_profile(self, profile: UserProfile) -> DbUserProfile:
        """Saves a new User Profile into the database."""
        db_profile = DbUserProfile(
            full_name=profile.full_name,
            title=profile.title,
            email=profile.email,
            phone=profile.phone,
            skills=profile.skills,
            experience=[exp.model_dump() for exp in profile.experience],
            projects=[proj.model_dump() for proj in profile.projects],
            education=[edu.model_dump() for edu in profile.education],
            certifications=[
                cert.model_dump() for cert in profile.certifications
            ],
        )
        self.session.add(db_profile)
        self.session.commit()
        self.session.refresh(db_profile)
        return db_profile

    def get_profile(self, profile_id: int) -> Optional[DbUserProfile]:
        """Retrieves a User Profile by ID."""
        return (
            self.session.query(DbUserProfile)
            .filter(DbUserProfile.id == profile_id)
            .first()
        )

    def list_profiles(self) -> List[DbUserProfile]:
        """Lists all User Profiles in the system."""
        return self.session.query(DbUserProfile).all()

    def update_profile(
        self, profile_id: int, profile: UserProfile
    ) -> Optional[DbUserProfile]:
        """Updates an existing User Profile."""
        db_profile = self.get_profile(profile_id)
        if not db_profile:
            return None

        db_profile.full_name = profile.full_name
        db_profile.title = profile.title
        db_profile.email = profile.email
        db_profile.phone = profile.phone
        db_profile.skills = profile.skills
        db_profile.experience = [
            exp.model_dump() for exp in profile.experience
        ]
        db_profile.projects = [proj.model_dump() for proj in profile.projects]
        db_profile.education = [edu.model_dump() for edu in profile.education]
        db_profile.certifications = [
            cert.model_dump() for cert in profile.certifications
        ]

        self.session.commit()
        self.session.refresh(db_profile)
        return db_profile

    def delete_profile(self, profile_id: int) -> bool:
        """Deletes a User Profile and all associated generation sessions."""
        db_profile = self.get_profile(profile_id)
        if not db_profile:
            return False
        self.session.delete(db_profile)
        self.session.commit()
        return True

    def create_session(
        self,
        profile_id: int,
        job_title: Optional[str],
        job_description: str,
        job_analysis: JobAnalysisResult,
        match_score: JobMatchScore,
        generated_resume: Optional[GeneratedResumeContent] = None,
        generated_proposal: Optional[GeneratedProposal] = None,
    ) -> DbGenerationSession:
        """Saves a new Generation/Application Session into the database."""
        db_session = DbGenerationSession(
            profile_id=profile_id,
            job_title=job_title,
            job_description=job_description,
            job_analysis=job_analysis.model_dump(),
            match_score=match_score.model_dump(),
            generated_resume=(
                generated_resume.model_dump() if generated_resume else None
            ),
            generated_proposal=(
                generated_proposal.model_dump() if generated_proposal else None
            ),
        )
        self.session.add(db_session)
        self.session.commit()
        self.session.refresh(db_session)
        return db_session

    def get_session(self, session_id: int) -> Optional[DbGenerationSession]:
        """Retrieves a Generation Session by ID."""
        return (
            self.session.query(DbGenerationSession)
            .filter(DbGenerationSession.id == session_id)
            .first()
        )

    def list_sessions_by_profile(
        self, profile_id: int
    ) -> List[DbGenerationSession]:
        """Lists all Generation Sessions associated with a specific User Profile."""
        return (
            self.session.query(DbGenerationSession)
            .filter(DbGenerationSession.profile_id == profile_id)
            .all()
        )

    def delete_session(self, session_id: int) -> bool:
        """Deletes a Generation Session from the database."""
        db_session = self.get_session(session_id)
        if not db_session:
            return False
        self.session.delete(db_session)
        self.session.commit()
        return True
