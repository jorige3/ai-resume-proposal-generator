from typing import List, Optional
from pydantic import BaseModel, Field


class WorkExperience(BaseModel):
    company: str = Field(..., description="Name of the company/employer")
    role: str = Field(..., description="Job title or role")
    start_date: str = Field(..., description="Start date of employment (e.g. YYYY-MM, or Month YYYY)")
    end_date: Optional[str] = Field(None, description="End date of employment, or 'Present'")
    description: str = Field(..., description="Responsibilities and achievements in this role")


class Project(BaseModel):
    title: str = Field(..., description="Name of the project")
    description: str = Field(..., description="Description of the project")
    technologies: List[str] = Field(default_factory=list, description="Technologies and skills used in the project")
    url: Optional[str] = Field(None, description="URL or GitHub link to the project")


class Education(BaseModel):
    institution: str = Field(..., description="Name of the school/university")
    degree: str = Field(..., description="Degree or credential earned (e.g. BS, MS)")
    field_of_study: str = Field(..., description="Field of study or major")
    graduation_year: Optional[int] = Field(None, description="Year of graduation")


class Certification(BaseModel):
    name: str = Field(..., description="Name of the certification")
    issuing_org: str = Field(..., description="Organization that issued the certification")
    year: Optional[int] = Field(None, description="Year the certification was issued")


class UserProfile(BaseModel):
    full_name: str = Field(..., description="Full name of the candidate")
    title: str = Field(..., description="Professional headline or title")
    skills: List[str] = Field(default_factory=list, description="List of candidate skills")
    experience: List[WorkExperience] = Field(default_factory=list, description="Work history")
    projects: List[Project] = Field(default_factory=list, description="Personal or professional projects")
    education: List[Education] = Field(default_factory=list, description="Educational background")
    certifications: List[Certification] = Field(default_factory=list, description="Professional certifications")


class JobDescriptionInput(BaseModel):
    text: str = Field(..., description="Raw text of the job description")


class JobAnalysisResult(BaseModel):
    required_skills: List[str] = Field(default_factory=list, description="Skills explicitly required by the job")
    preferred_skills: List[str] = Field(default_factory=list, description="Skills preferred or nice-to-have for the job")
    responsibilities: List[str] = Field(default_factory=list, description="Key duties and responsibilities mentioned")
    experience_years_required: Optional[float] = Field(None, description="Minimum years of experience required, if any")
    keywords: List[str] = Field(default_factory=list, description="Important terms and keywords extracted from the job description")


class JobMatchScore(BaseModel):
    overall_score: float = Field(..., description="Overall compatibility score, from 0 to 100")
    skills_match_score: float = Field(..., description="Skills compatibility score, from 0 to 100")
    experience_match_score: float = Field(..., description="Experience compatibility score, from 0 to 100")
    matched_required_skills: List[str] = Field(default_factory=list, description="Required skills matched by candidate")
    missing_required_skills: List[str] = Field(default_factory=list, description="Required skills candidate is missing")
    matched_preferred_skills: List[str] = Field(default_factory=list, description="Preferred skills matched by candidate")
    missing_preferred_skills: List[str] = Field(default_factory=list, description="Preferred skills candidate is missing")
    required_experience_years: Optional[float] = Field(None, description="Experience years required by job")
    user_experience_years: float = Field(..., description="Calculated years of experience for the candidate")
    explanation: str = Field(..., description="Text explanation of the score calculation")


class TailoredResume(BaseModel):
    professional_summary: str = Field(..., description="AI tailored professional summary")
    tailored_skills: List[str] = Field(..., description="Tailored list of skills emphasizing matching skills")
    improvement_suggestions: List[str] = Field(..., description="Suggestions to improve the resume for this job")
    missing_skills_report: List[str] = Field(..., description="Report of skills missing from the candidate's profile")


class FreelanceProposal(BaseModel):
    proposal_text: str = Field(..., description="AI generated concise freelance proposal")


class GeneratedResumeContent(TailoredResume):
    pass


class GeneratedProposal(FreelanceProposal):
    pass

