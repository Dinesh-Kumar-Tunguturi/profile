# app/views.py

from __future__ import annotations

import os
import re
import io
import base64
import random
import tempfile
from typing import Dict, List

from django.conf import settings
from django.core.mail import send_mail
from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest
from django.shortcuts import render, redirect
from django.template.loader import get_template
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

# Twilio (use environment/setting variables, not hard-coded)
from twilio.rest import Client

# ========= Your utils (as referenced in your file) =========
from .utils import (
    extract_text_from_pdf,
    extract_text_from_docx,
    extract_applicant_name,
    extract_github_username,
    extract_leetcode_username,
    calculate_dynamic_ats_score,
)

# If you really need DOC parsing of legacy .doc:
# from .utils import extract_text_from_doc  # uncomment if available

# Non-technical scoring module (you referenced these)
from .ats_score_non_tech import ats_scoring_non_tech_v2  # keep only the one you use

# Role-based certifications (clean “Title – Issuer”, max 6)
from .services.certifications import suggest_role_certifications


# PDF export
from xhtml2pdf import pisa


# ========= In-memory OTP stores (not for production) =========
otp_storage: Dict[str, str] = {}
signup_otp_storage: Dict[str, str] = {}


# ========= Plans =========
PLANS = {
    1: {"name": "Applywizz Resume", "price": 499, "description": "Builds a resume with the highest ATS score."},
    2: {"name": "Resume + Profile Portfolio", "price": 999, "description": "Includes Resume building and a professional Portfolio Website."},
    3: {"name": "All-in-One Package", "price": 2999, "description": "Includes Resume, Portfolio, and applying to jobs on your behalf."},
}


# ========= Basic pages =========
def landing(request):
    return render(request, "landing.html")

def signin(request):
    return render(request, "login.html")

def login_view(request):
    return render(request, "login.html")

def signup(request):
    return render(request, "login.html")

def about_us(request):
    return render(request, "about_us.html")

def why(request):
    return render(request, "why.html")

def who(request):
    return render(request, "who.html")


# ========= Twilio Verify (OTP over SMS) =========
# Configure in settings:
# TWILIO_ACCOUNT_SID = "ACxxxx"
# TWILIO_AUTH_TOKEN  = "xxxx"
# TWILIO_VERIFY_SID  = "VAxxxx"


# from django.views.decorators.csrf import csrf_exempt
# from django.http import JsonResponse
# from django.conf import settings
# from twilio.rest import Client

# def _twilio_client():
#     account_sid = getattr(settings, "TWILIO_ACCOUNT_SID", None)
#     auth_token = getattr(settings, "TWILIO_AUTH_TOKEN", None)
#     if not account_sid or not auth_token:
#         raise Exception("Twilio credentials not configured")
#     return Client(account_sid, auth_token)

# @csrf_exempt
# def send_otp(request):
#     if request.method != "POST":
#         return JsonResponse({"status": "error", "message": "Invalid request method"}, status=405)

#     mobile = request.POST.get("mobile", "").strip()
#     if not mobile or len(mobile) != 10 or not mobile.isdigit():
#         return JsonResponse({"status": "error", "message": "Invalid mobile number"}, status=400)

#     # Check if mobile is registered
#     if mobile not in registered_users:
#         return JsonResponse({"status": "error", "message": "Mobile number not registered. Please sign up first."}, status=400)

#     client = _twilio_client()
#     verify_sid = getattr(settings, "TWILIO_VERIFY_SID", None)
#     if not verify_sid:
#         return JsonResponse({"status": "error", "message": "Twilio Verify SID not configured"}, status=500)

#     try:
#         verification = client.verify.v2.services(verify_sid).verifications.create(
#             to=f"+91{mobile}",
#             channel="sms"
#         )
#         return JsonResponse({"status": "success", "message": "OTP sent successfully"})
#     except Exception as e:
#         return JsonResponse({"status": "error", "message": f"Error sending OTP: {str(e)}"}, status=500)



# @csrf_exempt
# def verify_otp(request):
#     if request.method != "POST":
#         return JsonResponse({"status": "error", "message": "Invalid request method"}, status=405)

#     mobile = request.POST.get("mobile", "").strip()
#     otp = request.POST.get("otp", "").strip()

#     if not mobile or not otp:
#         return JsonResponse({"status": "error", "message": "Mobile and OTP required"}, status=400)

#     client = _twilio_client()
#     verify_sid = getattr(settings, "TWILIO_VERIFY_SID", None)
#     if not verify_sid:
#         return JsonResponse({"status": "error", "message": "Twilio Verify SID not configured"}, status=500)

#     try:
#         verification_check = client.verify.v2.services(verify_sid).verification_checks.create(
#             to=f"+91{mobile}",
#             code=otp
#         )
#         if verification_check.status == "approved":
#             # You can authenticate user here or create session as needed
#             return JsonResponse({"status": "success", "redirect_url": "/upload_resume"})
#         else:
#             return JsonResponse({"status": "error", "message": "Invalid OTP"}, status=400)
#     except Exception as e:
#         return JsonResponse({"status": "error", "message": f"Error verifying OTP: {str(e)}"}, status=500)


# For demo: in-memory user storage, use real DB
registered_users = {}  # key: mobile, value: email

signup_otp_storage = {}

import random, re
from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

# Optional: keep your in-memory mapping if you're using it elsewhere
registered_users = {}   # {mobile:str -> email:str}

OTP_TTL_SECONDS = 300  # 5 minutes

def norm_email(email: str) -> str:
    return (email or "").strip().lower()

def norm_mobile(mobile: str) -> str:
    # Keep digits only; e.g., "+91 94945-57188" -> "919494557188"
    return re.sub(r"\D+", "", (mobile or "").strip())

def send_otp_email(to_email: str, otp: str, subject: str):
    send_mail(
        subject=subject,
        message=f"Your OTP is {otp}. It will expire in {OTP_TTL_SECONDS // 60} minutes.",
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@applywizz.com"),
        recipient_list=[to_email],
        fail_silently=False,
    )

# ---------------------------
# SIGNUP (email + mobile) -> OTP to email
# ---------------------------
@csrf_exempt
def send_signup_otp(request):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Invalid request"}, status=405)

    email_raw = request.POST.get("email", "")
    mobile_raw = request.POST.get("mobile", "")
    email = norm_email(email_raw)
    mobile = norm_mobile(mobile_raw)

    if not email or not mobile:
        return JsonResponse({"status": "error", "message": "Email and mobile required"}, status=400)

    otp = f"{random.randint(100000, 999999)}"
    cache_key = f"signup_otp:{email}:{mobile}"
    cache.set(cache_key, otp, timeout=OTP_TTL_SECONDS)

    try:
        send_otp_email(email, otp, subject="Your ApplyWizz Signup OTP")
        return JsonResponse({"status": "success", "message": "OTP sent to your email"})
    except Exception as e:
        return JsonResponse({"status": "error", "message": f"Failed to send OTP: {e}"}, status=500)

@csrf_exempt
def verify_signup_otp(request):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Invalid request"}, status=405)

    email = norm_email(request.POST.get("email", ""))
    mobile = norm_mobile(request.POST.get("mobile", ""))
    otp = (request.POST.get("otp", "") or "").strip()

    cache_key = f"signup_otp:{email}:{mobile}"
    stored_otp = cache.get(cache_key)

    if stored_otp and stored_otp == otp:
        # Register user (store mapping as you already do)
        registered_users[mobile] = email
        cache.delete(cache_key)
        return JsonResponse({"status": "success", "redirect_url": "/login"})
    else:
        return JsonResponse({"status": "error", "message": "Invalid or expired OTP"}, status=400)

# ---------------------------
# LOGIN (email only) -> OTP to email
# ---------------------------
@csrf_exempt
def send_login_otp(request):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Invalid request"}, status=405)

    email = norm_email(request.POST.get("email", ""))
    if not email:
        return JsonResponse({"status": "error", "message": "Email required"}, status=400)

    otp = f"{random.randint(100000, 999999)}"
    cache_key = f"login_otp:{email}"
    cache.set(cache_key, otp, timeout=OTP_TTL_SECONDS)

    try:
        send_otp_email(email, otp, subject="Your ApplyWizz Login OTP")
        return JsonResponse({"status": "success", "message": "OTP sent to your email"})
    except Exception as e:
        return JsonResponse({"status": "error", "message": f"Failed to send OTP: {e}"}, status=500)

@csrf_exempt
def verify_login_otp(request):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Invalid request"}, status=405)

    email = norm_email(request.POST.get("email", ""))
    otp = (request.POST.get("otp", "") or "").strip()

    cache_key = f"login_otp:{email}"
    stored_otp = cache.get(cache_key)

    if stored_otp and stored_otp == otp:
        cache.delete(cache_key)
        # TODO: log the user in (set session) if you have a User model
        return JsonResponse({"status": "success", "redirect_url": "/upload_resume"})
    else:
        return JsonResponse({"status": "error", "message": "Invalid or expired OTP"}, status=400)

# ========= Upload page =========
def upload_resume(request):
    return render(request, "upload_resume.html")


# ========= Pie chart helper (dark theme friendly) =========
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from typing import Dict
import io, base64
import matplotlib.pyplot as plt

from typing import Dict
import io, base64
import matplotlib.pyplot as plt

def generate_pie_chart_tech(sections: Dict) -> str | None:
    """
    sections: { "Section Name": {"score": number}, ... }
    Returns base64 PNG string or None if no data.
    No percentages inside slices; legend (2 per row) shown at the bottom.
    """
    labels, sizes = [], []
    for label, data in (sections or {}).items():
        score = data.get("score", 0)
        if isinstance(score, (int, float)) and score == score:  # not NaN
            labels.append(label)
            sizes.append(float(score))

    if not sizes or sum(sizes) == 0:
        return None

    fig, ax = plt.subplots(figsize=(8, 8), facecolor="#121212")

    # Pie without percentages or labels inside slices
    wedges = ax.pie(
        sizes,
        labels=None,  # keep interior clean
    )[0]

    # Legend at bottom with slice colors
    ax.legend(
        wedges,
        labels,
        loc="lower center",
        bbox_to_anchor=(0.5, -0.15),
        fontsize=18,
        frameon=False,
        labelcolor="white",
        ncol=2,  # Two per row
        title="Categories",
        title_fontsize=13
    )

    ax.set_facecolor("#121212")
    plt.axis("equal")
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", facecolor="#121212")
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode("utf-8")
    buf.close()
    plt.close(fig)
    return encoded





# ========= TECHNICAL ANALYZE → report_technical.html =========
# --- Helper for stable cache key ---
import hashlib, json

def _make_result_key(role_type: str, role_slug: str, resume_text: str, github_username: str = "", leetcode_username: str = "") -> str:
    payload = json.dumps({
        "role_type": role_type,
        "role_slug": role_slug,
        "resume_hash": hashlib.sha256((resume_text or "").encode("utf-8")).hexdigest(),
        "github": github_username or "",
        "leetcode": leetcode_username or "",
    }, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# --- Read-only report views (no recompute on refresh) ---
def show_report_technical(request):
    ctx = request.session.get("resume_context_tech")
    if not ctx:
        return redirect("upload_page")
    return render(request, "resume_result.html", ctx)

def show_report_nontechnical(request):
    ctx = request.session.get("resume_context_nontech")
    if not ctx:
        return redirect("upload_page")
    return render(request, "score_of_non_tech.html", ctx)

from collections import OrderedDict

def _ordered_sections(sections):
    key_mapping = {
        "ATS": "Resume (ATS Readiness)",
        "GitHub": "GitHub Score",
        "LeetCode": "LeetCode Score",
        "LinkedIn": "LinkedIn Profile",
        "Portfolio": "Portfolio",
        "Certifications": "Certifications",
    }

    desired_order = ["ATS", "GitHub", "LeetCode", "LinkedIn", "Portfolio", "Certifications"]

    ordered = []
    for name in desired_order:
        key = key_mapping.get(name)
        if key and key in sections:
            ordered.append((key, sections[key]))

    existing_keys = {k for k, _ in ordered}
    for key, value in sections.items():
        if key not in existing_keys:
            ordered.append((key, value))

    return ordered






# ========= TECHNICAL ANALYZE (PRG) =========

from django.shortcuts import render
from django.views.decorators.http import require_POST
import os

from django.views.decorators.http import require_POST
from django.shortcuts import render
from django.http import HttpResponseBadRequest
import os

from django.views.decorators.http import require_POST
from django.shortcuts import render
from django.http import HttpResponseBadRequest
import os

def _quick_resume_ats_percent(resume_text: str, role_title: str) -> float:
    """
    Heuristic ATS% (0–100) for non-technical: mirrors your ATS subcriteria.
    """
    t = _norm(resume_text)
    # Sections
    sections_present = any(k in t for k in ["experience","work history"]) and ("education" in t) and ("skills" in t)
    single_column = True  # assume ok unless you detect otherwise
    text_extractable = len(t) > 0
    pts_layout = int(sections_present) + int(single_column) + int(text_extractable)  # /3

    # Action verbs & quantified
    action_verbs = ["led","built","created","designed","implemented","developed","optimized","increased","reduced","launched","improved","delivered"]
    bullets = max(1, len(re.findall(r"(\n•|\n-|\n\d+\.)", resume_text)))
    av_hits = sum(len(re.findall(rf"(^|\n|•|\-)\s*({v})\b", resume_text, flags=re.I)) for v in action_verbs)
    av_per_bullet = min(1.0, av_hits / bullets)
    quant_ratio = min(1.0, len(re.findall(r"\b\d+(\.\d+)?%?|\b(k|m|bn)\b", resume_text, flags=re.I)) / bullets)
    pts_actions = (2 if av_per_bullet >= 0.8 else 1 if av_per_bullet >= 0.5 else 0) \
                + (2 if quant_ratio >= 0.6 else 1 if quant_ratio >= 0.3 else 0)     # /4

    # Keywords
    kws = _NONTECH_ROLE_KEYWORDS.get(role_title, [])
    cover = 0.0
    if kws:
        cover = sum(1 for k in kws if k in t) / len(kws)
    pts_kw = 3 if cover >= 0.75 else 2 if cover >= 0.5 else 1 if cover >= 0.3 else 0  # /3

    # Brevity
    pages = max(1, round(len(resume_text) / 2000))
    avg_bullets = bullets / max(1, len(re.findall(r"\b(company|employer|experience)\b", t)))
    pts_brev = (1 if pages <= 2 else 0) + (1 if avg_bullets <= 7 else 0)              # /2

    # Jargon / repetition
    rep = 0.18 if "responsible for" in t else 0.08
    jar = 0.22 if any(j in t for j in ["synergy","leverage"]) else 0.12
    unique_skills_count = len(set(re.findall(r"[a-zA-Z][a-zA-Z0-9\+\#\.\-]{1,20}", resume_text))) // 50
    pts_clean = (1 if rep <= 0.10 else 0) + (1 if jar <= 0.15 else 0) + (1 if unique_skills_count >= 8 else 0)  # /3

    earned = pts_layout + pts_actions + pts_kw + pts_brev + pts_clean  # max 15
    return round((earned / 15.0) * 100.0, 2)


from .utils import derive_resume_metrics, ats_resume_scoring

@require_POST
def analyze_resume(request):
    if request.POST.get("domain") != "technical":
        return HttpResponseBadRequest("Please choose the Technical category.")

    if "resume" not in request.FILES:
        return HttpResponseBadRequest("Resume file is required.")

    resume_file = request.FILES["resume"]
    ext = os.path.splitext(resume_file.name)[1].lower()

    # Extract text from resume file
    if ext == ".pdf":
        resume_text = extract_text_from_pdf(resume_file)
    elif ext == ".docx":
        resume_text = extract_text_from_docx(resume_file)
    else:
        return HttpResponseBadRequest("Unsupported file format. Please upload a PDF or DOCX.")

    applicant_name = extract_applicant_name(resume_text) or "Candidate"
    github_username = (request.POST.get("github_username") or "").strip() or extract_github_username(resume_text) or ""
    leetcode_username = (request.POST.get("leetcode_username") or "").strip() or extract_leetcode_username(resume_text) or ""

    role_slug = request.POST.get("tech_role", "software_engineer")
    TECH_ROLE_MAP = {
        "software_engineer": "Software Engineer",
        "data_scientist": "Data Scientist",
        "devops_engineer": "DevOps Engineer",
        "web_developer": "Web Developer",
        "mobile_developer": "Mobile App Developer",
    }
    role_title = TECH_ROLE_MAP.get(role_slug, "Software Engineer")

    # Use your utils function to derive metrics
    metrics = derive_resume_metrics(resume_text, role_title)

    # Use ats_resume_scoring (from utils.py) to get ATS Resume scoring dict
    ats_resume_score_dict = ats_resume_scoring(metrics)
    metrics = derive_resume_metrics(resume_text, role_title)
    ats_resume_score_dict = ats_resume_scoring(metrics)

    # Prefer normalized score_100; fall back to computing it from subtotal if missing
    raw_100 = ats_resume_score_dict.get("score_100")
    if raw_100 is None:
        earned = ats_resume_score_dict.get("subtotal", {}).get("earned", 0)
        max_pts = ats_resume_score_dict.get("subtotal", {}).get("max", 15) or 15
        raw_100 = round((earned / max_pts) * 100)

    # Always keep it < 90
    ats_resume_score = max(0, min(89, int(raw_100)))



    # Calculate full ATS result (may have other sections)
    ats_result = calculate_dynamic_ats_score(
        resume_text=resume_text,
        github_username=github_username,
        leetcode_username=leetcode_username,
        extracted_links=[],
    )
    sections = ats_result.get("sections", {})

    # Override the ATS score in sections dict to your computed one from ats_resume_scoring
    # Get the original Resume (ATS Score) section if it exists
    original_ats_section = sections.get("Resume (ATS Score)", {})

    # Update only the score, keep grade and sub_criteria as is (or empty defaults)
    sections["Resume (ATS Score)"] = {
        "score": ats_resume_score,
        "grade": original_ats_section.get("grade", ""),
        "sub_criteria": original_ats_section.get("sub_criteria", ats_resume_score_dict.get("items", [])),
    }


    # Define desired order of sections for display
    desired_order = [
        "Resume (ATS Score)",
        "GitHub Profile",
        "Portfolio Website",
        "LeetCode/DSA Skills",
        "LinkedIn",
        "Certifications & Branding",
    ]

    # Prepare ordered sections list
    score_breakdown_ordered = []
    for key in desired_order:
        if key in sections:
            score_breakdown_ordered.append((key, sections[key]))
    # Append any other sections not in desired_order at the end
    for key, val in sections.items():
        if key not in desired_order:
            score_breakdown_ordered.append((key, val))

    pie_chart_image = generate_pie_chart_tech(sections)
    overall_score_average = int(ats_result.get("overall_score_average", 0))
    suggestions = (ats_result.get("suggestions") or [])[:2]
    recommended_certs = suggest_role_certifications(role_title)

    context = {
        "result_key": _make_result_key("technical", role_slug, resume_text, github_username, leetcode_username),
        "applicant_name": applicant_name,
        "contact_detection": "YES" if any(s in resume_text.lower() for s in ["@", "phone", "email"]) else "NO",
        "linkedin_detection": "YES" if "linkedin.com" in resume_text.lower() else "NO",
        "github_detection": "YES" if ("github.com" in resume_text.lower() or github_username) else "NO",
        "ats_score": ats_resume_score,  # This is the ATS Resume score from ats_resume_scoring
        "overall_score_average": overall_score_average,
        "overall_grade": ats_result.get("overall_grade", ""),
        "score_breakdown": sections,
        "score_breakdown_ordered": score_breakdown_ordered,
        "pie_chart_image": pie_chart_image,
        "missing_certifications": recommended_certs,
        "suggestions": suggestions,
        "role": role_title,
    }

    request.session["resume_context_tech"] = context
    request.session.modified = True
    return redirect("show_report_technical")






# --- Non-technical helpers (self-contained) ---

import re

_NONTECH_ROLE_KEYWORDS = {
    "Human Resources": ["recruitment","hiring","onboarding","payroll","hrms","policy","compliance","talent acquisition","employee engagement","grievance","training","performance review"],
    "Marketing": ["seo","sem","campaign","content","email marketing","social media","branding","analytics","conversion","google ads","meta ads","roi","copywriting"],
    "Sales": ["crm","pipeline","lead generation","prospecting","negotiation","quota","closing","upsell","cross-sell","demo","forecast"],
    "Finance": ["budgeting","forecasting","reconciliation","audit","financial analysis","p&l","variance","gl","sap","tally","excel","balance sheet","cash flow"],
    "Customer Service": ["crm","zendesk","freshdesk","sla","csat","ticketing","call handling","escalation","knowledge base","aht","nps","first call resolution"],
}

def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "").lower()).strip()

def _quick_resume_ats_percent(resume_text: str, role_title: str) -> float:
    """
    Heuristic ATS% (0–100) for non-technical: mirrors your ATS subcriteria.
    """
    t = _norm(resume_text)
    # Sections
    sections_present = any(k in t for k in ["experience","work history"]) and ("education" in t) and ("skills" in t)
    single_column = True  # assume ok unless you detect otherwise
    text_extractable = len(t) > 0
    pts_layout = int(sections_present) + int(single_column) + int(text_extractable)  # /3

    # Action verbs & quantified
    action_verbs = ["led","built","created","designed","implemented","developed","optimized","increased","reduced","launched","improved","delivered"]
    bullets = max(1, len(re.findall(r"(\n•|\n-|\n\d+\.)", resume_text)))
    av_hits = sum(len(re.findall(rf"(^|\n|•|\-)\s*({v})\b", resume_text, flags=re.I)) for v in action_verbs)
    av_per_bullet = min(1.0, av_hits / bullets)
    quant_ratio = min(1.0, len(re.findall(r"\b\d+(\.\d+)?%?|\b(k|m|bn)\b", resume_text, flags=re.I)) / bullets)
    pts_actions = (2 if av_per_bullet >= 0.8 else 1 if av_per_bullet >= 0.5 else 0) \
                + (2 if quant_ratio >= 0.6 else 1 if quant_ratio >= 0.3 else 0)     # /4

    # Keywords
    kws = _NONTECH_ROLE_KEYWORDS.get(role_title, [])
    cover = 0.0
    if kws:
        cover = sum(1 for k in kws if k in t) / len(kws)
    pts_kw = 3 if cover >= 0.75 else 2 if cover >= 0.5 else 1 if cover >= 0.3 else 0  # /3

    # Brevity
    pages = max(1, round(len(resume_text) / 2000))
    avg_bullets = bullets / max(1, len(re.findall(r"\b(company|employer|experience)\b", t)))
    pts_brev = (1 if pages <= 2 else 0) + (1 if avg_bullets <= 7 else 0)              # /2

    # Jargon / repetition
    rep = 0.18 if "responsible for" in t else 0.08
    jar = 0.22 if any(j in t for j in ["synergy","leverage"]) else 0.12
    unique_skills_count = len(set(re.findall(r"[a-zA-Z][a-zA-Z0-9\+\#\.\-]{1,20}", resume_text))) // 50
    pts_clean = (1 if rep <= 0.10 else 0) + (1 if jar <= 0.15 else 0) + (1 if unique_skills_count >= 8 else 0)  # /3

    earned = pts_layout + pts_actions + pts_kw + pts_brev + pts_clean  # max 15
    return round((earned / 15.0) * 100.0, 2)

def _role_match_percent(resume_text: str, role_title: str) -> tuple[float, dict]:
    """
    Role-Match% (0–100) from keyword coverage + density.
    Weighted 70% coverage, 30% density.
    """
    t = _norm(resume_text)
    kws = _NONTECH_ROLE_KEYWORDS.get(role_title, [])
    if not kws:
        return 0.0, {"keywords": [], "coverage": 0.0, "occurrences": 0}

    coverage_hits = sum(1 for k in kws if k in t)
    coverage = coverage_hits / len(kws)
    pattern = "|".join(map(re.escape, kws))
    occurrences = len(re.findall(pattern, t))
    density = min(1.0, occurrences / (len(kws) * 2))

    score = 0.70 * coverage + 0.30 * density
    return round(score * 100.0, 2), {"keywords": kws, "coverage": round(coverage, 2), "occurrences": occurrences}



# ========= NON-TECHNICAL ANALYZE (PRG) =========
from .utils import *
from .utils import (
    extract_text_from_pdf,
    extract_text_from_docx,
    extract_applicant_name,
    extract_github_username,
    extract_leetcode_username,
    calculate_dynamic_ats_score,
    extract_links_from_pdf  # <- Make sure this exists
)
@require_POST
def analyze_resume_v2(request):
    context = {
        "applicant_name": "N/A",
        "ats_score": 0,
        "overall_score_average": 0,
        "overall_grade": "N/A",
        "score_breakdown": {},
        "suggestions": [],
        "pie_chart_image": None,
        "detected_links": [],
        "error": None,
        "contact_detection": "NO",
        "github_detection": "NO",
        "linkedin_detection": "NO",
    }

    if request.method == 'POST' and request.FILES.get('resume'):
        resume_file = request.FILES['resume']
        ext = os.path.splitext(resume_file.name)[1].lower()

        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            for chunk in resume_file.chunks():
                tmp.write(chunk)
            temp_path = tmp.name

        if ext not in [".pdf", ".docx", ".doc"]:
            context["error"] = "Unsupported file format. Please upload a PDF, DOCX, or DOC file."
            return render(request, 'score_of_non_tech.html', context)

        if ext == ".pdf":
            extracted_links, resume_text = extract_links_combined(temp_path)
        elif ext == ".docx":
            resume_text = extract_text_from_docx(temp_path)
            extracted_links = []
        else:
            resume_text = extract_text_from_doc(temp_path)
            extracted_links = []

        # Normalize text lowercase for detection
        text_lower = resume_text.lower()

        # Contact detection: check for common indicators
        contact_detection = "YES" if any(x in text_lower for x in ["@", "phone", "email"]) else "NO"

        # GitHub detection: check for github link or username in links
        github_detection = "YES" if ("github.com" in text_lower or any("github.com" in link for link in extracted_links)) else "NO"

        # LinkedIn detection: check for linkedin link in text or extracted links
        linkedin_detection = "YES" if ("linkedin.com" in text_lower or any("linkedin.com" in link for link in extracted_links)) else "NO"

        applicant_name = extract_applicant_name(resume_text) or "N/A"

        # Role title for non-tech (you can set as per your logic or default)
        role_title = request.POST.get("role_title", "human resources")  # or some default non-tech role

        # Calculate ATS resume score using utils
        metrics = derive_resume_metrics(resume_text, role_title)
        ats_resume_score_dict = ats_resume_scoring(metrics)
        metrics = derive_resume_metrics(resume_text, role_title)
        ats_resume_score_dict = ats_resume_scoring(metrics)

        # Prefer normalized score_100; fall back to computing it from subtotal if missing
        raw_100 = ats_resume_score_dict.get("score_100")
        if raw_100 is None:
            earned = ats_resume_score_dict.get("subtotal", {}).get("earned", 0)
            max_pts = ats_resume_score_dict.get("subtotal", {}).get("max", 15) or 15
            raw_100 = round((earned / max_pts) * 100)

        # Always keep it < 90
        ats_resume_score = max(0, min(89, int(raw_100)))  # 100→89, 90→80, 73→65
 # scale to 0-100

        # Calculate other ATS scoring as needed
        ats_result = ats_scoring_non_tech_v2(temp_path)

        context.update({
            "applicant_name": applicant_name,
            "ats_score": ats_resume_score,  # use calculated ATS score here
            "overall_score_average": ats_result.get("overall_score_average", 0),
            "overall_grade": ats_result.get("overall_grade", "N/A"),
            "score_breakdown": ats_result.get("score_breakdown", {}),
            "pie_chart_image": ats_result.get("pie_chart_image"),
            "suggestions": ats_result.get("suggestions", []),
            "detected_links": extracted_links,
            "contact_detection": contact_detection,
            "github_detection": github_detection,
            "linkedin_detection": linkedin_detection,
        })

    return render(request, 'score_of_non_tech.html', context)


# ========= PDF download (server-side render) =========
from django.template.loader import get_template
from django.http import HttpResponse
from weasyprint import HTML, CSS

def download_resume_pdf(request):
    """
    Renders the last analysis context from session into a PDF using WeasyPrint.
    """
    context = request.session.get("resume_context_tech") # Assuming you want to use the tech context
    if not context:
        # Fallback to non-tech context if technical is not found
        context = request.session.get("resume_context_nontech")
    
    if not context:
        return HttpResponse("No resume analysis found in session.", status=404)

    # Choose template dynamically based on the context
    if context.get("role") in ["Human Resources", "Marketing", "Sales", "Finance", "Customer Service"]:
        template_path = "score_of_non_tech.html"
    else:
        template_path = "resume_result.html"

    template = get_template(template_path)
    html_string = template.render(context)

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="resume_report.pdf"'

    # Generate PDF using WeasyPrint
    try:
        HTML(string=html_string).write_pdf(response)
    except Exception as e:
        return HttpResponse(f"Error generating PDF: {str(e)}", status=500)
    
    return response

# views.py (add these)

from django.urls import reverse
import hashlib
import json

def _make_result_key(role_type: str, role_slug: str, resume_text: str, github_username: str = "", leetcode_username: str = "") -> str:
    payload = json.dumps({
        "role_type": role_type,
        "role_slug": role_slug,
        "resume_hash": hashlib.sha256((resume_text or "").encode("utf-8")).hexdigest(),
        "github": github_username or "",
        "leetcode": leetcode_username or "",
    }, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def show_report_technical(request):
    ctx = request.session.get("resume_context_tech")
    if not ctx:
        # nothing cached: send back to upload
        return redirect("upload_page")
    return render(request, "resume_result.html", ctx)

def show_report_nontechnical(request):
    ctx = request.session.get("resume_context_nontech")
    if not ctx:
        return redirect("upload_page")
    return render(request, "score_of_non_tech.html", ctx)


