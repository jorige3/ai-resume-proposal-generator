import logging
import os
import sys
from typing import List, Optional

# Ensure the project root is in the Python search path when running Streamlit directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import text

from app.database import get_db_session, Repository
from app.database.models import DbUserProfile, DbGenerationSession
from app.models.schemas import (
    UserProfile,
    WorkExperience,
    Project,
    Education,
    Certification,
    JobDescriptionInput,
    JobAnalysisResult,
    JobMatchScore,
    GeneratedResumeContent,
    GeneratedProposal,
)
from app.services.ollama_client import OllamaClient
from app.services.job_analyzer import analyze_job_description
from app.services.match_calculator import calculate_match_score
from app.services.resume_generator import ResumeGenerator
from app.services.proposal_generator import ProposalGenerator
from app.services.pdf_exporter import export_resume_pdf, export_proposal_pdf, ExportError
from app.services.docx_exporter import export_resume_docx, export_proposal_docx

import re

def get_filename_prefix(full_name: str) -> str:
    """Helper to convert full name to a snake_case filename prefix."""
    name_part = full_name.strip().lower()
    if name_part:
        name_part = re.sub(r'\s+', '_', name_part)
        name_part = re.sub(r'[^a-z0-9_\-]', '', name_part)
        name_part = re.sub(r'_+', '_', name_part).strip('_')
    if not name_part:
        name_part = "candidate"
    return name_part

# Ensure environments are loaded
load_dotenv()

# Initialize Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# --- Front-end Pure Helper Functions (Testable) ---
def get_match_color(score: float) -> str:
    """Returns CSS hex color matching score levels."""
    if score >= 75.0:
        return "#2ecc71"  # Emerald Green
    elif score >= 50.0:
        return "#f39c12"  # Amber Orange
    else:
        return "#e74c3c"  # Crimson Red


def format_experience_text(experiences: List[WorkExperience]) -> str:
    """Formats experiences list into clean human-readable text block."""
    lines = []
    for exp in experiences:
        end = exp.end_date if exp.end_date else "Present"
        lines.append(f"{exp.role} at {exp.company} ({exp.start_date} - {end})")
    return "\n".join(lines) if lines else "No experience items registered."


def check_ollama_health(client: OllamaClient) -> bool:
    """Tests Ollama service availability."""
    return client.health_check()


def check_database_health() -> bool:
    """Tests SQLite connection status."""
    db = None
    try:
        db = get_db_session()
        db.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error("Database health check failed: %s", e)
        return False
    finally:
        if db:
            db.close()


# --- Database CRUD Helpers mapped to Pydantic ---
def db_list_profiles():
    db = get_db_session()
    try:
        repo = Repository(db)
        return repo.list_profiles()
    except Exception as e:
        logger.error("DB Error listing profiles: %s", e)
        return []
    finally:
        db.close()


def db_get_profile(profile_id: int) -> Optional[UserProfile]:
    db = get_db_session()
    try:
        repo = Repository(db)
        db_prof = repo.get_profile(profile_id)
        if db_prof:
            return UserProfile(
                full_name=db_prof.full_name,
                title=db_prof.title,
                email=db_prof.email,
                phone=db_prof.phone,
                skills=db_prof.skills,
                experience=[
                    WorkExperience(**exp) for exp in db_prof.experience
                ],
                projects=[Project(**proj) for proj in db_prof.projects],
                education=[Education(**edu) for edu in db_prof.education],
                certifications=[
                    Certification(**cert) for cert in db_prof.certifications
                ],
            )
        return None
    except Exception as e:
        logger.error("DB Error fetching profile: %s", e)
        return None
    finally:
        db.close()


def db_save_profile(
    profile: UserProfile, profile_id: Optional[int] = None
) -> Optional[int]:
    db = get_db_session()
    try:
        repo = Repository(db)
        if profile_id:
            db_prof = repo.update_profile(profile_id, profile)
        else:
            db_prof = repo.create_profile(profile)
        return db_prof.id
    except Exception as e:
        logger.error("DB Error saving profile: %s", e)
        return None
    finally:
        db.close()


def db_list_sessions(profile_id: int):
    db = get_db_session()
    try:
        repo = Repository(db)
        return repo.list_sessions_by_profile(profile_id)
    except Exception as e:
        logger.error("DB Error listing sessions: %s", e)
        return []
    finally:
        db.close()


def db_save_session(
    profile_id: int,
    job_title: Optional[str],
    job_description: str,
    job_analysis: JobAnalysisResult,
    match_score: JobMatchScore,
    generated_resume: Optional[GeneratedResumeContent] = None,
    generated_proposal: Optional[GeneratedProposal] = None,
) -> Optional[int]:
    db = get_db_session()
    try:
        repo = Repository(db)
        db_sess = repo.create_session(
            profile_id=profile_id,
            job_title=job_title,
            job_description=job_description,
            job_analysis=job_analysis,
            match_score=match_score,
            generated_resume=generated_resume,
            generated_proposal=generated_proposal,
        )
        return db_sess.id
    except Exception as e:
        logger.error("DB Error saving session: %s", e)
        return None
    finally:
        db.close()


def db_delete_session(session_id: int) -> bool:
    db = get_db_session()
    try:
        repo = Repository(db)
        return repo.delete_session(session_id)
    except Exception as e:
        logger.error("DB Error deleting session: %s", e)
        return False
    finally:
        db.close()


def db_get_metrics():
    """Calculates dashboard metrics and recent activity from SQLite."""
    db = get_db_session()
    try:
        profiles_count = db.query(DbUserProfile).count()
        sessions = db.query(DbGenerationSession).all()
        apps_count = len(sessions)
        
        scores = []
        for s in sessions:
            if s.match_score and "overall_score" in s.match_score:
                scores.append(s.match_score["overall_score"])
                
        avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0
        
        from datetime import date
        today = date.today()
        today_count = sum(1 for s in sessions if s.created_at.date() == today)
        
        # Get recent activity
        recent_sessions = sorted(sessions, key=lambda x: x.created_at, reverse=True)[:3]
        recent_activity = []
        for s in recent_sessions:
            recent_activity.append({
                "job_title": s.job_title or "Job Session",
                "time": s.created_at.strftime("%Y-%m-%d %H:%M"),
                "score": s.match_score.get("overall_score", 0) if s.match_score else 0
            })
            
        return {
            "profiles_count": profiles_count,
            "apps_count": apps_count,
            "avg_score": avg_score,
            "today_count": today_count,
            "recent_activity": recent_activity
        }
    except Exception as e:
        logger.error("DB Error calculating metrics: %s", e)
        return {
            "profiles_count": 0,
            "apps_count": 0,
            "avg_score": 0.0,
            "today_count": 0,
            "recent_activity": []
        }
    finally:
        db.close()


# --- Streamlit Presentation Setup ---
def section_header(icon: str, title: str):
    """Helper to render a styled section header separator."""
    st.markdown(
        f"""
        <div class="section-separator">
            <span style="font-size: 1.6rem;">{icon}</span>
            <span class="section-title">{title}</span>
        </div>
        """,
        unsafe_allow_html=True
    )


def run_app():
    st.set_page_config(
        page_title="AI Resume & Proposal Generator", layout="wide"
    )

    # Clean styling definitions
    st.markdown(
        """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&family=Outfit:wght@400;500;600;700;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }
    
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Outfit', sans-serif;
    }
    
    .title-gradient {
        background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 50%, #8B5CF6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
        font-size: 2.8rem;
        margin-bottom: 0.2rem;
        letter-spacing: -1px;
    }
    
    .subtitle {
        font-size: 1.1rem;
        color: #4B5563;
        margin-bottom: 1.5rem;
    }
    
    .section-separator {
        border-bottom: 2px solid #F3F4F6;
        margin-top: 2rem;
        margin-bottom: 1.2rem;
        padding-bottom: 0.4rem;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    
    .section-title {
        font-size: 1.4rem;
        color: #1E3A8A;
        font-weight: 700;
        margin: 0;
    }
    
    .metric-card {
        border-radius: 12px;
        padding: 1.25rem;
        background-color: #FFFFFF;
        border: 1px solid #E5E7EB;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        margin-bottom: 1rem;
        text-align: center;
    }
    
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #1E3A8A;
    }
    
    .metric-label {
        font-size: 0.9rem;
        color: #6B7280;
        font-weight: 500;
    }
    
    .status-badge {
        display: inline-flex;
        align-items: center;
        padding: 0.35rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.85rem;
        font-weight: 600;
        margin-bottom: 0.5rem;
        width: 100%;
        border: 1px solid #E5E7EB;
    }
    
    .status-badge.green {
        background-color: #ECFDF5;
        color: #065F46;
        border-color: #A7F3D0;
    }
    
    .status-badge.red {
        background-color: #FEF2F2;
        color: #991B1B;
        border-color: #FCA5A5;
    }
    
    .recent-activity-item {
        font-size: 0.9rem;
        color: #4B5563;
        padding: 0.5rem 0;
        border-bottom: 1px solid #F3F4F6;
    }
    
    .recent-activity-item:last-child {
        border-bottom: none;
    }
    
    .match-banner {
        border-radius: 12px;
        padding: 1.25rem;
        color: white;
        text-align: center;
        margin-bottom: 1.5rem;
        font-weight: 600;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    </style>
    """,
        unsafe_allow_html=True,
    )

    # Session State Initialization
    if "profile" not in st.session_state:
        st.session_state.profile = UserProfile(
            full_name="",
            title="",
            skills=[],
            experience=[],
            projects=[],
            education=[],
            certifications=[],
        )
    if "active_profile_id" not in st.session_state:
        st.session_state.active_profile_id = None
    if "job_analysis" not in st.session_state:
        st.session_state.job_analysis = None
    if "match_score" not in st.session_state:
        st.session_state.match_score = None
    if "resume_content" not in st.session_state:
        st.session_state.resume_content = None
    if "proposal_content" not in st.session_state:
        st.session_state.proposal_content = None
    if "job_description_input" not in st.session_state:
        st.session_state.job_description_input = ""
    if "job_title" not in st.session_state:
        st.session_state.job_title = ""
    if "is_saved" not in st.session_state:
        st.session_state.is_saved = False
    if "save_success" not in st.session_state:
        st.session_state.save_success = False
    if "load_success" not in st.session_state:
        st.session_state.load_success = None

    # Initialize client
    ollama_client = OllamaClient()
    ollama_ok = check_ollama_health(ollama_client)
    db_ok = check_database_health()
    profile_loaded = st.session_state.active_profile_id is not None

    # --- SIDEBAR CONTROL PANEL ---
    with st.sidebar:
        st.markdown("### 🟢 System Status")
        
        # Ollama connection
        if ollama_ok:
            st.markdown('<div class="status-badge green">🟢 Ollama Connected</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="status-badge red">🔴 Ollama Disconnected</div>', unsafe_allow_html=True)
            
        # Database connection
        if db_ok:
            st.markdown('<div class="status-badge green">🟢 Database Connected</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="status-badge red">🔴 Database Disconnected</div>', unsafe_allow_html=True)
            
        # Profile status
        if profile_loaded:
            st.markdown('<div class="status-badge green">🟢 Profile Loaded</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="status-badge red">🔴 Profile Not Loaded</div>', unsafe_allow_html=True)
            
        st.divider()
        
        st.markdown("### ⚙️ Metadata")
        st.markdown(f"**Model:** `{ollama_client.model}`")
        st.markdown("**Database:** `SQLite`")
        if profile_loaded:
            st.markdown(f"**Profile:** `{st.session_state.profile.full_name}`")
        else:
            st.markdown("**Profile:** `None`")
        st.markdown("**Branch:** `feature/phase-6-ui-improvements`")
        
        st.divider()

        # Candidate Profiles dropdown
        st.markdown("### 📁 Select Profile")
        profiles_list = db_list_profiles()
        options = {"New Profile (Unsaved)": None}
        for p in profiles_list:
            options[f"{p.full_name} - {p.title} (ID: {p.id})"] = p.id

        # Determine index dynamically
        index = 0
        keys_list = list(options.keys())
        if st.session_state.active_profile_id:
            for idx, val in enumerate(options.values()):
                if val == st.session_state.active_profile_id:
                    index = idx
                    break

        selected_label = st.selectbox(
            "Select Candidate Profile", options=keys_list, index=index
        )
        selected_id = options[selected_label]

        # Handle active profile changes
        if selected_id != st.session_state.active_profile_id:
            st.session_state.active_profile_id = selected_id
            if selected_id:
                loaded_prof = db_get_profile(selected_id)
                if loaded_prof:
                    st.session_state.profile = loaded_prof
            else:
                st.session_state.profile = UserProfile(
                    full_name="",
                    title="",
                    skills=[],
                    experience=[],
                    projects=[],
                    education=[],
                    certifications=[],
                )
            # Flush existing matches
            st.session_state.job_analysis = None
            st.session_state.match_score = None
            st.session_state.resume_content = None
            st.session_state.proposal_content = None
            st.session_state.is_saved = False
            st.rerun()

    # --- MAIN VIEW ---
    # Gradient Header
    st.markdown('<div class="title-gradient">AI Resume & Proposal Generator</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Tailor resume points and generate professional proposals targeting specific job details.</div>', unsafe_allow_html=True)

    # Metrics Section
    metrics = db_get_metrics()
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    with m_col1:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-value">{metrics['profiles_count']}</div>
                <div class="metric-label">Candidate Profiles</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    with m_col2:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-value">{metrics['apps_count']}</div>
                <div class="metric-label">Saved Applications</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    with m_col3:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-value">{metrics['avg_score']}%</div>
                <div class="metric-label">Avg Match Score</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    with m_col4:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-value">{metrics['today_count']}</div>
                <div class="metric-label">Today's Sessions</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    # Recent Activity Expander
    if metrics["recent_activity"]:
        with st.expander("⏱️ Recent Activity Logs", expanded=False):
            for act in metrics["recent_activity"]:
                st.markdown(
                    f"""
                    <div class="recent-activity-item">
                        📝 Loaded <b>{act['job_title']}</b> ({act['score']}% Match) saved at <i>{act['time']}</i>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

    st.divider()

    # Dynamic notifications
    if st.session_state.save_success:
        st.success("✅ Application saved successfully.")
        st.session_state.save_success = False

    if st.session_state.load_success:
        st.success(f"✅ {st.session_state.load_success}")
        st.session_state.load_success = None

    # --- SECTION 1: PROFILE ---
    section_header("👤", "Profile")
    with st.expander("Edit Candidate Profile Details", expanded=not profile_loaded):
        st.subheader("Candidate Information")
        col_n, col_t = st.columns(2)
        p_name = col_n.text_input(
            "Full Name", value=st.session_state.profile.full_name, key="profile_full_name_input"
        )
        p_title = col_t.text_input(
            "Professional Title", value=st.session_state.profile.title, key="profile_title_input"
        )

        col_e, col_p = st.columns(2)
        p_email = col_e.text_input(
            "Email Address", value=st.session_state.profile.email or "", key="profile_email_input"
        )
        p_phone = col_p.text_input(
            "Phone Number", value=st.session_state.profile.phone or "", key="profile_phone_input"
        )

        p_skills_str = st.text_area(
            "Skills (comma-separated)",
            value=", ".join(st.session_state.profile.skills),
            placeholder="e.g. Python, SQL, REST APIs, Git",
            key="profile_skills_input"
        )

        st.session_state.profile.full_name = p_name
        st.session_state.profile.title = p_title
        st.session_state.profile.email = p_email.strip() if p_email.strip() else None
        st.session_state.profile.phone = p_phone.strip() if p_phone.strip() else None
        st.session_state.profile.skills = [
            s.strip() for s in p_skills_str.split(",") if s.strip()
        ]

        st.divider()

        # Experience Nested Lists
        st.subheader("Work Experience")
        for i, exp in enumerate(st.session_state.profile.experience):
            with st.expander(
                f"💼 {exp.role} at {exp.company} ({exp.start_date} - {exp.end_date or 'Present'})"
            ):
                st.write(exp.description)
                if st.button(
                    f"Remove Work Experience {i+1}", key=f"rem_exp_{i}"
                ):
                    st.session_state.profile.experience.pop(i)
                    st.session_state.is_saved = False
                    st.rerun()

        with st.form("add_exp_form", clear_on_submit=True):
            st.markdown("##### Add Work Experience")
            comp = st.text_input("Company")
            role = st.text_input("Role / Headline")
            start = st.text_input("Start Date (e.g. 2021-01)")
            end = st.text_input("End Date (e.g. 2023-01 or Present)")
            desc = st.text_area("Responsibilities & Accomplishments")

            submitted_exp = st.form_submit_button("Add Experience")
            if submitted_exp:
                if comp and role and start and desc:
                    new_exp = WorkExperience(
                        company=comp,
                        role=role,
                        start_date=start,
                        end_date=end if end else "Present",
                        description=desc,
                    )
                    st.session_state.profile.experience.append(new_exp)
                    st.session_state.is_saved = False
                    st.success("Experience added!")
                    st.rerun()
                else:
                    st.error("Please fill in Company, Role, Start, and Description.")

        st.divider()

        # Projects Nested Lists
        st.subheader("Projects")
        for i, proj in enumerate(st.session_state.profile.projects):
            tech_s = ", ".join(proj.technologies)
            with st.expander(
                f"🚀 {proj.title} (Technologies: {tech_s})"
            ):
                st.write(proj.description)
                if proj.url:
                    st.write(f"[Project URL]({proj.url})")
                if st.button(f"Remove Project {i+1}", key=f"rem_proj_{i}"):
                    st.session_state.profile.projects.pop(i)
                    st.session_state.is_saved = False
                    st.rerun()

        with st.form("add_proj_form", clear_on_submit=True):
            st.markdown("##### Add Project")
            title = st.text_input("Project Title")
            desc_proj = st.text_area("Description")
            tech_proj = st.text_input("Technologies (comma-separated)")
            url_proj = st.text_input("Project URL (Optional)")

            submitted_proj = st.form_submit_button("Add Project")
            if submitted_proj:
                if title and desc_proj:
                    new_proj = Project(
                        title=title,
                        description=desc_proj,
                        technologies=[
                            t.strip() for t in tech_proj.split(",") if t.strip()
                        ],
                        url=url_proj if url_proj.strip() else None,
                    )
                    st.session_state.profile.projects.append(new_proj)
                    st.session_state.is_saved = False
                    st.success("Project added!")
                    st.rerun()
                else:
                    st.error("Please fill in Project Title and Description.")

        st.divider()

        # Education and Certifications Side-by-Side
        col_edu, col_cert = st.columns(2)
        with col_edu:
            st.subheader("Education")
            for i, edu in enumerate(st.session_state.profile.education):
                grad_s = (
                    f" (Graduated: {edu.graduation_year})"
                    if edu.graduation_year
                    else ""
                )
                st.markdown(
                    f"- **{edu.degree}** in **{edu.field_of_study}**  \n*{edu.institution}*{grad_s}"
                )
                if st.button(f"Remove Education {i+1}", key=f"rem_edu_{i}"):
                    st.session_state.profile.education.pop(i)
                    st.session_state.is_saved = False
                    st.rerun()

            with st.form("add_edu_form", clear_on_submit=True):
                st.markdown("##### Add Education")
                inst = st.text_input("School / University")
                deg = st.text_input("Degree")
                fos = st.text_input("Field of Study")
                grad = st.number_input(
                    "Graduation Year",
                    min_value=1950,
                    max_value=2050,
                    value=2023,
                )

                submitted_edu = st.form_submit_button("Add Education")
                if submitted_edu:
                    if inst and deg and fos:
                        new_edu = Education(
                            institution=inst,
                            degree=deg,
                            field_of_study=fos,
                            graduation_year=int(grad),
                        )
                        st.session_state.profile.education.append(new_edu)
                        st.session_state.is_saved = False
                        st.success("Education added!")
                        st.rerun()

        with col_cert:
            st.subheader("Certifications")
            for i, cert in enumerate(st.session_state.profile.certifications):
                yr_s = f" ({cert.year})" if cert.year else ""
                st.markdown(
                    f"- **{cert.name}** issued by **{cert.issuing_org}**{yr_s}"
                )
                if st.button(
                    f"Remove Certification {i+1}", key=f"rem_cert_{i}"
                ):
                    st.session_state.profile.certifications.pop(i)
                    st.session_state.is_saved = False
                    st.rerun()

            with st.form("add_cert_form", clear_on_submit=True):
                st.markdown("##### Add Certification")
                c_name = st.text_input("Certification Name")
                c_org = st.text_input("Issuing Organization")
                c_yr = st.number_input(
                    "Year Issued", min_value=1950, max_value=2050, value=2023
                )

                submitted_cert = st.form_submit_button("Add Certification")
                if submitted_cert:
                    if c_name and c_org:
                        new_cert = Certification(
                            name=c_name,
                            issuing_org=c_org,
                            year=int(c_yr),
                        )
                        st.session_state.profile.certifications.append(new_cert)
                        st.session_state.is_saved = False
                        st.success("Certification added!")
                        st.rerun()

        st.divider()

        # Database save trigger
        if st.button("💾 Save Profile to Database", type="primary", key="save_profile_btn_top"):
            if (
                not st.session_state.profile.full_name
                or not st.session_state.profile.title
            ):
                st.error("Name and Professional Title are required to save.")
            else:
                saved_prof_id = db_save_profile(
                    st.session_state.profile, st.session_state.active_profile_id
                )
                if saved_prof_id:
                    st.session_state.active_profile_id = saved_prof_id
                    st.session_state.is_saved = False
                    st.success("Profile saved successfully!")
                    st.rerun()
                else:
                    st.error("Failed to save profile. Check SQLite connection.")

    # --- SECTION 2: JOB MATCHING ---
    section_header("💼", "Job Matching")
    with st.container(border=True):
        st.session_state.job_title = st.text_input(
            "Job Title Reference",
            value=st.session_state.job_title,
            placeholder="e.g. Senior Backend Engineer",
            key="job_title_match_input"
        )

        st.session_state.job_description_input = st.text_area(
            "Paste Job Description Here",
            value=st.session_state.job_description_input,
            height=200,
            placeholder="Paste text contents...",
            key="job_desc_match_input"
        )

        col_m, col_g = st.columns(2)
        with col_m:
            if st.button("🔍 Match Job Description & Profile", type="primary", width="stretch", key="run_match_btn"):
                if not st.session_state.job_description_input.strip():
                    st.error("Please insert a job description.")
                else:
                    with st.spinner("Analyzing requirements..."):
                        parsed_analysis = analyze_job_description(
                            st.session_state.job_description_input
                        )
                        st.session_state.job_analysis = parsed_analysis

                        calculated_score = calculate_match_score(
                            st.session_state.profile, parsed_analysis
                        )
                        st.session_state.match_score = calculated_score
                        st.session_state.is_saved = False
                        st.success("Match Score analysis complete!")
                        st.rerun()
                        
        with col_g:
            match_ready = st.session_state.job_analysis is not None and st.session_state.match_score is not None
            if st.button("✨ Generate Tailored Assets", type="secondary", disabled=not match_ready, width="stretch", key="run_generate_btn"):
                if not ollama_ok:
                    st.error("Ollama is not running. Start Ollama model to generate AI content.")
                else:
                    # Sequential loaders
                    with st.spinner("Analyzing job description..."):
                        import time
                        time.sleep(0.5)
                        
                    with st.spinner("Generating tailored resume..."):
                        res_builder = ResumeGenerator(ollama_client)
                        tailored_resume = res_builder.generate_resume(
                            st.session_state.profile,
                            st.session_state.job_analysis,
                        )
                        st.session_state.resume_content = tailored_resume
                        
                    with st.spinner("Generating freelance proposal..."):
                        prop_builder = ProposalGenerator(ollama_client)
                        job_in = JobDescriptionInput(
                            text=st.session_state.job_description_input
                        )
                        tailored_proposal = prop_builder.generate_proposal(
                            st.session_state.profile,
                            job_in,
                            st.session_state.job_analysis,
                            st.session_state.match_score,
                        )
                        st.session_state.proposal_content = tailored_proposal
                        
                    st.session_state.is_saved = False
                    st.success("Assets tailored successfully!")
                    st.rerun()

        # Display matching calculations
        if st.session_state.match_score and st.session_state.job_analysis:
            score = st.session_state.match_score
            analysis = st.session_state.job_analysis

            st.divider()

            # Render Score Banner
            color = get_match_color(score.overall_score)
            st.markdown(
                f'<div class="match-banner" style="background-color: {color};">'
                f'<span style="font-size: 1.6rem; font-weight: bold;">Match Compatibility: {score.overall_score}%</span>'
                f'<br/><span style="font-size: 0.95rem;">{score.explanation}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("#### Skills Mapping Breakdown")
                st.write(
                    "**Matched Required:**",
                    ", ".join(score.matched_required_skills)
                    if score.matched_required_skills
                    else "None",
                )
                st.write(
                    "**Missing Required:**",
                    ", ".join(score.missing_required_skills)
                    if score.missing_required_skills
                    else "None",
                )
                st.write(
                    "**Matched Preferred:**",
                    ", ".join(score.matched_preferred_skills)
                    if score.matched_preferred_skills
                    else "None",
                )
                st.write(
                    "**Missing Preferred:**",
                    ", ".join(score.missing_preferred_skills)
                    if score.missing_preferred_skills
                    else "None",
                )

            with col2:
                st.markdown("#### Job Requirements")
                st.write(
                    "**Required Years:**",
                    f"{score.required_experience_years} years"
                    if score.required_experience_years
                    else "Not specified",
                )
                st.write(
                    "**Extracted Keywords:**",
                    ", ".join(analysis.keywords)
                    if analysis.keywords
                    else "None",
                )
                st.write("**Extracted Responsibilities:**")
                for r in analysis.responsibilities[:5]:
                    st.markdown(f"- {r}")
                if len(analysis.responsibilities) > 5:
                    st.markdown(
                        f"*... and {len(analysis.responsibilities) - 5} more.*"
                    )

    # --- SECTION 3: AI RESUME GENERATOR ---
    section_header("🤖", "AI Resume Generator")
    if not st.session_state.resume_content:
        st.info("Tailored resume content will be displayed here after you click 'Generate Tailored Assets' in the Job Matching section.")
    else:
        res_output = st.session_state.resume_content
        with st.container(border=True):
            # Download buttons for Resume
            try:
                pdf_data = export_resume_pdf(
                    st.session_state.profile,
                    res_output,
                    st.session_state.match_score
                )
                docx_data = export_resume_docx(
                    st.session_state.profile,
                    res_output,
                    st.session_state.match_score
                )
                
                prefix = get_filename_prefix(st.session_state.profile.full_name)
                pdf_filename = f"{prefix}_tailored_resume.pdf"
                docx_filename = f"{prefix}_tailored_resume.docx"
                
                col_btn1, col_btn2 = st.columns(2)
                col_btn1.download_button(
                    label="📄 Download Resume PDF",
                    data=pdf_data,
                    file_name=pdf_filename,
                    mime="application/pdf",
                    key="dl_resume_pdf_dash",
                    width="stretch"
                )
                col_btn2.download_button(
                    label="📄 Download Resume DOCX",
                    data=docx_data,
                    file_name=docx_filename,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key="dl_resume_docx_dash",
                    width="stretch"
                )
            except ExportError as e:
                st.error(f"Failed to prepare resume exports: {e}")
            except Exception:
                logger.exception("Resume export generation failed")
                st.error("Failed to prepare resume exports due to an unexpected error.")

            st.markdown("#### Tailored Professional Summary")
            st.info(res_output.professional_summary)

            st.markdown("#### Tailored Focus Skills")
            st.write(", ".join(res_output.tailored_skills))

            st.markdown("#### Improvement Suggestions")
            for sug in res_output.improvement_suggestions:
                st.markdown(f"- {sug}")

            st.markdown("#### Missing Skills Report")
            for rep in res_output.missing_skills_report:
                st.markdown(f"- {rep}")

    # --- SECTION 4: PROPOSAL GENERATOR ---
    section_header("📑", "Proposal Generator")
    if not st.session_state.proposal_content:
        st.info("Tailored freelance proposal will be displayed here after you click 'Generate Tailored Assets' in the Job Matching section.")
    else:
        prop_output = st.session_state.proposal_content
        with st.container(border=True):
            # Download buttons for Proposal
            try:
                proposal_pdf = export_proposal_pdf(
                    st.session_state.profile,
                    prop_output,
                    st.session_state.match_score
                )
                proposal_docx = export_proposal_docx(
                    st.session_state.profile,
                    prop_output,
                    st.session_state.match_score
                )
                
                prefix = get_filename_prefix(st.session_state.profile.full_name)
                pdf_filename = f"{prefix}_proposal.pdf"
                docx_filename = f"{prefix}_proposal.docx"
                
                col_pbtn1, col_pbtn2 = st.columns(2)
                col_pbtn1.download_button(
                    label="📄 Download Proposal PDF",
                    data=proposal_pdf,
                    file_name=pdf_filename,
                    mime="application/pdf",
                    key="dl_proposal_pdf_dash",
                    width="stretch"
                )
                col_pbtn2.download_button(
                    label="📄 Download Proposal DOCX",
                    data=proposal_docx,
                    file_name=docx_filename,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key="dl_proposal_docx_dash",
                    width="stretch"
                )
            except ExportError as e:
                st.error(f"Failed to prepare proposal exports: {e}")
            except Exception:
                logger.exception("Proposal export generation failed")
                st.error("Failed to prepare proposal exports due to an unexpected error.")

            st.text_area(
                "Proposal Text (Copy Ready)",
                value=prop_output.proposal_text,
                height=400,
                key="prop_text_dash_disp"
            )

    # --- SAVE APPLICATION TRIGGER ---
    if st.session_state.resume_content and st.session_state.proposal_content:
        st.divider()
        col_save_btn, col_status = st.columns([1, 2])
        with col_save_btn:
            save_disabled = st.session_state.get("is_saved", False)
            if not st.session_state.active_profile_id:
                st.button("💾 Save Application", disabled=True, help="Save Candidate Profile first")
            else:
                if st.button("💾 Save Application", key="save_app_btn_dash", disabled=save_disabled, type="primary", width="stretch"):
                    with st.spinner("Saving application..."):
                        saved_sess_id = db_save_session(
                            profile_id=st.session_state.active_profile_id,
                            job_title=(
                                st.session_state.job_title
                                if st.session_state.job_title
                                else "Application Session"
                            ),
                            job_description=st.session_state.job_description_input,
                            job_analysis=st.session_state.job_analysis,
                            match_score=st.session_state.match_score,
                            generated_resume=st.session_state.resume_content,
                            generated_proposal=st.session_state.proposal_content,
                        )
                        if saved_sess_id:
                            st.session_state.is_saved = True
                            st.session_state.save_success = True
                            st.rerun()
                        else:
                            st.error("Failed to save session. Database error.")
        with col_status:
            if st.session_state.get("is_saved", False):
                st.markdown("<div style='padding-top: 10px; color: green; font-weight: bold;'>✅ Saved to Applications Database</div>", unsafe_allow_html=True)
            else:
                st.markdown("<div style='padding-top: 10px; color: orange;'>⚠️ Unsaved Generation Session</div>", unsafe_allow_html=True)

    # --- SECTION 5: SAVED APPLICATIONS ---
    section_header("📚", "Saved Applications")
    if not st.session_state.active_profile_id:
        st.info("Please select or save a candidate profile to view application history.")
    else:
        sessions = db_list_sessions(st.session_state.active_profile_id)
        if not sessions:
            st.info("No saved applications found for this profile.")
        else:
            cols = st.columns(3)
            for idx, s in enumerate(sessions):
                col = cols[idx % 3]
                with col.container(border=True):
                    st.markdown(f"#### {s.job_title or 'Job'}")
                    overall_score = s.match_score.get("overall_score", 0) if s.match_score else 0
                    st.markdown(f"**Score:** {overall_score}% Match")
                    st.markdown(f"*Saved: {s.created_at.strftime('%Y-%m-%d %H:%M')}*")
                    
                    c_load, c_del = st.columns(2)
                    if c_load.button("📂 Load", key=f"load_s_dash_{s.id}", width="stretch"):
                        st.session_state.job_title = s.job_title or ""
                        st.session_state.job_description_input = s.job_description
                        st.session_state.job_analysis = JobAnalysisResult(**s.job_analysis)
                        st.session_state.match_score = JobMatchScore(**s.match_score)
                        st.session_state.resume_content = (
                            GeneratedResumeContent(**s.generated_resume)
                            if s.generated_resume
                            else None
                        )
                        st.session_state.proposal_content = (
                            GeneratedProposal(**s.generated_proposal)
                            if s.generated_proposal
                            else None
                        )
                        st.session_state.is_saved = True
                        st.session_state.load_success = f"Loaded application details for '{s.job_title}'."
                        st.rerun()
                        
                    if c_del.button("🗑️ Delete", key=f"del_s_dash_{s.id}", width="stretch"):
                        with st.spinner("Deleting application..."):
                            if db_delete_session(s.id):
                                st.session_state.is_saved = False
                                st.session_state.load_success = "Application removed successfully."
                                st.rerun()


# Run the application when runtime is active
if st.runtime.exists():
    run_app()
