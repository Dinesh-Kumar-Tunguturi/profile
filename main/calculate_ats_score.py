import os
import re
import PyMuPDF
import docx
import requests
from django.shortcuts import render
from django.http import HttpResponse

# ----------- Resume Text Extraction -----------

def extract_text_from_pdf(path):
    text = ""
    doc = fitz.open(path)
    for page in doc:
        text += page.get_text()
    return text

def extract_text_from_docx(path):
    doc = docx.Document(path)
    return "\n".join([para.text for para in doc.paragraphs])

# ----------- Link Extractors -----------

def extract_link(pattern, text):
    match = re.search(pattern, text)
    return match.group(0) if match else None

# ----------- GitHub Section (25 pts) -----------

def score_github(github_url):
    score = 0
    if not github_url:
        return score

    score += 3  # Link present
    username = github_url.rstrip("/").split("/")[-1]
    api_url = f"https://api.github.com/users/{username}"
    repos_url = f"https://api.github.com/users/{username}/repos"

    try:
        profile = requests.get(api_url).json()
        repos = requests.get(repos_url).json()

        # Sort repos for consistent scoring
        if isinstance(repos, list):
            repos = sorted(repos, key=lambda r: r.get("name", ""))

            if len(repos) >= 3:
                score += 5  # 3+ pinned repos

            if any('pushed_at' in repo for repo in repos):
                score += 5  # Assume active recently for demo

            if any(repo.get("description") and any(keyword in repo["description"].lower()
                                                  for keyword in ["ml", "web", "data", "django", "flask", "api"])
                   for repo in repos):
                score += 6

            if any(repo.get("has_wiki") or "readme" in repo.get("name", "").lower() for repo in repos):
                score += 6

    except:
        pass

    return min(score, 25)

# ----------- LeetCode Section (20 pts) -----------

def score_leetcode(leetcode_url):
    score = 0
    if not leetcode_url:
        return score

    score += 2  # Link present
    username = leetcode_url.rstrip("/").split("/")[-1]

    query = {
        "query": """
        query getUserProfile($username: String!) {
          matchedUser(username: $username) {
            submitStatsGlobal {
              acSubmissionNum {
                difficulty
                count
              }
            }
            contestBadge {
              name
            }
          }
        }
        """,
        "variables": {"username": username}
    }

    try:
        res = requests.post("https://leetcode.com/graphql/", json=query)
        data = res.json()
        user = data["data"].get("matchedUser")
        if not user:
            return score

        solved = user["submitStatsGlobal"]["acSubmissionNum"]
        total = sum(i['count'] for i in solved)
        medium_or_hard = sum(i['count'] for i in solved if i['difficulty'] in ['Medium', 'Hard'])

        if total >= 100:
            score += 5
        if medium_or_hard >= 30:
            score += 4
        if user.get("contestBadge"):
            score += 4
        if len(solved) >= 4:  # multiple topics
            score += 5
    except:
        pass

    return min(score, 20)

# ----------- Portfolio Section (15 pts) -----------

def score_portfolio(portfolio_url):
    return 15 if portfolio_url else 0

# ----------- LinkedIn Section (10 pts) -----------

def score_linkedin(linkedin_url, resume_text):
    if not linkedin_url:
        return 0

    score = 1  # Link present
    text_lower = resume_text.lower()

    if "summary" in text_lower or "headline" in text_lower:
        score += 2
    if "endorsement" in text_lower or "skills" in text_lower:
        score += 2
    if "github" in text_lower or "portfolio" in text_lower:
        score += 2
    if "post" in text_lower or "activity" in text_lower:
        score += 3

    return min(score, 10)

# ----------- Resume Structure Score (15 pts) -----------

def score_resume_structure(text):
    score = 0
    text_lower = text.lower()
    if len(text.split()) < 1200:
        score += 2
    score += 3
    if any(x in text_lower for x in ["increased", "improved", "achieved", "%", "reduced"]):
        score += 4
    if any(x in text_lower for x in ["python", "developer", "engineer", "ml", "ai"]):
        score += 3
    score += 3

    return min(score, 15)

# ----------- Certifications Score (15 pts) -----------

def score_certifications(text):
    score = 0
    lines = text.lower().splitlines()
    cert_keywords = ["coursera", "ibm", "aws", "google", "data", "certificate", "udemy", "microsoft"]
    recent_keywords = ["2023", "2024", "2025"]
    cert_lines = [line for line in lines if any(k in line for k in cert_keywords)]

    if len(cert_lines) > 0:
        score += 5
    if any(platform in line for platform in cert_keywords for line in cert_lines):
        score += 5
    if any(date in line for date in recent_keywords for line in cert_lines):
        score += 3
    if any("coursera" in line and "certificate" in line for line in cert_lines):
        score += 2

    return min(score, 15)

# ----------- Final Grade -----------

def grade_from_score(score):
    if score >= 85:
        return "✅ Job-Ready Candidate"
    elif score >= 70:
        return "⚠️ Good Start"
    else:
        return "🚫 Needs Major Fixes"

# ----------- Main Django View -----------

def upload_resume(request):
    if request.method == 'POST':
        resume = request.FILES.get('resume')
        if not resume:
            return HttpResponse("No resume uploaded.")

        # Save resume file temporarily
        path = f'temp/{resume.name}'
        os.makedirs('temp', exist_ok=True)
        with open(path, 'wb+') as dest:
            for chunk in resume.chunks():
                dest.write(chunk)

        # Extract text
        if resume.name.endswith('.pdf'):
            text = extract_text_from_pdf(path)
        elif resume.name.endswith('.docx'):
            text = extract_text_from_docx(path)
        else:
            return HttpResponse("Unsupported file format.")

        # Extract links
        github_url = extract_link(r'https?://github\.com/[A-Za-z0-9_-]+', text)
        leetcode_url = extract_link(r'https?://leetcode\.com/[A-Za-z0-9_-]+', text)
        portfolio_url = extract_link(r'https?://[a-zA-Z0-9.-]+\.(me|tech|dev|xyz|site|vercel\.app|github\.io)', text)
        linkedin_url = extract_link(r'https?://(www\.)?linkedin\.com/in/[A-Za-z0-9_-]+', text)

        # Check if already calculated for session
        if 'ats_scores' not in request.session:
            scores = {
                "GitHub": score_github(github_url),
                "LeetCode": score_leetcode(leetcode_url),
                "Portfolio": score_portfolio(portfolio_url),
                "LinkedIn": score_linkedin(linkedin_url, text),
                "Resume": score_resume_structure(text),
                "Certifications": score_certifications(text)
            }
            total = sum(scores.values())
            grade = grade_from_score(total)

            request.session['ats_scores'] = scores
            request.session['ats_total'] = total
            request.session['ats_grade'] = grade

        else:
            scores = request.session['ats_scores']
            total = request.session['ats_total']
            grade = request.session['ats_grade']

        # Render results
        html = f"<h2>ApplyWizz ATS Score: {total}/100</h2>"
        html += f"<h3>{grade}</h3><ul>"
        for k, v in scores.items():
            html += f"<li>{k}: {v} pts</li>"
        html += "</ul>"

        return HttpResponse(html)

    return render(request, 'upload.html')
