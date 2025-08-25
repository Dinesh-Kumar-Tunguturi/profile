import re
import fitz
import docx2txt
import textract
from collections import OrderedDict
import base64
import io
import matplotlib.pyplot as plt


def extract_text_from_resume(file_path):
    """Extracts text from resume."""
    if not isinstance(file_path, str):
        raise ValueError("extract_text_from_resume expects a file path string, got {}".format(type(file_path)))
    
    text = ""
    if file_path.lower().endswith(".pdf"):
        doc = fitz.open(file_path)
        for page in doc:
            text += page.get_text()
    elif file_path.lower().endswith(".docx"):
        text = docx2txt.process(file_path)
    elif file_path.lower().endswith(".doc"):
        text = textract.process(file_path).decode("utf-8", errors="ignore")
    return text.strip()



def generate_pie_chart(score_breakdown):
    """Generate a pie chart and return base64 image."""
    labels = list(score_breakdown.keys())
    sizes = [data["score"] for data in score_breakdown.values()]
    colors = ['#4CAF50', '#2196F3', '#FF9800', '#dc3545', '#9C27B0', '#00BCD4', '#FFC107', '#795548', '#E91E63', '#607D8B', '#8BC34A']
    fig, ax = plt.subplots()
    ax.pie(sizes, labels=labels, colors=colors[:len(labels)], autopct='%1.1f%%', startangle=140)
    ax.axis('equal')
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches="tight", transparent=True)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('utf-8')


def ats_scoring_for_non_tech(file_path, applicant_name="Candidate"):
    """ATS scoring for non-tech resumes with full report data for HTML."""
    text = extract_text_from_resume(file_path)
    text_lower = text.lower()

    # Contact/links detection
    contact_detection = "YES" if re.search(r'\b\d{10}\b', text) and re.search(r'@\w+\.\w+', text) else "NO"
    linkedin_detection = "YES" if "linkedin.com" in text_lower else "NO"
    github_detection = "YES" if "github.com" in text_lower else "NO"

    # Weights from requirement
    criteria = [
        ("Format & Layout", 20, "Professional one-column, no tables/headers."),
        ("File Type & Parsing", 10, "ATS-readable file format."),
        ("Section Headings & Structure", 10, "Proper headings, reverse chronological."),
        ("Job-Title & Core Skills", 10, "Target job title and key skills."),
        ("Dedicated Skills Section", 10, "Clear skills list."),
        ("Keyword Integration", 10, "Relevant keywords included."),
        ("Action Verbs", 10, "Strong verbs used in bullets."),
        ("Quantifiable Results", 10, "Metrics and outcomes provided."),
        ("Conciseness & Readability", 10, "Under 2 pages, readable."),
        ("Contact Info & Links", 5, "Name, phone, email, portfolio."),
        ("Proofreading & Consistency", 5, "No typos, consistent format."),
    ]

    score_breakdown = OrderedDict()

    # Simple evaluation logic (expandable)
    for name, weight, explanation in criteria:
        score = 0
        insight = explanation
        recs = []

        if name == "Format & Layout":
            if "\t" not in text and not re.search(r'(table|column|header|footer)', text_lower):
                score = weight
            else:
                score = weight // 2
                recs.append("Use a clean one-column layout without tables.")

        elif name == "File Type & Parsing":
            if file_path.lower().endswith((".doc", ".docx")):
                score = weight
            elif file_path.lower().endswith(".pdf"):
                score = int(weight * 0.7)
                recs.append("Use DOC/DOCX for maximum ATS compatibility.")
            else:
                score = 0

        elif name == "Section Headings & Structure":
            if all(h in text_lower for h in ["work experience", "education", "skills"]):
                score = weight
            else:
                score = weight // 2
                recs.append("Ensure standard section headings are included.")

        elif name == "Job-Title & Core Skills":
            if re.search(r'(manager|assistant|executive|analyst|officer)', text_lower):
                score = weight
            else:
                score = weight // 2

        elif name == "Dedicated Skills Section":
            score = weight if "skills" in text_lower else 0

        elif name == "Keyword Integration":
            keywords = ["communication", "teamwork", "leadership", "customer service", "problem solving"]
            score = min(sum(1 for kw in keywords if kw in text_lower) * 2, weight)

        elif name == "Action Verbs":
            verbs = ["developed", "implemented", "optimized", "managed", "led", "organized", "achieved"]
            score = min(sum(1 for v in verbs if v in text_lower) * 2, weight)

        elif name == "Quantifiable Results":
            if re.search(r'\d+%', text) or re.search(r'\d{1,3}(?:,\d{3})*(?:\.\d+)?', text):
                score = weight

        elif name == "Conciseness & Readability":
            wc = len(text.split())
            if wc <= 800:
                score = weight
            elif wc <= 1200:
                score = weight // 2

        elif name == "Contact Info & Links":
            score = weight if contact_detection == "YES" else 0

        elif name == "Proofreading & Consistency":
            if len(re.findall(r'\s{2,}', text)) < 5:
                score = weight

        # Grade
        pct = (score / weight) * 100
        if pct >= 85:
            grade = "Excellent"
        elif pct >= 70:
            grade = "Good"
        elif pct >= 50:
            grade = "Average"
        else:
            grade = "Poor"

        score_breakdown[name] = {
            "score": score,
            "grade": grade,
            "weight": weight,
            "sub_criteria": [{"name": name, "score": score, "weight": weight, "insight": insight}],
            "recommendations": recs
        }

    total_score = sum(v["score"] for v in score_breakdown.values())
    total_weight = sum(v["weight"] for v in score_breakdown.values())
    overall_score_average = int((total_score / total_weight) * 100)

    pie_chart_image = generate_pie_chart(score_breakdown)

    suggestions = [rec for sec in score_breakdown.values() for rec in sec["recommendations"]]

    return {
        "applicant_name": applicant_name,
        "contact_detection": contact_detection,
        "linkedin_detection": linkedin_detection,
        "github_detection": github_detection,
        "ats_score": score_breakdown["Keyword Integration"]["score"],  # Example: ATS = keyword score
        "overall_score_average": overall_score_average,
        "score_breakdown": score_breakdown,
        "pie_chart_image": pie_chart_image,
        "suggestions": suggestions
    }


import re
from collections import OrderedDict
from .utils import *  # adjust paths as needed

from collections import OrderedDict
import re
from .utils import *

def ats_scoring_non_tech_v2(file_path, applicant_name="Candidate"):
    """
    New ATS scoring for non-technical resumes using updated 11-criterion model.
    - ATS score = formatting & parsing readiness only
    - Overall score = job match + ATS readiness
    """
    # Extract text
    text = extract_text_from_resume(file_path)
    text_lower = text.lower()

    # Detect applicant name from first line (fallback to given)
    first_line = text.split("\n")[0].strip()
    if len(first_line.split()) <= 5 and not re.search(r'\d', first_line):
        applicant_name = first_line

    # Contact detection
    contact_detection = "YES" if re.search(r'\b\d{10}\b', text) and re.search(r'@\w+\.\w+', text) else "NO"

    # Criteria (weights & explanations)
    criteria = [
        ("Format & Layout", 20, "Single-column; professional font; minimal colours; avoid headers/footers, text boxes, tables, and multi-column designs."),
        ("File Type & Parsing", 10, "Use .doc/.docx unless PDF is explicitly accepted; avoid image-based formats."),
        ("Section Headings & Structure", 10, "Use standard headings (Work Experience, Education, Skills), reverse-chronological order, consistent date formats."),
        ("Job-Title & Core Skills", 10, "Include the target job title and 2–3 critical skills in the headline or summary."),
        ("Dedicated Skills Section", 10, "Clear Skills/Core Competencies list; include relevant hard skills and abbreviations."),
        ("Keyword Integration", 10, "Use keywords from job descriptions naturally throughout the resume."),
        ("Action Verbs", 10, "Start bullet points with strong verbs like 'Developed', 'Implemented', 'Optimized'."),
        ("Quantifiable Results", 10, "Provide metrics and outcomes using industry terminology."),
        ("Conciseness & Readability", 10, "Under two pages; avoid dense paragraphs; use bullet points."),
        ("Contact Info & Links", 5, "Include name, phone, email."),
        ("Proofreading & Consistency", 5, "Ensure spelling/grammar accuracy and consistent formatting."),
    ]

    score_breakdown = OrderedDict()
    suggestions = []

    for name, weight, explanation in criteria:
        score = 0
        recs = []

        if name == "Format & Layout":
            if "\t" not in text and not re.search(r'(table|column|header|footer)', text_lower):
                score = weight
            else:
                score = weight // 2
                recs.append("Switch to a clean one-column layout with no tables or headers/footers.")

        elif name == "File Type & Parsing":
            if file_path.lower().endswith((".doc", ".docx")):
                score = weight
            elif file_path.lower().endswith(".pdf"):
                score = int(weight * 0.7)
                recs.append("Prefer DOC/DOCX unless PDF is explicitly accepted.")
            else:
                score = 0

        elif name == "Section Headings & Structure":
            if all(h in text_lower for h in ["work experience", "education", "skills"]):
                score = weight
            else:
                score = weight // 2
                recs.append("Add standard section headings and ensure reverse-chronological order.")

        elif name == "Job-Title & Core Skills":
            if re.search(r'(manager|assistant|executive|analyst|officer)', text_lower):
                score = weight
            else:
                score = weight // 2
                recs.append("Include target job title and core skills in your headline/summary.")

        elif name == "Dedicated Skills Section":
            score = weight if "skills" in text_lower else 0
            if score == 0:
                recs.append("Add a dedicated Skills or Core Competencies section.")

        elif name == "Keyword Integration":
            keywords = ["communication", "teamwork", "leadership", "customer service", "problem solving"]
            kw_count = sum(1 for kw in keywords if kw in text_lower)
            score = min(kw_count * 2, weight)
            if score < weight:
                recs.append("Integrate more role-specific keywords from job descriptions.")

        elif name == "Action Verbs":
            verbs = ["developed", "implemented", "optimized", "managed", "led", "organized", "achieved"]
            verb_count = sum(1 for v in verbs if v in text_lower)
            score = min(verb_count * 2, weight)
            if score < weight:
                recs.append("Use strong action verbs to start bullet points.")

        elif name == "Quantifiable Results":
            if re.search(r'\d+%', text) or re.search(r'\d{1,3}(?:,\d{3})*(?:\.\d+)?', text):
                score = weight
            else:
                score = weight // 2
                recs.append("Add measurable results and metrics to your achievements.")

        elif name == "Conciseness & Readability":
            wc = len(text.split())
            if wc <= 800:
                score = weight
            elif wc <= 1200:
                score = weight // 2
                recs.append("Shorten resume to under two pages with concise bullet points.")
            else:
                score = 0
                recs.append("Significantly shorten and simplify content.")

        elif name == "Contact Info & Links":
            score = weight if contact_detection == "YES" else 0
            if score == 0:
                recs.append("Include phone, email, and name clearly at the top.")

        elif name == "Proofreading & Consistency":
            if len(re.findall(r'\s{2,}', text)) < 5:
                score = weight
            else:
                score = weight // 2
                recs.append("Proofread for consistent formatting and no typos.")

        # Grade assignment
        pct = (score / weight) * 100
        if pct >= 85:
            grade = "Excellent"
        elif pct >= 70:
            grade = "Good"
        elif pct >= 50:
            grade = "Average"
        else:
            grade = "Poor"

        score_breakdown[name] = {
            "score": score,
            "grade": grade,
            "weight": weight,
            "sub_criteria": [{"name": name, "score": score, "weight": weight, "insight": explanation}],
            "recommendations": recs
        }

        suggestions.extend(recs)

    # --- Calculate ATS score (only ATS-related criteria) ---
    ats_criteria_names = [
        "Format & Layout",
        "File Type & Parsing",
        "Section Headings & Structure",
        "Contact Info & Links",
        "Proofreading & Consistency"
    ]
    ats_total_score = sum(v["score"] for k, v in score_breakdown.items() if k in ats_criteria_names)
    ats_total_weight = sum(v["weight"] for k, v in score_breakdown.items() if k in ats_criteria_names)
    ats_score = int((ats_total_score / ats_total_weight) * 100)

    # --- Calculate Overall score (all criteria) ---
    total_score = sum(v["score"] for v in score_breakdown.values())
    total_weight = sum(v["weight"] for v in score_breakdown.values())
    overall_score_average = int((total_score / total_weight) * 100)

    # Pie chart
    pie_chart_image = generate_pie_chart_v2(score_breakdown)

    return {
        "applicant_name": applicant_name,
        "contact_detection": contact_detection,
        "ats_score": ats_score,  # % ATS readiness
        "overall_score_average": overall_score_average,  # % job match
        "score_breakdown": score_breakdown,
        "pie_chart_image": pie_chart_image,
        "suggestions": suggestions
    }
