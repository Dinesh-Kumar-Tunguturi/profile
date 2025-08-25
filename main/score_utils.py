# main/utils.py  — lean, serverless-friendly

from __future__ import annotations

import io
import os
import re
import json
from typing import Any, Dict, Iterable, List, Optional, Tuple

# Light-weight parsers only
from PyPDF2 import PdfReader
import docx2txt

# --- Config (env, no hard-coded secrets) ---
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
def _github_headers() -> Dict[str, str]:
    # Only add Authorization if a token is present
    h = {"Accept": "application/vnd.github.v3+json", "User-Agent": "applywizz"}
    if GITHUB_TOKEN:
        h["Authorization"] = f"token {GITHUB_TOKEN}"
    return h


# =========================
# Text extraction (PDF/DOCX)
# =========================

def _readall(file_or_bytes: Any) -> bytes:
    """Return bytes from a Django UploadedFile, file-like, or bytes/path."""
    if hasattr(file_or_bytes, "read"):
        pos = getattr(file_or_bytes, "tell", lambda: 0)()
        data = file_or_bytes.read()
        try:
            file_or_bytes.seek(pos)
        except Exception:
            pass
        return data
    if isinstance(file_or_bytes, (bytes, bytearray)):
        return bytes(file_or_bytes)
    if isinstance(file_or_bytes, str):
        with open(file_or_bytes, "rb") as f:
            return f.read()
    raise TypeError("Unsupported input for _readall()")

def extract_text_from_pdf(file_or_path: Any) -> str:
    """Fast, pure-Python PDF text via PyPDF2 (no pdfminer/fitz)."""
    try:
        b = _readall(file_or_path)
        reader = PdfReader(io.BytesIO(b))
        chunks = []
        for p in reader.pages:
            try:
                t = p.extract_text() or ""
            except Exception:
                t = ""
            if t:
                chunks.append(t)
        return "\n".join(chunks)
    except Exception:
        return ""

def extract_text_from_docx(file_or_path: Any) -> str:
    """DOCX text with docx2txt (write to temp only if needed)."""
    try:
        if isinstance(file_or_path, str):
            return docx2txt.process(file_or_path) or ""
        # docx2txt wants a path; write to a temp
        data = _readall(file_or_path)
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=True) as tmp:
            tmp.write(data); tmp.flush()
            return docx2txt.process(tmp.name) or ""
    except Exception:
        return ""


# =========================
# Link finding & helpers
# =========================

_URL_RE = r"https?://[^\s\)>\]\"'}]+"
_EMAIL_RE = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"

def extract_links_from_text(text: str) -> List[str]:
    return re.findall(_URL_RE, text or "")

def extract_links_from_pdf(file_or_path: Any) -> List[str]:
    """Cheaper: parse text & regex the URLs (no embedded-annotation crawl)."""
    return extract_links_from_text(extract_text_from_pdf(file_or_path))

def extract_applicant_name(resume_text: str) -> str:
    lines = [ln.strip() for ln in (resume_text or "").splitlines() if ln.strip()]
    return lines[0] if lines else "Applicant Name Not Found"

def extract_github_username(text: str) -> Optional[str]:
    m = re.search(r"github\.com/([A-Za-z0-9\-]+)", text or "", flags=re.I)
    return m.group(1) if m else None

def extract_leetcode_username(text: str) -> Optional[str]:
    m = re.search(r"leetcode\.com/(?:u/)?([\w\-]+)", text or "", flags=re.I)
    return m.group(1) if m else None


# =========================
# Light-weight scoring pieces
# =========================

def get_grade_tag(score: float | int) -> str:
    s = float(score)
    if s >= 85: return "Excellent"
    if s >= 70: return "Good"
    if s >= 50: return "Average"
    return "Poor"

def get_cert_suggestions(domain: str) -> List[str]:
    domain = (domain or "").lower()
    if domain in {"analytical", "data", "data analytics", "data science"}:
        return [
            "Google Data Analytics Professional Certificate – Coursera",
            "IBM Data Science Professional Certificate – Coursera",
            "Microsoft Certified: Azure Data Scientist Associate",
        ]
    if domain in {"technical", "software", "engineering"}:
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

TECHNICAL_WEIGHTS = {
    "GitHub Profile": 25,
    "LeetCode/DSA Skills": 20,
    "Portfolio Website": 20,
    "LinkedIn": 15,
    "Resume (ATS Score)": 10,
    "Certifications & Branding": 10,
}

def calculate_dynamic_ats_score(
    resume_text: str,
    github_username: Optional[str],
    leetcode_username: Optional[str],
    extracted_links: Optional[List[Dict[str, str]]] = None,
    domain: str = "Technical",
) -> Dict[str, Any]:
    """
    Pure-Python, no network required. Uses presence heuristics.
    """
    extracted_links = extracted_links or []
    def _has_link(kind: str) -> bool:
        return any((lk.get("type") or "").lower() == kind.lower() for lk in extracted_links)

    text = resume_text or ""
    has_github = bool(github_username) or ("github.com" in text.lower())
    has_lc = bool(leetcode_username) or ("leetcode.com" in text.lower())
    has_portfolio = bool(re.search(r"\b(netlify|vercel|github\.io|\.me|\.io|\.dev|\.app)\b", text, re.I))
    has_linkedin = _has_link("LinkedIn") or ("linkedin.com/in/" in text.lower())
    has_certs = bool(re.search(r"\b(certification|certified|certificate|course)\b", text, re.I))

    sections: Dict[str, Dict[str, Any]] = {}

    def sec(name: str, score: int) -> None:
        sections[name] = {
            "score": int(score),
            "grade": get_grade_tag(score),
        }

    # Heuristic scores (kept modest so your own ATS number can override)
    sec("GitHub Profile", 70 if has_github else 0)
    sec("LeetCode/DSA Skills", 60 if has_lc else 0)
    sec("Portfolio Website", 55 if has_portfolio else 0)
    sec("LinkedIn", 60 if has_linkedin else 0)
    sec("Resume (ATS Score)", 60)  # you usually overwrite this from ats_resume_scoring()
    sec("Certifications & Branding", 50 if has_certs else 0)

    suggestions: List[str] = []
    if not has_github: suggestions.append("Add a public GitHub link with recent activity.")
    if not has_lc: suggestions.append("Include your LeetCode (or equivalent) problem-solving profile.")
    if not has_portfolio: suggestions.append("Publish a portfolio (Netlify/Vercel/GitHub Pages) with 2–3 write-ups.")
    if not has_linkedin: suggestions.append("Link a public LinkedIn profile with a clear headline/summary.")
    if not has_certs: suggestions.append("Add 1–2 recent role-relevant certifications.")

    # Weighted blend to a small composite (not used directly in your UI today)
    total_score = sum(sections[k]["score"] * (TECHNICAL_WEIGHTS[k] / 100.0) for k in TECHNICAL_WEIGHTS if k in sections)
    overall_avg = round(sum(v["score"] for v in sections.values()) / max(1, len(sections)))

    return {
        "sections": sections,
        "total_score": int(round(total_score)),
        "overall_score_average": int(overall_avg),
        "overall_grade": get_grade_tag(overall_avg),
        "suggestions": suggestions,
    }


# =========================
# ATS subscore helpers (no heavy deps)
# =========================

def normalize_text(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "")).strip().lower()

def keyword_match_rate(text: str, target_keywords: List[str]) -> float:
    if not target_keywords: return 0.0
    t = normalize_text(text)
    hits = sum(1 for kw in target_keywords if kw.lower() in t)
    return hits / max(1, len(target_keywords))

ROLE_KEYWORDS = {
    "software engineer": ["python","java","javascript","react","node","docker","kubernetes","microservices","rest","graphql","aws","gcp","ci/cd","unit testing"],
    "data scientist": ["python","pandas","numpy","sklearn","tensorflow","pytorch","nlp","cv","statistics","sql","experiment","a/b testing","data visualization"],
    "devops engineer": ["ci/cd","docker","kubernetes","terraform","ansible","aws","gcp","azure","monitoring","prometheus","grafana","helm","sre"],
    "web developer": ["html","css","javascript","react","next.js","vue","node","express","rest","graphql","responsive","seo"],
    "mobile app developer": ["android","ios","kotlin","swift","flutter","react native","firebase","push notifications","play store","app store"],
    "human resources": ["recruitment","onboarding","payroll","employee engagement","hrms","policy","compliance","talent acquisition","grievance","training"],
    "marketing": ["seo","sem","campaign","content","email marketing","social media","analytics","branding","roi","conversion","google ads"],
    "sales": ["crm","pipeline","lead generation","negotiation","quota","prospecting","closing","upsell","cross-sell","demo"],
    "finance": ["budgeting","forecasting","reconciliation","audit","financial analysis","p&l","variance","sap","tally","excel"],
    "customer service": ["crm","zendesk","freshdesk","sla","csat","ticketing","call handling","escalation","knowledge base","communication"],
}

def derive_resume_metrics(resume_text: str, role_title: str) -> Dict[str, Any]:
    t = normalize_text(resume_text)
    sections_present = any(k in t for k in ["experience","work history"]) and ("education" in t) and ("skills" in t)
    single_column = True
    text_extractable = len(t) > 0

    action_verbs = ["led","built","created","designed","implemented","developed","optimized","increased","reduced","launched","migrated","improved","delivered"]
    av_hits = sum(len(re.findall(rf"(^|\n|•|\-)\s*({v})\b", resume_text, flags=re.I)) for v in action_verbs)
    bullets = max(1, len(re.findall(r"(\n•|\n-|\n\d+\.)", resume_text)))
    av_per_bullet = min(1.0, av_hits / bullets)

    quant_ratio = min(1.0, len(re.findall(r"\b\d+(\.\d+)?%?|\b(k|m|bn)\b", resume_text, flags=re.I)) / max(1, bullets))

    pages = max(1, round(len(resume_text) / 2000))
    avg_bullets_per_job = min(12.0, bullets / max(1, len(re.findall(r"\b(company|employer|experience)\b", t))))

    base_role = next((rk for rk in ROLE_KEYWORDS if rk in (role_title or "").lower()), None)
    kws = ROLE_KEYWORDS.get(base_role, [])
    kmr = keyword_match_rate(resume_text, kws) if kws else 0.0

    repetition_rate = 0.08 if "responsible for" not in t else 0.18
    jargon_rate = 0.12 if "synergy" not in t and "leverage" not in t else 0.22

    unique_skills_count = len(set(re.findall(r"[a-zA-Z][a-zA-Z0-9\+\#\.\-]{1,20}", resume_text))) // 50
    unique_skills_count = max(0, min(unique_skills_count, 15))

    return {
        "sections_present": sections_present,
        "single_column": single_column,
        "text_extractable": text_extractable,
        "action_verbs_per_bullet": av_per_bullet,
        "quantified_bullets_ratio": quant_ratio,
        "keyword_match_rate": kmr,
        "pages": pages,
        "avg_bullets_per_job": avg_bullets_per_job,
        "repetition_rate": repetition_rate,
        "jargon_rate": jargon_rate,
        "unique_skills_count": unique_skills_count,
    }

def ats_resume_scoring(metrics: Dict[str, Any]) -> Dict[str, Any]:
    b: Dict[str, Any] = {"items": []}
    total = 0
    MAX_ATS = 15

    pts_layout = int(bool(metrics.get("sections_present"))) + int(bool(metrics.get("single_column"))) + int(bool(metrics.get("text_extractable")))
    b["items"].append({"name": "ATS-friendly layout & structure", "earned": pts_layout, "max": 3})
    total += pts_layout

    av = float(metrics.get("action_verbs_per_bullet", 0.0))
    qr = float(metrics.get("quantified_bullets_ratio", 0.0))
    pts_actions = (2 if av >= 0.8 else 1 if av >= 0.5 else 0) + (2 if qr >= 0.6 else 1 if qr >= 0.3 else 0)
    b["items"].append({"name": "Action verbs & quantified results", "earned": pts_actions, "max": 4})
    total += pts_actions

    kmr = float(metrics.get("keyword_match_rate", 0.0))
    pts_keywords = 3 if kmr >= 0.75 else 2 if kmr >= 0.5 else 1 if kmr >= 0.3 else 0
    b["items"].append({"name": "Job-relevant keyword alignment", "earned": pts_keywords, "max": 3})
    total += pts_keywords

    pages = int(metrics.get("pages", 2))
    avg_bullets = float(metrics.get("avg_bullets_per_job", 6.0))
    pts_brev = (1 if pages <= 2 else 0) + (1 if avg_bullets <= 7 else 0)
    b["items"].append({"name": "Brevity & conciseness", "earned": pts_brev, "max": 2})
    total += pts_brev

    rep = float(metrics.get("repetition_rate", 0.15))
    jar = float(metrics.get("jargon_rate", 0.2))
    usk = int(metrics.get("unique_skills_count", 8))
    pts_clean = (1 if rep <= 0.10 else 0) + (1 if jar <= 0.15 else 0) + (1 if usk >= 8 else 0)
    b["items"].append({"name": "Minimal jargon / repetition", "earned": pts_clean, "max": 3})
    total += pts_clean

    b["subtotal"] = {"earned": total, "max": MAX_ATS}
    b["score_100"] = int(round((total / MAX_ATS) * 100))
    return b
