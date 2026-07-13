from datetime import date
import logging
from typing import List
from dateutil.parser import parse as parse_date
from app.models.schemas import UserProfile, JobAnalysisResult, JobMatchScore, WorkExperience

logger = logging.getLogger(__name__)


def calculate_user_experience_years(experience_list: List[WorkExperience]) -> float:
    """Calculates the total years of work experience for the user.

    Aggregates duration across all experiences.
    """
    total_days = 0
    for exp in experience_list:
        try:
            start = parse_date(exp.start_date).date()
            if not exp.end_date or exp.end_date.strip().lower() in (
                "present",
                "now",
                "current",
                "active",
            ):
                end = date.today()
            else:
                end = parse_date(exp.end_date).date()

            # Avoid negative days just in case dates are misconfigured
            duration_days = max(0, (end - start).days)
            total_days += duration_days
        except Exception as e:
            logger.warning(
                "Could not parse dates for experience at %s (%s - %s): %s",
                exp.company,
                exp.start_date,
                exp.end_date,
                e,
            )
            continue
    return round(total_days / 365.25, 1)


def calculate_match_score(
    profile: UserProfile, job_analysis: JobAnalysisResult
) -> JobMatchScore:
    """Calculates a transparent job-match score comparing user profile to job requirements.

    Weights:
    - Skills match (required: 80%, preferred: 20%)
    - Experience match (30% overall weight if required; skills is 70%. Otherwise skills is 100%)
    """
    user_skills_lower = {s.lower() for s in profile.skills}

    # 1. Classify required skills match
    matched_req = []
    missing_req = []
    for skill in job_analysis.required_skills:
        if skill.lower() in user_skills_lower:
            matched_req.append(skill)
        else:
            missing_req.append(skill)

    # 2. Classify preferred skills match
    matched_pref = []
    missing_pref = []
    for skill in job_analysis.preferred_skills:
        if skill.lower() in user_skills_lower:
            matched_pref.append(skill)
        else:
            missing_pref.append(skill)

    # 3. Calculate skills score
    # Required skills weight: 80%, Preferred: 20%
    req_pct = 100.0
    if job_analysis.required_skills:
        req_pct = (len(matched_req) / len(job_analysis.required_skills)) * 100.0

    pref_pct = 100.0
    if job_analysis.preferred_skills:
        pref_pct = (len(matched_pref) / len(job_analysis.preferred_skills)) * 100.0

    if job_analysis.required_skills and job_analysis.preferred_skills:
        skills_match_score = (req_pct * 0.8) + (pref_pct * 0.2)
    elif job_analysis.required_skills:
        skills_match_score = req_pct
    elif job_analysis.preferred_skills:
        skills_match_score = pref_pct
    else:
        # No skills mentioned in job description
        skills_match_score = 100.0

    # 4. Calculate experience score
    user_exp = calculate_user_experience_years(profile.experience)
    req_exp = job_analysis.experience_years_required

    if req_exp is not None and req_exp > 0:
        if user_exp >= req_exp:
            exp_match_score = 100.0
        else:
            exp_match_score = (user_exp / req_exp) * 100.0
    else:
        exp_match_score = 100.0

    # 5. Calculate overall score
    # If there is experience requirement, weight is 70% skills, 30% experience.
    # Otherwise, it's 100% skills.
    if req_exp is not None and req_exp > 0:
        overall_score = (skills_match_score * 0.7) + (exp_match_score * 0.3)
    else:
        overall_score = skills_match_score

    # 6. Generate detailed explanation
    explanations = []
    if job_analysis.required_skills:
        explanations.append(
            f"Required Skills: Matched {len(matched_req)} of {len(job_analysis.required_skills)} "
            f"({req_pct:.0f}%)."
        )
    else:
        explanations.append("No specific required skills extracted.")

    if job_analysis.preferred_skills:
        explanations.append(
            f"Preferred Skills: Matched {len(matched_pref)} of {len(job_analysis.preferred_skills)} "
            f"({pref_pct:.0f}%)."
        )

    if req_exp is not None and req_exp > 0:
        explanations.append(
            f"Experience: Job requires {req_exp} years, candidate has {user_exp} years "
            f"({exp_match_score:.0f}% match)."
        )
    else:
        explanations.append(
            f"No specific experience requirements found. Candidate has {user_exp} years."
        )

    explanation_str = " | ".join(explanations)

    return JobMatchScore(
        overall_score=round(overall_score, 1),
        skills_match_score=round(skills_match_score, 1),
        experience_match_score=round(exp_match_score, 1),
        matched_required_skills=matched_req,
        missing_required_skills=missing_req,
        matched_preferred_skills=matched_pref,
        missing_preferred_skills=missing_pref,
        required_experience_years=req_exp,
        user_experience_years=user_exp,
        explanation=explanation_str,
    )
