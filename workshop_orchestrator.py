#!/usr/bin/env python3
import stat
import requests
import os
import time
import shutil
import re
import secrets
import string
import json
import argparse

# --- Helper Functions ---
def is_valid_email(email):
    """Check if email is valid"""
    email_pattern = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    return bool(email_pattern.match(email))

def get_github_username_from_email(email, headers_graphql):
    """Try to find GitHub username associated with email"""
    query = f"""
    query {{
      search(query: "{email} in:email", type: USER, first: 1) {{
        userCount
        edges {{
          node {{
            ... on User {{
              login
            }}
          }}
        }}
      }}
    }}
    """
    
    response = requests.post("https://api.github.com/graphql", 
                            headers=headers_graphql, 
                            json={"query": query})
    
    result = response.json()
    if result.get('data', {}).get('search', {}).get('userCount', 0) > 0:
        return result['data']['search']['edges'][0]['node']['login']
    return None

def generate_unique_org_name(email, prefix="GH-Canarys"):
    """Generate a unique organization name using email's first part"""
    firstname = email.split("@")[0].split(".")[0].capitalize()
    random_str = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4))
    return f"{prefix}-{firstname}-{random_str}"

def create_organization(email, enterprise_id, org_login=None, github_token=None):
    """Create a new GitHub organization and make the user an owner"""
    headers_graphql = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json"
    }
    
    headers_rest = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    if not is_valid_email(email):
        return {"success": False, "message": "Invalid email address"}
    
    if not org_login:
        org_login = generate_unique_org_name(email)
    
    org_name = org_login.replace("-", " ")
    
    github_username = get_github_username_from_email(email, headers_graphql)
    admin_logins = [github_username] if github_username else []
    
    create_org_mutation = f"""
    mutation {{
      createEnterpriseOrganization(
        input: {{
          enterpriseId: "{enterprise_id}"
          login: "{org_login}"
          profileName: "{org_name}"
          billingEmail: "{email}"
          adminLogins: {json.dumps(admin_logins)}
        }}
      ) {{
        organization {{
          id
          login
          name
        }}
      }}
    }}
    """
    
    response = requests.post(
        "https://api.github.com/graphql", 
        headers=headers_graphql, 
        json={"query": create_org_mutation}
    )
    
    result = response.json()
    
    if "errors" in result:
        for error in result["errors"]:
            message = error.get("message", "").lower()
            if (
                "already exists" in message or
                "login already exists" in message or
                "organization name is not available" in message
            ):
                return {"success": False, "message": f"Organization '{org_login}' already exists. Please try a different name."}
            else:
                return {"success": False, "message": f"Organization creation failed: {error.get('message')}"}
    
    if "data" in result and result["data"]["createEnterpriseOrganization"]["organization"]:
        org_id = result["data"]["createEnterpriseOrganization"]["organization"]["id"]
        invite_user_rest(email, org_login, headers_rest)
    
    return {
        "success": True, 
        "message": f"Organization '{org_login}' created successfully!",
        "org_login": org_login
    }

def invite_user_rest(email, org_login, headers_rest):
    """Invite user to organization via REST API"""
    url = f"https://api.github.com/orgs/{org_login}/invitations"
    payload = {
        "email": email,
        "role": "admin"
    }
    response = requests.post(url, headers=headers_rest, json=payload)
    print(f"[+] REST Invite Status for {email}: {response.status_code}")
    print(response.json())
    return response.json()

def clone_repositories(org_login, repos_to_clone, source_org, github_token):
    """Clone repositories from source organization to target organization"""
    headers_rest = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    results = []
    
    for repo in repos_to_clone:
        create_repo_url = f"https://api.github.com/orgs/{org_login}/repos"
        payload = {
            "name": repo,
            "private": True,
            "description": f"Cloned from {source_org}/{repo}",
            "auto_init": False
        }
        
        r = requests.post(create_repo_url, headers=headers_rest, json=payload)
        
        if r.status_code == 422 and "name already exists" in r.text:
            results.append(f"Repository '{repo}' already exists in {org_login}. Skipping creation.")
            continue
        elif r.status_code != 201:
            results.append(f"Failed to create repository '{repo}' in {org_login}: {r.status_code} - {r.text}")
            continue
        
        repo_dir = f"{repo}.git"
        clone_url = f"https://x-access-token:{github_token}@github.com/{source_org}/{repo}.git"
        
        try:
            os.system(f"git clone --bare {clone_url}")
            os.chdir(repo_dir)
            push_url = f"https://x-access-token:{github_token}@github.com/{org_login}/{repo}.git"
            os.system(f"git push --mirror {push_url}")
            os.chdir("..")
            
            try:
                def force_remove_readonly(func, path, _):
                    os.chmod(path, stat.S_IWRITE)
                    func(path)
                
                shutil.rmtree(repo_dir, onerror=force_remove_readonly)
            except Exception as e:
                results.append(f"Cleanup failed for {repo_dir}: {e}")
            
            results.append(f"Successfully cloned repository '{repo}' to {org_login}")
        except Exception as e:
            results.append(f"Error cloning repository '{repo}': {e}")
    
    return results

def main():
    parser = argparse.ArgumentParser(description="GitHub Workshop Orchestrator")
    parser.add_argument("--emails", required=True, help="Comma-separated list of participant email addresses")
    parser.add_argument("--repos", required=True, help="Comma-separated list of repositories to clone")
    parser.add_argument("--token", required=True, help="GitHub Personal Access Token")
    parser.add_argument("--enterprise-id", required=True, help="Enterprise ID")
    parser.add_argument("--source-org", default="Instance-test-org01", help="Source organization for template repos")
    
    args = parser.parse_args()
    
    emails = [email.strip() for email in args.emails.split(",") if email.strip()]
    repos_to_clone = [repo.strip() for repo in args.repos.split(",") if repo.strip()]
    
    if not emails:
        print("Error: No valid email addresses provided")
        exit(1)
    
    if not repos_to_clone:
        print("Error: No repositories specified")
        exit(1)
    
    results = []
    for email in emails:
        create_result = create_organization(
            email=email,
            enterprise_id=args.enterprise_id,
            github_token=args.token
        )
        
        if create_result["success"]:
            org_login = create_result["org_login"]
            clone_results = clone_repositories(
                org_login=org_login,
                repos_to_clone=repos_to_clone,
                source_org=args.source_org,
                github_token=args.token
            )
            
            results.append({
                "email": email,
                "organization": org_login,
                "success": True,
                "message": create_result["message"],
                "repo_results": clone_results
            })
        else:
            results.append({
                "email": email,
                "success": False,
                "message": create_result["message"]
            })
    
    print(json.dumps({"success": True, "results": results}, indent=2))

if __name__ == "__main__":
    main()
