from typing import List

ROLE_ALIASES = {
    # technical
    "software engineer": "software engineer",
    "software developer": "software engineer",
    "web developer": "web developer",
    "frontend developer": "web developer",
    "full stack developer": "web developer",
    "backend developer": "software engineer",
    "data scientist": "data scientist",
    "data analyst": "data analyst",
    "devops engineer": "devops engineer",
    "sre": "devops engineer",
    "mobile app developer": "mobile app developer",
    "android developer": "mobile app developer",
    "ios developer": "mobile app developer",
    # non-technical
    "human resources": "human resources",
    "hr": "human resources",
    "marketing": "marketing",
    "sales": "sales",
    "finance": "finance",
    "customer service": "customer service",
}

ROLE_CERTS = {
    "software engineer": [
        "Meta Back-End Developer Professional Certificate – Coursera",
        "Meta Front-End Developer Professional Certificate – Coursera",
        "Google IT Automation with Python – Coursera",
        "AWS Certified Developer Associate (Exam Prep) – LinkedIn Learning",
        "Version Control with Git – Atlassian (Coursera)",
        "System Design Fundamentals – LinkedIn Learning",
    ],
    "web developer": [
        "Meta Front-End Developer Professional Certificate – Coursera",
        "IBM Full Stack Software Developer – Coursera",
        "Responsive Web Design – freeCodeCamp",
        "React Basics – Meta (Coursera)",
        "Advanced CSS – LinkedIn Learning",
        "JavaScript Algorithms and Data Structures – freeCodeCamp",
    ],
    "data scientist": [
        "IBM Data Science Professional Certificate – Coursera",
        "DeepLearning.AI TensorFlow Developer – Coursera",
        "Machine Learning Specialization – DeepLearning.AI (Coursera)",
        "Applied Data Science with Python – University of Michigan (Coursera)",
        "SQL for Data Science – UC Davis (Coursera)",
        "MLOps Fundamentals – LinkedIn Learning",
    ],
    "data analyst": [
        "Google Data Analytics Professional Certificate – Coursera",
        "IBM Data Analyst Professional Certificate – Coursera",
        "Excel Skills for Business – Macquarie (Coursera)",
        "Data Visualization with Tableau – UC Davis (Coursera)",
        "Power BI Data Analyst Associate (PL-300 Prep) – LinkedIn Learning",
        "SQL Basics for Data Science – Coursera Project Network",
    ],
    "devops engineer": [
        "DevOps on AWS – AWS Training",
        "Docker Essentials – IBM (Coursera)",
        "Kubernetes for Beginners – LinkedIn Learning",
        "Terraform on Azure – LinkedIn Learning",
        "CI/CD with Jenkins – LinkedIn Learning",
        "Site Reliability Engineering: Measure and Manage Reliability – Coursera",
    ],
    "mobile app developer": [
        "Android Kotlin Developer – Google (Android Developers)",
        "iOS App Development with Swift – University of Toronto (Coursera)",
        "Meta React Native Specialization – Coursera",
        "Firebase in a Weekend – Google (Udacity)",
        "Flutter Development – London App Brewery (Udemy)",
        "Mobile UI/UX Design – LinkedIn Learning",
    ],
    "human resources": [
        "HR Management and Analytics – Wharton (Coursera)",
        "Recruiting, Hiring, and Onboarding Employees – SHRM/LinkedIn Learning",
        "People Analytics – University of Pennsylvania (Coursera)",
        "Performance Management: Conducting Appraisals – LinkedIn Learning",
        "Compensation and Benefits – LinkedIn Learning",
        "Employment Law Fundamentals – LinkedIn Learning",
    ],
    "marketing": [
        "Google Digital Marketing & E-commerce – Coursera",
        "Meta Social Media Marketing – Coursera",
        "SEO Foundations – LinkedIn Learning",
        "Content Marketing Strategy – UC Davis (Coursera)",
        "Google Ads Search Certification – Google Skillshop",
        "Email Marketing Basics – HubSpot Academy",
    ],
    "sales": [
        "Sales Enablement – HubSpot Academy",
        "B2B Sales Strategy – LinkedIn Learning",
        "Negotiation Fundamentals – Yale (Coursera)",
        "CRM for Sales (Salesforce) – Trailhead",
        "Strategic Sales Management – IIM (MOOC variants)",
        "Solution Selling – LinkedIn Learning",
    ],
    "finance": [
        "Financial Markets – Yale (Coursera)",
        "Excel for Corporate Finance – LinkedIn Learning",
        "Financial Analysis and Modeling – Wharton (Coursera)",
        "Accounting Fundamentals – University of Virginia (Coursera)",
        "CFA Investment Foundations – CFA Institute",
        "Bloomberg Market Concepts (BMC) – Bloomberg",
    ],
    "customer service": [
        "Customer Service Fundamentals – LinkedIn Learning",
        "Service Desk Analyst – SDI (Foundations)",
        "Call Center Customer Service – LinkedIn Learning",
        "CX: Customer Experience Management – Coursera",
        "Communication Skills for Support – LinkedIn Learning",
        "Conflict Resolution for Customer Service – LinkedIn Learning",
    ],
}

def suggest_role_certifications(role_title_or_slug: str, limit: int = 6) -> List[str]:
    if not role_title_or_slug:
        return []
    key = role_title_or_slug.strip().lower()
    canonical = ROLE_ALIASES.get(key, key)
    certs = ROLE_CERTS.get(canonical, [])
    seen, out = set(), []
    for cert in certs:
        if cert not in seen:
            seen.add(cert)
            out.append(cert)
        if len(out) >= limit:
            break
    return out
