import os
import json
import requests
import pandas as pd
from datetime import datetime, timedelta

# GitHub API setup
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_NAME = os.getenv("REPO_NAME")  # e.g., "owner/repo"
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
API_BASE = "https://api.github.com"

# Datadog API setup
DATADOG_API_KEY = os.getenv("DATADOG_API_KEY")
DATADOG_API_URL = "https://api.datadoghq.com/api/v1/series"

# Helper function to query GitHub API
def github_api_request(endpoint):
    url = f"{API_BASE}/{endpoint}"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 403:  # Handle API rate limits or permission issues
        print(f"API error for {endpoint}: {response.text}")
        return []
    response.raise_for_status()
    return response.json()

# Step 1: Collect Metadata (including all GHAS components)
def collect_metadata():
    owner, repo = REPO_NAME.split("/")

    # Commit frequency (commits in the last 30 days)
    since = (datetime.utcnow() - timedelta(days=30)).isoformat() + "Z"
    commits = github_api_request(f"repos/{REPO_NAME}/commits?since={since}")
    commits_per_week = len(commits) / 4.0  # Rough estimate

    # Number of contributors
    contributors = github_api_request(f"repos/{REPO_NAME}/contributors")
    contributor_count = len(contributors)

    # Dependency age (simplified count of outdated dependencies)
    deps = github_api_request(f"repos/{REPO_NAME}/dependency-graph/snapshots")
    old_deps = 0
    if deps and "manifests" in deps[0]:
        for manifest in deps[0]["manifests"]:
            for dep in manifest.get("dependencies", []):
                old_deps += 1 if "version" in dep and "outdated" in dep.get("status", "") else 0

    # GHAS Findings
    # 1. Dependabot alerts
    dependabot_alerts = github_api_request(f"repos/{REPO_NAME}/dependabot/alerts?state=open")
    dependabot_count = len(dependabot_alerts)
    dependabot_severity = sum(
        {"critical": 10, "high": 7, "medium": 4, "low": 1}.get(alert.get("security_vulnerability", {}).get("severity", "low").lower(), 1)
        for alert in dependabot_alerts
    )

    # 2. Secret scanning alerts
    secret_alerts = github_api_request(f"repos/{REPO_NAME}/secret-scanning/alerts?state=open")
    secret_count = len(secret_alerts)
    secret_severity = secret_count * 5  # Assign medium severity (adjustable)

    # 3. Code scanning alerts
    code_alerts = github_api_request(f"repos/{REPO_NAME}/code-scanning/alerts?state=open")
    code_count = len(code_alerts)
    code_severity = sum(
        {"critical": 10, "high": 7, "medium": 4, "low": 1}.get(alert.get("rule", {}).get("severity", "low").lower(), 1)
        for alert in code_alerts
    )

    # Total GHAS severity score
    total_ghas_severity = dependabot_severity + secret_severity + code_severity

    return {
        "commits_per_week": commits_per_week,
        "contributors": contributor_count,
        "old_deps": old_deps,
        "dependabot_count": dependabot_count,
        "secret_count": secret_count,
        "code_count": code_count,
        "total_ghas_severity": total_ghas_severity
    }

# Step 2: Parse Scorecard Results
# def get_scorecard_score():
#     with open("scorecard-results.json", "r") as f:
#         scorecard_data = json.load(f)
#     checks = scorecard_data.get("checks", [])
#     avg_score = sum(check["score"] for check in checks if check["score"] >= 0) / len(checks) if checks else 0
#     return avg_score

def get_scorecard_score():
    try:
        with open("scorecard-results.json", "r") as f:
            scorecard_data = json.load(f)
        checks = scorecard_data.get("checks", [])
        avg_score = sum(check["score"] for check in checks if check["score"] >= 0) / len(checks) if checks else 0
        return avg_score
    except FileNotFoundError:
        print("Error: scorecard-results.json not found!")
        return 0  # Default to 0 if file is missing
    except json.JSONDecodeError:
        print("Error: Invalid JSON in scorecard-results.json!")
        return 0

# Step 3: Calculate Risk Score
def calculate_risk_score(metadata, scorecard_score):
    weights = {
        "scorecard": 0.3,
        "ghas": 0.4,  # Now includes Dependabot, secrets, and code scanning
        "commits": 0.1,
        "contributors": 0.1,
        "deps": 0.1
    }
    risk_score = (
        weights["scorecard"] * (10 - scorecard_score) +  # Invert Scorecard (higher = better)
        weights["ghas"] * metadata["total_ghas_severity"] +  # Use severity instead of raw count
        weights["commits"] * (1 if metadata["commits_per_week"] < 1 else 0) +
        weights["contributors"] * (1 if metadata["contributors"] < 3 else 0) +
        weights["deps"] * metadata["old_deps"]
    )
    return min(risk_score, 100)  # Cap at 100

# Step 4: Send Metrics to Datadog
def send_to_datadog(risk_score, metadata, scorecard_score):
    timestamp = int(datetime.utcnow().timestamp())
    series = [
        {
            "metric": "governance.risk_score",
            "points": [[timestamp, risk_score]],
            "type": "gauge",
            "tags": [f"repo:{REPO_NAME}"]
        },
        {
            "metric": "governance.scorecard_score",
            "points": [[timestamp, scorecard_score]],
            "type": "gauge",
            "tags": [f"repo:{REPO_NAME}"]
        },
        {
            "metric": "governance.dependabot_alerts",
            "points": [[timestamp, metadata["dependabot_count"]]],
            "type": "gauge",
            "tags": [f"repo:{REPO_NAME}"]
        },
        {
            "metric": "governance.secret_alerts",
            "points": [[timestamp, metadata["secret_count"]]],
            "type": "gauge",
            "tags": [f"repo:{REPO_NAME}"]
        },
        {
            "metric": "governance.code_alerts",
            "points": [[timestamp, metadata["code_count"]]],
            "type": "gauge",
            "tags": [f"repo:{REPO_NAME}"]
        },
        {
            "metric": "governance.total_ghas_severity",
            "points": [[timestamp, metadata["total_ghas_severity"]]],
            "type": "gauge",
            "tags": [f"repo:{REPO_NAME}"]
        },
        {
            "metric": "governance.commits_per_week",
            "points": [[timestamp, metadata["commits_per_week"]]],
            "type": "gauge",
            "tags": [f"repo:{REPO_NAME}"]
        },
        {
            "metric": "governance.contributors",
            "points": [[timestamp, metadata["contributors"]]],
            "type": "gauge",
            "tags": [f"repo:{REPO_NAME}"]
        },
        {
            "metric": "governance.old_deps",
            "points": [[timestamp, metadata["old_deps"]]],
            "type": "gauge",
            "tags": [f"repo:{REPO_NAME}"]
        }
    ]
    payload = {"series": series}
    response = requests.post(
        DATADOG_API_URL,
        headers={"Content-Type": "application/json", "DD-API-KEY": DATADOG_API_KEY},
        json=payload
    )
    response.raise_for_status()
    print(f"Sent metrics to Datadog: {response.status_code}")

# Main execution
if __name__ == "__main__":
    # Collect metadata
    metadata = collect_metadata()
    print(f"Metadata: {metadata}")

    # Get Scorecard score
    scorecard_score = get_scorecard_score()
    print(f"Scorecard Average Score: {scorecard_score}")

    # Calculate risk score
    risk_score = calculate_risk_score(metadata, scorecard_score)
    print(f"Risk Score: {risk_score}")

    # Send to Datadog
    send_to_datadog(risk_score, metadata, scorecard_score)
