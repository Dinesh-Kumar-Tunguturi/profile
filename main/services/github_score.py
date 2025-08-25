import requests
from datetime import datetime, timedelta
from dateutil.parser import parse as parse_dt

def score_github(username: str, token: str | None = None, domain_keywords: list[str] | None = None) -> dict:
    """
    GitHub Scoring (25 pts):
     - Link present: 3
     - Pinned repositories (3+): 5    [GraphQL; requires token to access pinned reliably]
     - Recent activity (PushEvent in last 90d): 5
     - README quality: 6              [presence across recent repos]
     - Domain-relevant projects: 6    [desc/topics keyword match]
    """
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "resume-scorer"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    base = "https://api.github.com"

    # 1) Link present
    pts_link = 3 if username else 0

    # 2) Pinned repos (GraphQL)
    pts_pinned = 0
    pinned_names = []
    if token and username:
        graphql = "https://api.github.com/graphql"
        query = """
        query($login:String!) {
          user(login:$login){
            pinnedItems(first: 6, types: REPOSITORY) {
              nodes { ... on Repository { nameWithOwner, name, description } }
            }
          }
        }"""
        try:
            r = requests.post(graphql, headers=headers, json={"query": query, "variables": {"login": username}}, timeout=20)
            if r.ok:
                nodes = r.json().get("data", {}).get("user", {}).get("pinnedItems", {}).get("nodes", [])
                pinned_names = [n["name"] for n in nodes if "name" in n]
                if len(pinned_names) >= 3:
                    pts_pinned = 5
                elif len(pinned_names) > 0:
                    pts_pinned = 3
        except Exception:
            pass

    # 3) Recent activity (PushEvent in last 90 days)
    pts_recent = 0
    if username:
        try:
            events = requests.get(f"{base}/users/{username}/events/public", headers=headers, timeout=20)
            recent_push = 0
            if events.ok:
                cutoff = datetime.utcnow() - timedelta(days=90)
                for e in events.json():
                    if e.get("type") == "PushEvent":
                        ts = parse_dt(e.get("created_at")).replace(tzinfo=None)
                        if ts >= cutoff:
                            recent_push += 1
                pts_recent = 5 if recent_push >= 5 else 3 if recent_push >= 1 else 0
        except Exception:
            pass

    # 4) README quality
    pts_readme = 0
    readme_hits = 0
    repos_checked = 0
    repos_resp = None
    if username:
        try:
            repos_resp = requests.get(f"{base}/users/{username}/repos?per_page=100&sort=updated",
                                      headers=headers, timeout=20)
            if repos_resp.ok:
                repo_list = repos_resp.json()[:10]
                for repo in repo_list:
                    owner = repo["owner"]["login"]; name = repo["name"]
                    readme = requests.get(f"{base}/repos/{owner}/{name}/readme", headers=headers, timeout=15)
                    repos_checked += 1
                    if readme.ok:
                        readme_hits += 1
                if readme_hits >= 5:
                    pts_readme = 6
                elif readme_hits >= 2:
                    pts_readme = 4
                elif readme_hits >= 1:
                    pts_readme = 2
        except Exception:
            pass

    # 5) Domain-relevant projects
    pts_domain = 0
    domain_keywords = [k.lower() for k in (domain_keywords or [])]
    domain_hits = 0
    if username:
        try:
            if repos_resp is None or not repos_resp.ok:
                repos_resp = requests.get(f"{base}/users/{username}/repos?per_page=100&sort=updated",
                                          headers=headers, timeout=20)
            if repos_resp.ok:
                for repo in repos_resp.json():
                    desc = (repo.get("description") or "").lower()
                    topics_resp = requests.get(
                        f"{base}/repos/{repo['owner']['login']}/{repo['name']}/topics",
                        headers={**headers, "Accept": "application/vnd.github.mercy-preview+json"},
                        timeout=15
                    )
                    topics = []
                    if topics_resp.ok:
                        topics = [t.lower() for t in topics_resp.json().get("names", [])]
                    text = desc + " " + " ".join(topics)
                    if any(k in text for k in domain_keywords):
                        domain_hits += 1
                pts_domain = 6 if domain_hits >= 3 else 4 if domain_hits == 2 else 2 if domain_hits == 1 else 0
        except Exception:
            pass

    total = pts_link + pts_pinned + pts_recent + pts_readme + pts_domain
    return {
        "breakdown": {
            "link_present": pts_link,
            "pinned_repos": pts_pinned,
            "recent_activity": pts_recent,
            "readme_quality": pts_readme,
            "domain_projects": pts_domain,
        },
        "subtotal": {"earned": total, "max": 25},
        "raw": {"pinned": pinned_names, "readme_hits": readme_hits, "domain_hits": domain_hits}
    }
