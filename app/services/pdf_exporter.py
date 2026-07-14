import re
from io import BytesIO
from typing import Optional
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

from app.models.schemas import UserProfile, GeneratedResumeContent, GeneratedProposal, JobMatchScore


class ExportError(Exception):
    """Exception raised for errors during document export."""
    pass


def sanitize_filename(filename: str) -> str:
    """Sanitizes a filename by removing unsupported characters."""
    if not filename:
        return "document"
    # Split filename and extension
    base, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
    # Replace non-alphanumeric/dash/underscore with underscore
    base = re.sub(r'[^a-zA-Z0-9_\-]', '_', base)
    # Collapse multiple underscores
    base = re.sub(r'_+', '_', base).strip('_')
    if ext:
        return f"{base}.{ext}"
    return base


def format_text_to_html(text: str) -> str:
    """Escapes HTML and translates newlines to <br/> for ReportLab Paragraphs."""
    if not text:
        return ""
    escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return escaped.replace("\n", "<br/>")


def draw_page_decorations(canvas, doc, title_text: str):
    """Draws consistent footer and header line on pages."""
    canvas.saveState()
    # Draw top header line
    canvas.setStrokeColor(colors.HexColor('#E2E8F0'))
    canvas.setLineWidth(0.5)
    canvas.line(54, doc.pagesize[1] - 40, doc.pagesize[0] - 54, doc.pagesize[1] - 40)
    
    # Draw footer line
    canvas.line(54, 50, doc.pagesize[0] - 54, 50)
    
    # Draw footer text
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(colors.HexColor('#718096'))
    canvas.drawString(54, 35, title_text)
    canvas.drawRightString(doc.pagesize[0] - 54, 35, f"Page {canvas.getPageNumber()}")
    canvas.restoreState()


def draw_resume_decorations(canvas, doc):
    draw_page_decorations(canvas, doc, "Tailored Resume")


def draw_proposal_decorations(canvas, doc):
    draw_page_decorations(canvas, doc, "Freelance Proposal")


def _get_export_styles():
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#1E3A8A'),
        spaceAfter=4
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=12,
        leading=15,
        textColor=colors.HexColor('#4A5568'),
        spaceAfter=8
    )

    contact_style = ParagraphStyle(
        'DocContact',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#718096'),
        spaceAfter=12
    )

    section_heading_style = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=16,
        textColor=colors.HexColor('#1E3A8A'),
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#2D3748'),
        spaceAfter=5
    )

    bullet_style = ParagraphStyle(
        'DocBullet',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor('#2D3748'),
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=3
    )
    
    return title_style, subtitle_style, contact_style, section_heading_style, body_style, bullet_style


def add_section_heading(story, text, style):
    """Creates a section header table with a bottom rule line."""
    t = Table([[Paragraph(text, style)]], colWidths=[504])
    t.setStyle(TableStyle([
        ('LINEBELOW', (0, 0), (-1, -1), 1.0, colors.HexColor('#1E3A8A')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(t)
    story.append(Spacer(1, 4))


def export_resume_pdf(
    profile: UserProfile,
    resume: GeneratedResumeContent,
    match_score: Optional[JobMatchScore] = None
) -> bytes:
    """Generates a professional resume PDF in memory and returns its bytes."""
    if not profile.full_name or not profile.full_name.strip():
        raise ExportError("Candidate full name cannot be empty.")
    if not resume.professional_summary or not resume.professional_summary.strip():
        raise ExportError("Resume professional summary cannot be empty.")
        
    try:
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            leftMargin=54,
            rightMargin=54,
            topMargin=54,
            bottomMargin=60
        )
        
        story = []
        title_style, subtitle_style, contact_style, section_heading_style, body_style, bullet_style = _get_export_styles()
        
        # 1. Candidate Name and Title
        story.append(Paragraph(format_text_to_html(profile.full_name), title_style))
        story.append(Paragraph(format_text_to_html(profile.title), subtitle_style))
        
        # 2. Contact details
        contact_parts = []
        if profile.email and profile.email.strip():
            contact_parts.append(f"Email: {profile.email.strip()}")
        if profile.phone and profile.phone.strip():
            contact_parts.append(f"Phone: {profile.phone.strip()}")
        if contact_parts:
            story.append(Paragraph(" | ".join(contact_parts), contact_style))
        else:
            story.append(Spacer(1, 5))
            
        # 3. Job Match Summary Box
        if match_score:
            match_data = [
                [
                    Paragraph(f"<b>Match Score: {match_score.overall_score}%</b>", body_style),
                    Paragraph(f"<b>Skills Fit: {match_score.skills_match_score}%</b>", body_style),
                    Paragraph(f"<b>Experience Fit: {match_score.experience_match_score}%</b>", body_style)
                ],
                [
                    Paragraph(f"<i>Overview: {format_text_to_html(match_score.explanation)}</i>", body_style),
                    "", ""
                ]
            ]
            t = Table(match_data, colWidths=[168, 168, 168])
            t.setStyle(TableStyle([
                ('SPAN', (0, 1), (2, 1)),
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
                ('PADDING', (0, 0), (-1, -1), 6),
                ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            story.append(t)
            story.append(Spacer(1, 8))
            
        # 4. Professional Summary
        add_section_heading(story, "Professional Summary", section_heading_style)
        story.append(Paragraph(format_text_to_html(resume.professional_summary), body_style))
        story.append(Spacer(1, 6))
        
        # 5. Skills
        if resume.tailored_skills:
            add_section_heading(story, "Key Skills", section_heading_style)
            skills_text = ", ".join(resume.tailored_skills)
            story.append(Paragraph(format_text_to_html(skills_text), body_style))
            story.append(Spacer(1, 6))
            
        # 6. Work Experience
        if profile.experience:
            add_section_heading(story, "Professional Experience", section_heading_style)
            for exp in profile.experience:
                end = exp.end_date if exp.end_date else "Present"
                role_comp = f"<b>{format_text_to_html(exp.role)}</b> at <b>{format_text_to_html(exp.company)}</b>"
                dates = f"{format_text_to_html(exp.start_date)} - {format_text_to_html(end)}"
                
                exp_header = Table(
                    [[Paragraph(role_comp, body_style), Paragraph(dates, ParagraphStyle('RightAlign', parent=body_style, alignment=2))]],
                    colWidths=[354, 150]
                )
                exp_header.setStyle(TableStyle([
                    ('PADDING', (0, 0), (-1, -1), 0),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ]))
                
                desc = Paragraph(format_text_to_html(exp.description), body_style)
                story.append(KeepTogether([exp_header, Spacer(1, 2), desc, Spacer(1, 6)]))
                
        # 7. Projects
        if profile.projects:
            add_section_heading(story, "Projects", section_heading_style)
            for proj in profile.projects:
                proj_title = f"<b>{format_text_to_html(proj.title)}</b>"
                if proj.url and proj.url.strip():
                    proj_title += f" (<a href='{proj.url.strip()}' color='#1E3A8A'>{format_text_to_html(proj.url.strip())}</a>)"
                
                tech_stack = ""
                if proj.technologies:
                    tech_stack = f"<i>Technologies: {format_text_to_html(', '.join(proj.technologies))}</i>"
                
                proj_elements = [
                    Paragraph(proj_title, body_style),
                ]
                if tech_stack:
                    proj_elements.append(Paragraph(tech_stack, body_style))
                proj_elements.append(Paragraph(format_text_to_html(proj.description), body_style))
                proj_elements.append(Spacer(1, 6))
                
                story.append(KeepTogether(proj_elements))
                
        # 8. Education
        if profile.education:
            add_section_heading(story, "Education", section_heading_style)
            for edu in profile.education:
                degree_major = f"<b>{format_text_to_html(edu.degree)}</b> in {format_text_to_html(edu.field_of_study)}"
                inst = format_text_to_html(edu.institution)
                grad_yr = f"Graduated: {edu.graduation_year}" if edu.graduation_year else ""
                
                edu_table = Table(
                    [[
                        Paragraph(degree_major, body_style),
                        Paragraph(inst, ParagraphStyle('CenterAlign', parent=body_style, alignment=1)),
                        Paragraph(grad_yr, ParagraphStyle('RightAlign', parent=body_style, alignment=2))
                    ]],
                    colWidths=[200, 184, 120]
                )
                edu_table.setStyle(TableStyle([
                    ('PADDING', (0, 0), (-1, -1), 0),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ]))
                story.append(KeepTogether([edu_table, Spacer(1, 4)]))
                
        # 9. Certifications
        if profile.certifications:
            story.append(Spacer(1, 2))
            add_section_heading(story, "Certifications", section_heading_style)
            for cert in profile.certifications:
                cert_text = f"<b>{format_text_to_html(cert.name)}</b> - {format_text_to_html(cert.issuing_org)}"
                if cert.year:
                    cert_text += f" ({cert.year})"
                story.append(Paragraph(cert_text, bullet_style))
            story.append(Spacer(1, 6))
            
        # 10. Suggestions Page (Optional, only if insights exist)
        if resume.improvement_suggestions or resume.missing_skills_report:
            story.append(PageBreak())
            add_section_heading(story, "Resume Tailoring Insights & Recommendations", section_heading_style)
            story.append(Spacer(1, 4))
            
            if resume.improvement_suggestions:
                story.append(Paragraph("<b>Improvement Suggestions:</b>", body_style))
                for sug in resume.improvement_suggestions:
                    story.append(Paragraph(format_text_to_html(sug), bullet_style))
                story.append(Spacer(1, 8))
                
            if resume.missing_skills_report:
                story.append(Paragraph("<b>Missing Skills Report & Recommendations:</b>", body_style))
                for rep in resume.missing_skills_report:
                    story.append(Paragraph(format_text_to_html(rep), bullet_style))
                    
        doc.build(story, onFirstPage=draw_resume_decorations, onLaterPages=draw_resume_decorations)
        return buffer.getvalue()
    except Exception as e:
        raise ExportError(f"Failed to generate resume PDF: {str(e)}") from e


def export_proposal_pdf(
    profile: UserProfile,
    proposal: GeneratedProposal,
    match_score: Optional[JobMatchScore] = None
) -> bytes:
    """Generates a professional freelance proposal PDF in memory and returns its bytes."""
    if not profile.full_name or not profile.full_name.strip():
        raise ExportError("Candidate full name cannot be empty.")
    if not proposal.proposal_text or not proposal.proposal_text.strip():
        raise ExportError("Proposal text content cannot be empty.")
        
    try:
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            leftMargin=54,
            rightMargin=54,
            topMargin=54,
            bottomMargin=60
        )
        
        story = []
        title_style, subtitle_style, contact_style, section_heading_style, body_style, bullet_style = _get_export_styles()
        
        # 1. Candidate Name and Title
        story.append(Paragraph(format_text_to_html(profile.full_name), title_style))
        story.append(Paragraph(format_text_to_html(profile.title), subtitle_style))
        
        # 2. Contact details
        contact_parts = []
        if profile.email and profile.email.strip():
            contact_parts.append(f"Email: {profile.email.strip()}")
        if profile.phone and profile.phone.strip():
            contact_parts.append(f"Phone: {profile.phone.strip()}")
        if contact_parts:
            story.append(Paragraph(" | ".join(contact_parts), contact_style))
        else:
            story.append(Spacer(1, 5))
            
        # 3. Job Match Summary Box
        if match_score:
            match_data = [
                [
                    Paragraph(f"<b>Overall Compatibility Match: {match_score.overall_score}%</b>", body_style),
                    Paragraph(f"<b>Skills Compatibility: {match_score.skills_match_score}%</b>", body_style),
                    Paragraph(f"<b>Experience Compatibility: {match_score.experience_match_score}%</b>", body_style)
                ]
            ]
            t = Table(match_data, colWidths=[168, 168, 168])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
                ('PADDING', (0, 0), (-1, -1), 6),
                ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            story.append(t)
            story.append(Spacer(1, 10))
            
        # 4. Proposal Body
        add_section_heading(story, "Freelance Proposal", section_heading_style)
        story.append(Paragraph(format_text_to_html(proposal.proposal_text), body_style))
        
        doc.build(story, onFirstPage=draw_proposal_decorations, onLaterPages=draw_proposal_decorations)
        return buffer.getvalue()
    except Exception as e:
        raise ExportError(f"Failed to generate proposal PDF: {str(e)}") from e
