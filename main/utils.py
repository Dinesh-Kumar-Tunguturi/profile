# utils.py  (slimmed for Vercel)

from __future__ import annotations

import os
import re
import io
import json
import tempfile
from typing import Dict, List, Tuple, Optional

import requests
from PyPDF2 import PdfReader
import docx2txt
from bs4 import BeautifulSoup

# ─────────────────────────────────────────────────────────────
# Weights (keep lightweight, no heavy imports here)
# ─────────────────────────────────────────────────────────────
TECHNICAL_WEIGHTS: Dict[str, int] = {
    "GitHub Profile": 25,
    "LeetCode/DSA Skills": 20,
    "Portfolio Website": 20,
    "LinkedIn Profile": 15,
    "Resume (ATS Score)": 10,
    "Certifications & Branding": 10,
}

# ─────────────────────────────────────────────────────────────
# GitHub API (no hard-coded token; use env if present)
# ─────────────────────────────────────────────────────────────
def _github_headers() -> Dict[str, str]:
    headers = {"Accept": "application/vnd.github.v3+json"}
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"token {token}"
    return headers


# ─────────────────────────────────────────────────────────────
# Basic text extraction (PDF/DOCX)
# ─────────────────────────────────────────────────────────────
def extract_text_from_pdf(file_obj_or_path) -> str:
    """
    Accepts a Django InMemoryUploadedFile, file-like, or a filesystem path.
    Uses PyPDF2 only (lightweight).
    """
    try:
        if isinstance(file_obj_or_path, (str, bytes, os.PathLike)):
            with open(file_obj_or_path, "rb") as f:
                reader = PdfReader(f)
                return "\n".join(
                    (page.extract_text() or "") for page in reader.pages
                )
        else:
            # file-like (e.g., InMemoryUploadedFile)
            reader = PdfReader(file_obj_or_path)
            return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception:
        return ""


def extract_text_from_docx(file_obj_or_path) -> str:
    """
    Accepts file-like or path; docx2txt expects a path, so we write to temp if needed.
    """
    try:
        if isinstance(file_obj_or_path, (str, bytes, os.PathLike)):
            return docx2txt.process(file_obj_or_path)
        # Write uploaded file to temp and process
        with tempfile.NamedTemporaryFile(delete=True, suffix=".docx") as tmp:
            chunk = file_obj_or_path.read()
            file_obj_or_path.seek(0)
            tmp.write(chunk)
            tmp.flush()
            return docx2txt.process(tmp.name)
    except Exception:
        return ""


def extract_applicant_name(resume_text: str) -> str:
    """
    Very simple heuristic: first non-empty line.
    """
    if not resume_text:
        return "Applicant Name Not Found"
    for line in (l.strip() for l in resume_text.splitlines()):
        if line:
            return line
    return "Applicant Name Not Found"


# ─────────────────────────────────────────────────────────────
# Link extraction (no PyMuPDF; parse text only)
# ─────────────────────────────────────────────────────────────
def extract_links_from_pdf(file_obj_or_path) -> List[str]:
    """
    Extract URLs from PDF text (annotations not included, to stay light).
    """
    text = extract_text_from_pdf(file_obj_or_path)
    url_pattern = r"https?://[^\s)>\]\"'}]+"
    return re.findall(url_pattern, text or "")


def extract_and_identify_links(text: str) -> List[Dict[str, Optional[str]]]:
    """
    Extract URLs, emails, and <a href> from HTML-ish text and classify.
    """
    links: List[Dict[str, Optional[str]]] = []

    url_pattern = r"https?://[^\s\"]+"
    email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"

    found_urls = re.findall(url_pattern, text or "")
    found_emails = re.findall(email_pattern, text or "")

    def _classify(u: str) -> str:
        if "github.com" in u:
            return "GitHub"
        if "linkedin.com" in u:
            return "LinkedIn"
        if re.search(r"portfolio|netlify|vercel|\.me|\.io|\.dev|\.app", u, re.I):
            return "Portfolio"
        if u.startswith("mailto:"):
            return "Email"
        return "Other"

    for u in found_urls:
        links.append({"url": u, "type": _classify(u)})

    for e in found_emails:
        links.append({"url": f"mailto:{e}", "type": "Email"})

    # Parse HTML anchors
    soup = BeautifulSoup(text or "", "html.parser")
    existing = {d["url"] for d in links if d.get("url")}
    for tag in soup.find_all("a", href=True):
        href = tag["href"]
        if href not in existing:
            links.append({"url": href, "type": _classify(href)})
            existing.add(href)

    # Inferred LinkedIn mention
    if re.search(r"linkedin", text or "", re.I):
        if not any(d.get("type") == "LinkedIn" for d in links):
            links.append({"url": None, "type": "LinkedIn (Inferred)"})

    return links


def extract_links_combined(pdf_path: str) -> Tuple[List[str], str]:
    """
    Lightweight variant: read PDF text with PyPDF2 and parse URLs from text.
    Returns (links, full_text). No annotation scanning (keeps deps small).
    """
    full_text = extract_text_from_pdf(pdf_path) or ""
    url_pattern = r"https?://[^\s)>\]\"'}]+"
    email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"

    found_urls = re.findall(url_pattern, full_text)
    found_emails = [f"mailto:{e}" for e in re.findall(email_pattern, full_text)]

    return list(dict.fromkeys(found_urls + found_emails)), full_text  # dedupe, keep order


# ─────────────────────────────────────────────────────────────
# Profile lookups
# ─────────────────────────────────────────────────────────────
def extract_github_username(text: str) -> Optional[str]:
    m = re.search(r"github\.com/([A-Za-z0-9\-]+)", text or "")
    return m.group(1) if m else None


def get_github_repo_count(username: str) -> int:
    if not username:
        return 0
    url = f"https://api.github.com/users/{username}"
    try:
        r = requests.get(url, headers=_github_headers(), timeout=10)
        if r.status_code == 200:
            return int(r.json().get("public_repos", 0))
    except Exception:
        pass
    return 0


def extract_leetcode_username(text: str) -> Optional[str]:
    """
    Accepts both styles: leetcode.com/u/username OR leetcode.com/username
    """
    m = re.search(r"leetcode\.com/(?:u/)?([\w\-]+)", text or "")
    return m.group(1) if m else None


def fetch_leetcode_problem_count(username: str) -> int:
    if not username:
        return 0
    base = "https://leetcode-api-faisalshohag.vercel.app/"
    try:
        res = requests.get(f"{base}{username}", timeout=10)
        if res.status_code == 200:
            return int(res.json().get("totalSolved", 0))
    except Exception:
        pass
    return 0


# ─────────────────────────────────────────────────────────────
# Scoring helpers (light logic only)
# ─────────────────────────────────────────────────────────────
def get_grade_tag(score: float | int) -> str:
    s = float(score or 0)
    if s >= 85:
        return "Excellent"
    if s >= 70:
        return "Good"
    if s >= 50:
        return "Average"
    return "Poor"


def get_cert_suggestions(domain: str) -> List[str]:
    if (domain or "").lower() == "analytical":
        return [
            "Google Data Analytics Professional Certificate – Coursera",
            "IBM Data Science Professional Certificate – Coursera",
            "Microsoft Certified: Azure Data Scientist Associate",
        ]
    if (domain or "").lower() == "technical":
        return [
            "AWS Certified Developer – AWS",
            "Microsoft Certified: Azure Developer Associate",
            "Certified Kubernetes Application Developer (CKAD)",
        ]
    return [
        "IBM AI Practitioner – Coursera",
        "Google Data Analytics Professional Certificate – Coursera",
        "AWS Certified Developer – AWS",
    ]


def calculate_dynamic_ats_score(
    resume_text: str,
    github_username: Optional[str],
    leetcode_username: Optional[str],
    extracted_links: List[Dict[str, str]] | List[str],
) -> Dict:
    """
    Lightweight, deterministic-ish scoring. No heavy libs. No network calls here.
    """
    weights = TECHNICAL_WEIGHTS.copy()
    sections: Dict[str, Dict] = {}
    suggestions: List[str] = []

    text = resume_text or ""
    github_presence = bool(github_username)
    leetcode_presence = bool(leetcode_username)
    portfolio_presence = bool(re.search(r"https?://[a-z0-9\-]+\.(com|io|dev|app|me|net|in|org)", text, re.I))
    linkedin_presence = bool(re.search(r"linkedin\.com/in/", text, re.I))
    cert_presence = bool(re.search(r"\b(certification|certified|course|certificate)\b", text, re.I))

    # 1) GitHub Profile
    github_score = 0
    github_criteria = []
    if github_presence:
        # small pseudo-criteria to avoid network calls
        github_criteria = [
            {"name": "Public link present", "score": 3, "weight": 3, "insight": "GitHub link detected."},
            {"name": "Recent activity (assumed)", "score": 4, "weight": 5, "insight": "Add recent commits/pins."},
            {"name": "Domain-relevant projects", "score": 4, "weight": 6, "insight": "Keep repos aligned to role."},
        ]
        github_score = sum(c["score"] for c in github_criteria)
    else:
        github_criteria = [{"name": "Public link present", "score": 0, "weight": 3, "insight": "Add your GitHub link."}]
        suggestions.append("Add a GitHub profile link with pinned, recent projects.")

    sections["GitHub Profile"] = {
        "score": github_score,
        "grade": get_grade_tag(github_score),
        "weight": weights["GitHub Profile"],
        "sub_criteria": github_criteria,
    }

    # 2) LeetCode / DSA
    leetcode_score = 0
    leetcode_criteria = []
    if leetcode_presence:
        leetcode_criteria = [
            {"name": "Link present", "score": 2, "weight": 2, "insight": "Profile link detected."},
            {"name": "Problem variety (assumed)", "score": 3, "weight": 5, "insight": "Cover DP/Graphs/Greedy."},
            {"name": "Consistency (assumed)", "score": 3, "weight": 4, "insight": "Regular practice helps."},
        ]
        leetcode_score = sum(c["score"] for c in leetcode_criteria)
    else:
        leetcode_criteria = [{"name": "Link present", "score": 0, "weight": 2, "insight": "Include your LeetCode link."}]
        suggestions.append("Include a LeetCode link to showcase DSA practice.")

    sections["LeetCode/DSA Skills"] = {
        "score": leetcode_score,
        "grade": get_grade_tag(leetcode_score),
        "weight": weights["LeetCode/DSA Skills"],
        "sub_criteria": leetcode_criteria,
    }

    # 3) Portfolio
    portfolio_score = 0
    portfolio_criteria = []
    if portfolio_presence:
        portfolio_criteria = [
            {"name": "Link present", "score": 2, "weight": 2, "insight": "Portfolio detected."},
            {"name": "Project write-ups (assumed)", "score": 3, "weight": 4, "insight": "Explain problems & impact."},
            {"name": "Interactive demos (assumed)", "score": 2, "weight": 3, "insight": "Add live demos if possible."},
        ]
        portfolio_score = sum(c["score"] for c in portfolio_criteria)
    else:
        portfolio_criteria = [{"name": "Link present", "score": 0, "weight": 2, "insight": "Add a simple portfolio site."}]
        suggestions.append("Publish a simple portfolio with 2–3 best projects.")

    sections["Portfolio Website"] = {
        "score": portfolio_score,
        "grade": get_grade_tag(portfolio_score),
        "weight": weights["Portfolio Website"],
        "sub_criteria": portfolio_criteria,
    }

    # 4) LinkedIn
    linkedin_score = 3 if linkedin_presence else 0
    linkedin_criteria = [
        {
            "name": "Public link present",
            "score": linkedin_score,
            "weight": 3,
            "insight": "Add a public LinkedIn URL to boost visibility." if not linkedin_presence else "LinkedIn detected.",
        }
    ]
    if not linkedin_presence:
        suggestions.append("Add a public LinkedIn link (custom URL preferred).")

    sections["LinkedIn"] = {
        "score": linkedin_score,
        "grade": get_grade_tag(linkedin_score),
        "weight": 3,
        "sub_criteria": linkedin_criteria,
    }

    # 5) Resume (ATS Score) — placeholder here; real value can override in views
    resume_section_score = 65  # neutral placeholder; views will override with ats_resume_scoring()
    resume_criteria = [
        {"name": "ATS-friendly layout", "score": 3, "weight": 3, "insight": "Readable fonts, minimal columns."},
        {"name": "Action verbs & results", "score": 4, "weight": 4, "insight": "Quantify achievements."},
        {"name": "Keyword alignment", "score": 3, "weight": 3, "insight": "Mirror JD keywords."},
        {"name": "Brevity", "score": 2, "weight": 2, "insight": "Keep to 1–2 pages."},
        {"name": "Clarity", "score": 3, "weight": 3, "insight": "Avoid jargon/repetition."},
    ]
    sections["Resume (ATS Score)"] = {
        "score": resume_section_score,
        "grade": get_grade_tag(resume_section_score),
        "weight": weights["Resume (ATS Score)"],
        "sub_criteria": resume_criteria,
    }

    # 6) Certifications
    if cert_presence:
        cert_score = 65
        cert_criteria = [
            {"name": "Role-relevant", "score": 5, "weight": 5, "insight": "Keep recent & relevant."},
            {"name": "Credible issuer", "score": 5, "weight": 5, "insight": "Prefer AWS, MS, Coursera, etc."},
            {"name": "Recency", "score": 3, "weight": 3, "insight": "Within 2 years preferred."},
            {"name": "Completeness", "score": 2, "weight": 2, "insight": "Title + issuer clearly listed."},
        ]
        cert_recs: List[str] = []
    else:
        cert_score = 0
        cert_criteria = [{"name": "Certifications present", "score": 0, "weight": 15, "insight": "Consider 1–2 role-aligned certs."}]
        cert_recs = get_cert_suggestions("technical")

    sections["Certifications & Branding"] = {
        "score": cert_score,
        "grade": get_grade_tag(cert_score),
        "weight": weights["Certifications & Branding"],
        "sub_criteria": cert_criteria,
        "recommendations": cert_recs,
    }

    # Totals
    total_score = sum(s.get("score", 0) * (s.get("weight", 0) / 100.0) for s in sections.values())
    all_scores = [s.get("score", 0) for s in sections.values()]
    overall_avg = int(round(sum(all_scores) / max(1, len(all_scores))))

    return {
        "sections": sections,
        "total_score": int(round(total_score)),
        "overall_score_average": overall_avg,
        "overall_grade": get_grade_tag(overall_avg),
        "suggestions": suggestions,
    }


# ─────────────────────────────────────────────────────────────
# Client-side chart payload (for Chart.js; no matplotlib)
# ─────────────────────────────────────────────────────────────
def prepare_chart_data(score_breakdown: Dict[str, Dict]) -> Dict[str, List]:
    labels = list(score_breakdown.keys())
    scores = [int(score_breakdown[k].get("score", 0)) for k in labels]
    colors: List[str] = []
    for k in labels:
        grade = (score_breakdown[k].get("grade") or "").lower()
        if grade == "excellent":
            colors.append("#4CAF50")
        elif grade == "good":
            colors.append("#2196F3")
        elif grade == "average":
            colors.append("#FF9800")
        else:
            colors.append("#dc3545")
    return {"labels": labels, "scores": scores, "backgroundColors": colors}


# ─────────────────────────────────────────────────────────────
# Text normalization + ATS resume scoring (lightweight)
# ─────────────────────────────────────────────────────────────
def normalize_text(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "")).strip().lower()


def keyword_match_rate(text: str, target_keywords: List[str]) -> float:
    if not target_keywords:
        return 0.0
    t = normalize_text(text)
    hits = sum(1 for kw in target_keywords if kw.lower() in t)
    return hits / max(1, len(target_keywords))


def ats_resume_scoring(metrics: Dict) -> Dict:
    """
    15-point breakdown => normalized 0..100 (lightweight).
    """
    b = {"items": []}
    total = 0
    MAX_ATS = 15

    # 1) Layout & structure — 3
    pts_layout = int(bool(metrics.get("sections_present"))) \
               + int(bool(metrics.get("single_column"))) \
               + int(bool(metrics.get("text_extractable")))
    b["items"].append({"name": "ATS-friendly layout & structure", "earned": pts_layout, "max": 3})
    total += pts_layout

    # 2) Action verbs & quantified — 4
    av = float(metrics.get("action_verbs_per_bullet", 0.0))
    qr = float(metrics.get("quantified_bullets_ratio", 0.0))
    pts_actions = (2 if av >= 0.8 else 1 if av >= 0.5 else 0) + (2 if qr >= 0.6 else 1 if qr >= 0.3 else 0)
    b["items"].append({"name": "Action verbs & quantified results", "earned": pts_actions, "max": 4})
    total += pts_actions

    # 3) Keyword alignment — 3
    kmr = float(metrics.get("keyword_match_rate", 0.0))
    pts_keywords = 3 if kmr >= 0.75 else 2 if kmr >= 0.5 else 1 if kmr >= 0.3 else 0
    b["items"].append({"name": "Job-relevant keyword alignment", "earned": pts_keywords, "max": 3})
    total += pts_keywords

    # 4) Brevity — 2
    pages = int(metrics.get("pages", 2))
    avg_bullets = float(metrics.get("avg_bullets_per_job", 6.0))
    pts_brev = (1 if pages <= 2 else 0) + (1 if avg_bullets <= 7 else 0)
    b["items"].append({"name": "Brevity & conciseness", "earned": pts_brev, "max": 2})
    total += pts_brev

    # 5) Minimal jargon / repetition — 3
    rep = float(metrics.get("repetition_rate", 0.15))
    jar = float(metrics.get("jargon_rate", 0.2))
    usk = int(metrics.get("unique_skills_count", 8))
    pts_clean = (1 if rep <= 0.10 else 0) + (1 if jar <= 0.15 else 0) + (1 if usk >= 8 else 0)
    b["items"].append({"name": "Minimal jargon / repetition", "earned": pts_clean, "max": 3})
    total += pts_clean

    b["subtotal"] = {"earned": total, "max": MAX_ATS}
    b["score_100"] = int(round((total / MAX_ATS) * 100))
    return b


# ─────────────────────────────────────────────────────────────
# Role keywords + metrics derivation (light)
# ─────────────────────────────────────────────────────────────
ROLE_KEYWORDS: Dict[str, List[str]] = {
    # Technical
    "software engineer": ["python","java","javascript","react","node","docker","kubernetes","microservices","rest","graphql","aws","gcp","ci/cd","unit testing"],
    "data scientist": ["python","pandas","numpy","sklearn","tensorflow","pytorch","nlp","cv","statistics","sql","experiment","a/b testing","data visualization"],
    "devops engineer": ["ci/cd","docker","kubernetes","terraform","ansible","aws","gcp","azure","monitoring","prometheus","grafana","helm","sre"],
    "web developer": ["html","css","javascript","react","next.js","vue","node","express","rest","graphql","responsive","seo"],
    "mobile app developer": ["android","ios","kotlin","swift","flutter","react native","firebase","push notifications","play store","app store"],
    # Non-technical
    "human resources": ["recruitment","onboarding","payroll","employee engagement","hrms","policy","compliance","talent acquisition","grievance","training"],
    "marketing": ["seo","sem","campaign","content","email marketing","social media","analytics","branding","roi","conversion","google ads"],
    "sales": ["crm","pipeline","lead generation","negotiation","quota","prospecting","closing","upsell","cross-sell","demo"],
    "finance": ["budgeting","forecasting","reconciliation","audit","financial analysis","p&l","variance","sap","tally","excel"],
    "customer service": ["crm","zendesk","freshdesk","sla","csat","ticketing","call handling","escalation","knowledge base","communication"],
}

def derive_resume_metrics(resume_text: str, role_title: str) -> Dict:
    t = normalize_text(resume_text)
    sections_present = any(k in t for k in ["experience", "work history"]) and ("education" in t) and ("skills" in t)
    single_column = True
    text_extractable = len(t) > 0

    action_verbs = ["led","built","created","designed","implemented","developed","optimized","increased","reduced","launched","migrated","improved","delivered"]
    action_verb_hits = sum(len(re.findall(rf"(^|\n|•|\-)\s*({v})\b", resume_text, flags=re.I)) for v in action_verbs)
    bullets = max(1, len(re.findall(r"(\n•|\n-|\n\d+\.)", resume_text)))
    action_verbs_per_bullet = min(1.0, action_verb_hits / bullets)

    quantified_bullets_ratio = min(
        1.0,
        len(re.findall(r"\b\d+(\.\d+)?%?|\b(k|m|bn)\b", resume_text, flags=re.I)) / max(1, bullets)
    )

    pages = max(1, round(len(resume_text) / 2000))
    avg_bullets_per_job = min(12.0, bullets / max(1, len(re.findall(r"\b(company|employer|experience)\b", t))))

    base_role = next((rk for rk in ROLE_KEYWORDS if rk in (role_title or "").lower()), None)
    kws = ROLE_KEYWORDS.get(base_role, [])
    kmr = keyword_match_rate(resume_text, kws) if kws else 0.0

    repetition_rate = 0.08 if "responsible for" not in t else 0.18
    jargon_rate = 0.12 if ("synergy" not in t and "leverage" not in t) else 0.22

    unique_skills_count = len(set(re.findall(r"[a-zA-Z][a-zA-Z0-9\+\#\.\-]{1,20}", resume_text))) // 50
    unique_skills_count = max(0, min(unique_skills_count, 15))

    return {
        "sections_present": sections_present,
        "single_column": single_column,
        "text_extractable": text_extractable,
        "action_verbs_per_bullet": action_verbs_per_bullet,
        "quantified_bullets_ratio": quantified_bullets_ratio,
        "keyword_match_rate": kmr,
        "pages": pages,
        "avg_bullets_per_job": avg_bullets_per_job,
        "repetition_rate": repetition_rate,
        "jargon_rate": jargon_rate,
        "unique_skills_count": unique_skills_count,
    }

def generate_pie_chart_v2(sections):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import io, base64

    # Only keep the five main aspects
    main_aspects = [
        "Format & Layout",
        "File Type & Parsing",
        "Section Headings & Structure",
        "Job-Title & Core Skills",
        "Dedicated Skills Section"
    ]

    labels = []
    sizes = []
    colors = ['#4CAF50', '#2196F3', '#FF9800', '#dc3545', '#673AB7']

    for aspect in main_aspects:
        if aspect in sections:
            score = sections[aspect].get('score', 0)
            labels.append(aspect)
            sizes.append(score)

    if not sizes or sum(sizes) == 0:
        return None  # Avoid division by zero

    fig, ax = plt.subplots(figsize=(10, 10), facecolor='#121212')
    wedges, texts, autotexts = ax.pie(
    sizes,
    autopct='%1.1f%%',
    colors=colors,
    textprops={'color': "white", 'fontsize': 20}  # ✅ Added font size here
    )
    plt.axis('equal')

    # Add space between pie and legend
    plt.subplots_adjust(bottom=0.25)  # Pushes legend down a bit

    # Legend
    legend_labels = [f"{label}: {size}" for label, size in zip(labels, sizes)]
    ax.legend(
        wedges,
        legend_labels,
        title="Main Aspects",
        loc='lower center',
        bbox_to_anchor=(0.5, -0.5),  # More negative moves it further down
        fontsize=20,
        title_fontsize=20,
        frameon=False,
        labelcolor='white'
    )


    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', facecolor='#121212')
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode('utf-8')
    buf.close()
    return encoded