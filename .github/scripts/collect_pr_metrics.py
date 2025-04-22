#!/usr/bin/env python3
# .github/scripts/collect_pr_metrics.py

import os
import datetime
import pandas as pd
from github import Github
from collections import defaultdict

# Initialize GitHub client
github_token = os.environ.get("GITHUB_TOKEN")
repo_name = os.environ.get("REPO_NAME")
g = Github(github_token)
repo = g.get_repo(repo_name)

# Get today's date for filename
today = datetime.datetime.now().strftime("%Y-%m-%d")

# Data structures to store metrics
pr_data = []
open_prs_count = 0
total_cycle_time = datetime.timedelta(0)
merged_prs_count = 0
total_time_to_review = datetime.timedelta(0)
prs_with_reviews_count = 0

# Get pull requests (limited to last 1000 for API efficiency)
pull_requests = repo.get_pulls(state='all', sort='created', direction='desc')[:1000]

for pr in pull_requests:
    # Basic PR info
    pr_info = {
        'number': pr.number,
        'title': pr.title,
        'created_at': pr.created_at,
        'updated_at': pr.updated_at,
        'state': pr.state,
        'user': pr.user.login,
    }
    
    # Count open PRs
    if pr.state == 'open':
        open_prs_count += 1
    
    # Calculate cycle time for merged PRs
    if pr.merged:
        pr_info['merged_at'] = pr.merged_at
        cycle_time = pr.merged_at - pr.created_at
        pr_info['cycle_time_hours'] = cycle_time.total_seconds() / 3600
        total_cycle_time += cycle_time
        merged_prs_count += 1
    else:
        pr_info['merged_at'] = None
        pr_info['cycle_time_hours'] = None
    
    # Calculate time to first review
    reviews = list(pr.get_reviews())
    if reviews:
        first_review = min(reviews, key=lambda r: r.submitted_at)
        time_to_review = first_review.submitted_at - pr.created_at
        pr_info['first_review_at'] = first_review.submitted_at
        pr_info['time_to_review_hours'] = time_to_review.total_seconds() / 3600
        pr_info['first_reviewer'] = first_review.user.login
        
        total_time_to_review += time_to_review
        prs_with_reviews_count += 1
    else:
        pr_info['first_review_at'] = None
        pr_info['time_to_review_hours'] = None
        pr_info['first_reviewer'] = None
    
    pr_data.append(pr_info)

# Calculate averages
avg_cycle_time_hours = (total_cycle_time.total_seconds() / 3600) / merged_prs_count if merged_prs_count > 0 else 0
avg_time_to_review_hours = (total_time_to_review.total_seconds() / 3600) / prs_with_reviews_count if prs_with_reviews_count > 0 else 0

# Create detailed PR dataframe and save to CSV
pr_df = pd.DataFrame(pr_data)
pr_df.to_csv(f'pr-metrics-detailed-{today}.csv', index=False)

# Create summary metrics dataframe
summary_data = {
    'date': [today],
    'open_prs_count': [open_prs_count],
    'merged_prs_count': [merged_prs_count],
    'avg_cycle_time_hours': [avg_cycle_time_hours],
    'avg_time_to_review_hours': [avg_time_to_review_hours],
    'prs_with_reviews_count': [prs_with_reviews_count]
}
summary_df = pd.DataFrame(summary_data)

# Append to historical summary if it exists
summary_file = 'pr-metrics-summary.csv'
if os.path.exists(summary_file):
    historical_df = pd.read_csv(summary_file)
    updated_df = pd.concat([historical_df, summary_df])
    updated_df.to_csv(summary_file, index=False)
else:
    summary_df.to_csv(summary_file, index=False)

# Create a daily summary file as well
summary_df.to_csv(f'pr-metrics-summary-{today}.csv', index=False)

print(f"Open PRs: {open_prs_count}")
print(f"Average PR Cycle Time: {avg_cycle_time_hours:.2f} hours")
print(f"Average Time to First Review: {avg_time_to_review_hours:.2f} hours")
print(f"Metrics saved to CSV files")
