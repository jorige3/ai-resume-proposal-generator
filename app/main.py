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


# --- Streamlit Presentation Setup ---
def run_app():
    st.set_page_config(
        page_title="AI Resume & Proposal Generator", layout="wide"
    )

    # Clean styling definitions
    st.markdown(
        """
    <style>
    .title-gradient {
        background: linear-gradient(90deg, #4A00E0, #8E2DE2);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
        font-size: 2.8rem;
        margin-bottom: 0.5rem;
    }
    .metric-container {
        border-radius: 8px;
        padding: 15px;
        color: white;
        text-align: center;
        margin-bottom: 20px;
    }
    </style>
    """,
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="title-gradient">AI Resume & Proposal Generator</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        "Tailor resume points and generate professional proposals targeting specific job details."
    )
    st.divider()

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

    # Initialize client
    ollama_client = OllamaClient()

    # --- SIDEBAR CONTROL PANEL ---
    with st.sidebar:
        st.header("Control Panel")

        # 1. Verification Health Lights
        st.subheader("System Status")
        ollama_ok = check_ollama_health(ollama_client)
        db_ok = check_database_health()

        o_emoji = "🟢" if ollama_ok else "🔴"
        d_emoji = "🟢" if db_ok else "🔴"

        st.markdown(f"{o_emoji} **Ollama Connection**")
        st.markdown(f"{d_emoji} **Database (SQLite)**")
        st.divider()

        # 2. Candidate Profiles dropdown
        st.subheader("Active Profiles")
        profiles_list = db_list_profiles()
        options = {"New Profile (Unsaved)": None}
        for p in profiles_list:
            options[f"{p.full_name} - {p.title} (ID: {p.id})"] = p.id

        selected_label = st.selectbox(
            "Select Profile", options=list(options.keys())
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
            st.rerun()

        st.divider()

        # 3. List Saved Sessions
        st.subheader("Application History")
        if st.session_state.active_profile_id:
            sessions = db_list_sessions(st.session_state.active_profile_id)
            if sessions:
                for s in sessions:
                    date_str = s.created_at.strftime("%Y-%m-%d %H:%M")
                    col1, col2 = st.columns([5, 1])
                    if col1.button(
                        f"📁 {s.job_title or 'Job'} ({date_str})",
                        key=f"load_s_{s.id}",
                        width="stretch",
                    ):
                        st.session_state.job_title = s.job_title or ""
                        st.session_state.job_description_input = (
                            s.job_description
                        )
                        st.session_state.job_analysis = JobAnalysisResult(
                            **s.job_analysis
                        )
                        st.session_state.match_score = JobMatchScore(
                            **s.match_score
                        )
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
                        st.success(f"Loaded application history for {s.job_title}!")
                        st.rerun()
                    if col2.button("🗑️", key=f"del_s_{s.id}"):
                        if db_delete_session(s.id):
                            st.success("Session removed.")
                            st.rerun()
            else:
                st.info("No applications saved for this profile.")
        else:
            st.info("Save profile first to track history.")

    # --- MAIN VIEW TABS ---
    tab_profile, tab_match, tab_ai = st.tabs(
        ["👤 Profile Editor", "🔍 Job Matching", "✍️ AI Content Generator"]
    )

    # --- TAB 1: PROFILE EDITOR ---
    with tab_profile:
        st.subheader("Candidate Information")
        col_n, col_t = st.columns(2)
        p_name = col_n.text_input(
            "Full Name", value=st.session_state.profile.full_name
        )
        p_title = col_t.text_input(
            "Professional Title", value=st.session_state.profile.title
        )

        col_e, col_p = st.columns(2)
        p_email = col_e.text_input(
            "Email Address", value=st.session_state.profile.email or ""
        )
        p_phone = col_p.text_input(
            "Phone Number", value=st.session_state.profile.phone or ""
        )

        p_skills_str = st.text_area(
            "Skills (comma-separated)",
            value=", ".join(st.session_state.profile.skills),
            placeholder="e.g. Python, SQL, REST APIs, Git",
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
                        st.success("Certification added!")
                        st.rerun()

        st.divider()

        # Database save trigger
        if st.button("💾 Save Profile to Database", type="primary"):
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
                    st.success("Profile saved successfully!")
                    st.rerun()
                else:
                    st.error("Failed to save profile. Check SQLite connection.")

    # --- TAB 2: JOB DESCRIPTION & MATCH ---
    with tab_match:
        st.subheader("Job Reference Details")
        st.session_state.job_title = st.text_input(
            "Job Title Reference",
            value=st.session_state.job_title,
            placeholder="e.g. Senior Backend Engineer",
        )

        st.session_state.job_description_input = st.text_area(
            "Paste Job Description Here",
            value=st.session_state.job_description_input,
            height=300,
            placeholder="Paste text contents...",
        )

        if st.button("🔍 Match Job Description & Profile", type="primary"):
            if not st.session_state.job_description_input.strip():
                st.error("Please insert a job description.")
            else:
                with st.spinner("Analyzing requirements..."):
                    # 1. Parse jd
                    parsed_analysis = analyze_job_description(
                        st.session_state.job_description_input
                    )
                    st.session_state.job_analysis = parsed_analysis

                    # 2. Score calculations
                    calculated_score = calculate_match_score(
                        st.session_state.profile, parsed_analysis
                    )
                    st.session_state.match_score = calculated_score
                    st.success("Match Score analysis complete!")
                    st.rerun()

        if st.session_state.match_score and st.session_state.job_analysis:
            score = st.session_state.match_score
            analysis = st.session_state.job_analysis

            st.divider()

            # Render Score Banner
            color = get_match_color(score.overall_score)
            st.markdown(
                f'<div class="metric-container" style="background-color: {color};">'
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

    # --- TAB 3: AI CONTENT GENERATION ---
    with tab_ai:
        st.subheader("Generate Tailored Assets")

        if not st.session_state.job_analysis or not st.session_state.match_score:
            st.warning("Analyze a job description first (Tab 2) to build matching facts.")
        else:
            if st.button("✨ Call AI to Generate Tailored Assets", type="primary"):
                if not ollama_ok:
                    st.error("Ollama is not running. Start Ollama model to generate AI content.")
                else:
                    with st.spinner("Tailoring content (calling Ollama local AI)..."):
                        try:
                            # 1. Resume Generator
                            res_builder = ResumeGenerator(ollama_client)
                            tailored_resume = res_builder.generate_resume(
                                st.session_state.profile,
                                st.session_state.job_analysis,
                            )
                            st.session_state.resume_content = tailored_resume

                            # 2. Proposal Generator
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

                            st.success("Assets tailored successfully!")
                            st.rerun()
                        except Exception as ex:
                            st.error(f"Failed to generate assets: {ex}")
                            logger.error("Ollama AI call failed: %s", ex)

            # Display generated output
            if (
                st.session_state.resume_content
                and st.session_state.proposal_content
            ):
                res_output = st.session_state.resume_content
                prop_output = st.session_state.proposal_content

                st.divider()

                # Save Results Trigger
                if st.button(
                    "💾 Save Assets and Session to Database",
                    key="save_sess_btn",
                ):
                    if not st.session_state.active_profile_id:
                        st.error(
                            "Please save the Candidate Profile (Tab 1) before storing applications."
                        )
                    else:
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
                            generated_resume=res_output,
                            generated_proposal=prop_output,
                        )
                        if saved_sess_id:
                            st.success(
                                "Application session stored successfully!"
                            )
                            st.rerun()
                        else:
                            st.error("Failed to save session. Database error.")

                st.divider()

                col_resume, col_proposal = st.columns(2)

                with col_resume:
                    st.markdown("### Tailored Resume Details")

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
                            label="📥 PDF Resume",
                            data=pdf_data,
                            file_name=pdf_filename,
                            mime="application/pdf",
                            key="dl_resume_pdf"
                        )
                        col_btn2.download_button(
                            label="📥 Word Resume",
                            data=docx_data,
                            file_name=docx_filename,
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            key="dl_resume_docx"
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

                with col_proposal:
                    st.markdown("### Freelance Proposal")

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
                            label="📥 PDF Proposal",
                            data=proposal_pdf,
                            file_name=pdf_filename,
                            mime="application/pdf",
                            key="dl_proposal_pdf"
                        )
                        col_pbtn2.download_button(
                            label="📥 Word Proposal",
                            data=proposal_docx,
                            file_name=docx_filename,
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            key="dl_proposal_docx"
                        )
                    except ExportError as e:
                        st.error(f"Failed to prepare proposal exports: {e}")
                    except Exception:
                        logger.exception("Proposal export generation failed")
                        st.error("Failed to prepare proposal exports due to an unexpected error.")

                    st.text_area(
                        "Proposal Text (Copy Ready)",
                        value=prop_output.proposal_text,
                        height=500,
                    )


# Run the application when runtime is active
if st.runtime.exists():
    run_app()
