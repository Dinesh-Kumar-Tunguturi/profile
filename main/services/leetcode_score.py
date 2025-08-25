import requests

def score_leetcode(username: str) -> dict:
    """
    LeetCode scoring (20 pts):
      - Link present: 2
      - 100+ questions solved: 5
      - Medium/Hard attempts: 4
      - Regular contest participation: 4
      - Topic variety: 5  (>=3 solved per topic counts)
    Uses public GraphQL endpoint.
    """
    pts_link = 2 if username else 0
    LC = "https://leetcode.com/graphql"
    headers = {"Content-Type": "application/json"}

    solved_total = 0
    solved_medium = 0
    solved_hard = 0
    contests_attended = 0
    topic_variety = 0

    if not username:
        return {
            "breakdown": {
                "link_present": pts_link,
                "questions_solved": 0,
                "medium_hard": 0,
                "contest_participation": 0,
                "topic_variety": 0,
            },
            "raw": {},
            "subtotal": {"earned": pts_link, "max": 20},
        }

    # Stats + tags
    q_stats = """
    query($username: String!) {
      matchedUser(username: $username) {
        submitStats { acSubmissionNum { difficulty, count } }
        tagProblemCounts { advanced { tagName, problemsSolved } }
      }
    }"""
    r1 = requests.post(LC, headers=headers, json={"query": q_stats, "variables": {"username": username}}, timeout=20)
    if r1.ok and r1.json().get("data", {}).get("matchedUser"):
        ac = r1.json()["data"]["matchedUser"]["submitStats"]["acSubmissionNum"]
        for row in ac:
            d = row["difficulty"].lower()
            if d == "all": solved_total = row["count"]
            elif d == "medium": solved_medium = row["count"]
            elif d == "hard": solved_hard = row["count"]

        tags = r1.json()["data"]["matchedUser"].get("tagProblemCounts", {}).get("advanced", [])
        topic_variety = sum(1 for t in tags if t.get("problemsSolved", 0) >= 3)

    # Contest history
    q_contest = """
    query($username: String!) {
      userContestRankingHistory(username: $username) { attended }
    }"""
    r2 = requests.post(LC, headers=headers, json={"query": q_contest, "variables": {"username": username}}, timeout=20)
    if r2.ok:
        history = r2.json().get("data", {}).get("userContestRankingHistory", []) or []
        contests_attended = sum(1 for h in history if h and h.get("attended"))

    # Points
    pts_100 = 5 if solved_total >= 200 else 4 if solved_total >= 150 else 3 if solved_total >= 100 else 1 if solved_total >= 50 else 0
    medium_hard = solved_medium + solved_hard
    pts_mh = 4 if medium_hard >= 120 else 3 if medium_hard >= 60 else 2 if medium_hard >= 20 else 0
    pts_contest = 4 if contests_attended >= 6 else 3 if contests_attended >= 3 else 1 if contests_attended >= 1 else 0
    pts_variety = 5 if topic_variety >= 8 else 4 if topic_variety >= 6 else 3 if topic_variety >= 4 else 1 if topic_variety >= 2 else 0

    total = pts_link + pts_100 + pts_mh + pts_contest + pts_variety
    return {
        "breakdown": {
            "link_present": pts_link,
            "questions_solved": pts_100,
            "medium_hard": pts_mh,
            "contest_participation": pts_contest,
            "topic_variety": pts_variety,
        },
        "raw": {
            "solved_total": solved_total,
            "solved_medium": solved_medium,
            "solved_hard": solved_hard,
            "contests_attended": contests_attended,
            "topic_variety_topics_3plus": topic_variety,
        },
        "subtotal": {"earned": total, "max": 20},
    }
