import pytest
from app.models.schemas import UserProfile, WorkExperience, Project, Education, Certification, GeneratedResumeContent, GeneratedProposal, JobMatchScore
from app.services.pdf_exporter import export_resume_pdf, export_proposal_pdf, ExportError, sanitize_filename
from app.services.docx_exporter import export_resume_docx, export_proposal_docx
from app.main import get_filename_prefix


def test_sanitize_filename():
    assert sanitize_filename("hello world.pdf") == "hello_world.pdf"
    assert sanitize_filename("hello@world!.docx") == "hello_world.docx"
    assert sanitize_filename("test") == "test"
    assert sanitize_filename("") == "document"


def test_get_filename_prefix():
    assert get_filename_prefix("John Doe") == "john_doe"
    assert get_filename_prefix("   Jane   Smith  ") == "jane_smith"
    assert get_filename_prefix("Special Characters @#$") == "special_characters"
    assert get_filename_prefix("") == "candidate"


@pytest.fixture
def sample_data():
    profile = UserProfile(
        full_name="John Doe",
        title="Software Engineer",
        email="john.doe@example.com",
        phone="+123456789",
        skills=["Python", "Go", "Docker"],
        experience=[
            WorkExperience(
                company="Tech Co",
                role="Backend Dev",
                start_date="2020-01",
                end_date="2022-12",
                description="Developing backend microservices in Go and Python.\n- Improved performance by 20%.\n- Mentored junior devs."
            )
        ],
        projects=[
            Project(
                title="AI Generator",
                description="Created an automated generator tool.",
                technologies=["Python", "Streamlit"],
                url="https://github.com/john/ai-gen"
            )
        ],
        education=[
            Education(
                institution="University of Tech",
                degree="B.S.",
                field_of_study="Computer Science",
                graduation_year=2019
            )
        ],
        certifications=[
            Certification(
                name="AWS Solutions Architect",
                issuing_org="Amazon",
                year=2021
            )
        ]
    )
    
    resume = GeneratedResumeContent(
        professional_summary="Highly skilled engineer with experience in cloud architectures and Python backend development.",
        tailored_skills=["Python", "Go"],
        improvement_suggestions=["Add more details about Docker projects."],
        missing_skills_report=["Familiarity with Kubernetes is preferred."]
    )
    
    proposal = GeneratedProposal(
        proposal_text="Dear Hiring Team,\n\nI am writing to express my interest in the Software Engineer position. Based on my experience..."
    )
    
    match_score = JobMatchScore(
        overall_score=85.0,
        skills_match_score=80.0,
        experience_match_score=90.0,
        user_experience_years=3.0,
        explanation="Strong technical match."
    )
    
    return profile, resume, proposal, match_score


def test_export_resume_pdf_success(sample_data):
    profile, resume, _, match_score = sample_data
    pdf_bytes = export_resume_pdf(profile, resume, match_score)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0


def test_export_resume_docx_success(sample_data):
    profile, resume, _, match_score = sample_data
    docx_bytes = export_resume_docx(profile, resume, match_score)
    assert isinstance(docx_bytes, bytes)
    assert len(docx_bytes) > 0


def test_export_proposal_pdf_success(sample_data):
    profile, _, proposal, match_score = sample_data
    pdf_bytes = export_proposal_pdf(profile, proposal, match_score)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0


def test_export_proposal_docx_success(sample_data):
    profile, _, proposal, match_score = sample_data
    docx_bytes = export_proposal_docx(profile, proposal, match_score)
    assert isinstance(docx_bytes, bytes)
    assert len(docx_bytes) > 0


def test_missing_optional_fields_pdf(sample_data):
    profile, resume, proposal, _ = sample_data
    profile.email = None
    profile.phone = None
    profile.experience = []
    profile.projects = []
    profile.education = []
    profile.certifications = []
    
    resume.improvement_suggestions = []
    resume.missing_skills_report = []
    
    pdf_resume = export_resume_pdf(profile, resume, None)
    assert len(pdf_resume) > 0
    
    pdf_proposal = export_proposal_pdf(profile, proposal, None)
    assert len(pdf_proposal) > 0


def test_missing_optional_fields_docx(sample_data):
    profile, resume, proposal, _ = sample_data
    profile.email = None
    profile.phone = None
    profile.experience = []
    profile.projects = []
    profile.education = []
    profile.certifications = []
    
    resume.improvement_suggestions = []
    resume.missing_skills_report = []
    
    docx_resume = export_resume_docx(profile, resume, None)
    assert len(docx_resume) > 0
    
    docx_proposal = export_proposal_docx(profile, proposal, None)
    assert len(docx_proposal) > 0


def test_invalid_content_raises_export_error(sample_data):
    profile, resume, proposal, _ = sample_data
    
    # 1. Empty candidate name
    profile.full_name = ""
    with pytest.raises(ExportError, match="Candidate full name cannot be empty."):
        export_resume_pdf(profile, resume)
    with pytest.raises(ExportError, match="Candidate full name cannot be empty."):
        export_resume_docx(profile, resume)
    with pytest.raises(ExportError, match="Candidate full name cannot be empty."):
        export_proposal_pdf(profile, proposal)
    with pytest.raises(ExportError, match="Candidate full name cannot be empty."):
        export_proposal_docx(profile, proposal)
        
    profile.full_name = "John"
    
    # 2. Empty professional summary
    resume.professional_summary = ""
    with pytest.raises(ExportError, match="Resume professional summary cannot be empty."):
        export_resume_pdf(profile, resume)
    with pytest.raises(ExportError, match="Resume professional summary cannot be empty."):
        export_resume_docx(profile, resume)
        
    # 3. Empty proposal text
    proposal.proposal_text = ""
    with pytest.raises(ExportError, match="Proposal text content cannot be empty."):
        export_proposal_pdf(profile, proposal)
    with pytest.raises(ExportError, match="Proposal text content cannot be empty."):
        export_proposal_docx(profile, proposal)
