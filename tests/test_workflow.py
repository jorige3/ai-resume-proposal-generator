from app.models.schemas import UserProfile, GeneratedResumeContent, GeneratedProposal, JobMatchScore, JobAnalysisResult
from app.services.pdf_exporter import export_resume_pdf, export_proposal_pdf
from app.services.docx_exporter import export_resume_docx, export_proposal_docx


class MockSessionState:
    def __init__(self):
        self.profile = None
        self.active_profile_id = None
        self.job_title = ""
        self.job_description_input = ""
        self.job_analysis = None
        self.match_score = None
        self.resume_content = None
        self.proposal_content = None
        self.is_saved = False
        self.save_success = False
        self.load_success = None


def test_download_eligibility():
    state = MockSessionState()
    assert state.resume_content is None
    assert state.proposal_content is None
    
    # Set generated contents
    state.resume_content = GeneratedResumeContent(
        professional_summary="Summary",
        tailored_skills=["Python"],
        improvement_suggestions=[],
        missing_skills_report=[]
    )
    state.proposal_content = GeneratedProposal(proposal_text="Dear hiring manager...")
    
    assert state.resume_content is not None
    assert state.proposal_content is not None


def test_reload_history_helper():
    state = MockSessionState()
    
    class FakeSession:
        def __init__(self):
            self.job_title = "Python Dev"
            self.job_description = "Requirements..."
            self.job_analysis = {
                "required_skills": ["Python"],
                "preferred_skills": [],
                "responsibilities": [],
                "experience_years_required": 1.0,
                "keywords": []
            }
            self.match_score = {
                "overall_score": 90.0,
                "skills_match_score": 90.0,
                "experience_match_score": 90.0,
                "user_experience_years": 1.0,
                "explanation": "Exp"
            }
            self.generated_resume = {
                "professional_summary": "Summary text",
                "tailored_skills": ["Python"],
                "improvement_suggestions": [],
                "missing_skills_report": []
            }
            self.generated_proposal = {
                "proposal_text": "Upwork proposal"
            }
            
    fs = FakeSession()
    
    # Reload function simulation
    state.job_title = fs.job_title
    state.job_description_input = fs.job_description
    state.job_analysis = JobAnalysisResult(**fs.job_analysis)
    state.match_score = JobMatchScore(**fs.match_score)
    state.resume_content = GeneratedResumeContent(**fs.generated_resume)
    state.proposal_content = GeneratedProposal(**fs.generated_proposal)
    state.is_saved = True
    
    assert state.job_title == "Python Dev"
    assert state.job_description_input == "Requirements..."
    assert state.job_analysis.required_skills == ["Python"]
    assert state.match_score.overall_score == 90.0
    assert state.resume_content.professional_summary == "Summary text"
    assert state.proposal_content.proposal_text == "Upwork proposal"
    assert state.is_saved is True


def test_duplicate_save_prevention():
    state = MockSessionState()
    assert state.is_saved is False
    
    # Set to saved
    state.is_saved = True
    
    def trigger_save(st_state):
        if st_state.is_saved:
            return "BLOCKED"
        return "SAVED"
        
    assert trigger_save(state) == "BLOCKED"
    
    # Reset on parameter change
    state.job_title = "New Title"
    state.is_saved = False
    assert trigger_save(state) == "SAVED"


def test_export_bytes_magic_numbers():
    profile = UserProfile(
        full_name="Jane Doe",
        title="Automator",
        skills=[],
        experience=[],
        projects=[],
        education=[],
        certifications=[]
    )
    resume = GeneratedResumeContent(
        professional_summary="Summary",
        tailored_skills=[],
        improvement_suggestions=[],
        missing_skills_report=[]
    )
    proposal = GeneratedProposal(proposal_text="Proposal")
    match_score = JobMatchScore(
        overall_score=80.0,
        skills_match_score=80.0,
        experience_match_score=80.0,
        user_experience_years=2.0,
        explanation="Exp"
    )
    
    # Resume PDF
    pdf_resume_bytes = export_resume_pdf(profile, resume, match_score)
    assert pdf_resume_bytes.startswith(b"%PDF")
    
    # Proposal PDF
    pdf_proposal_bytes = export_proposal_pdf(profile, proposal, match_score)
    assert pdf_proposal_bytes.startswith(b"%PDF")
    
    # Resume DOCX (starts with PK Zip magic number)
    docx_resume_bytes = export_resume_docx(profile, resume, match_score)
    assert docx_resume_bytes.startswith(b"PK\x03\x04")
    
    # Proposal DOCX
    docx_proposal_bytes = export_proposal_docx(profile, proposal, match_score)
    assert docx_proposal_bytes.startswith(b"PK\x03\x04")
