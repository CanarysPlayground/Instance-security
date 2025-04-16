#!/usr/bin/env python3
import requests
import os
import time
import shutil
import re
import secrets
import string
import json
from flask import Flask, request, render_template, jsonify

# --- Config ---
# IMPORTANT: Set these values directly for now, later move to environment variables
GITHUB_TOKEN = ""  # Replace with your new token
ENTERPRISE_ID = "MDEwOkVudGVycHJpc2UzMTEy"  # Your enterprise ID
SOURCE_ORG = "Instance-test-org"  # Your template/golden source org
REPOS_TO_CLONE = ["Java-Repo01","ghas-enablement"]  # Add more repos as needed

# --- Headers ---
headers_graphql = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
}

headers_rest = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

# --- Helper Functions ---
def is_valid_email(email):
    """Check if email is valid"""
    email_pattern = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    return bool(email_pattern.match(email))

def get_github_username_from_email(email):
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

# def generate_unique_org_name(prefix="GH-Org"):
#     """Generate a unique organization name"""
#     # Get timestamp and random string
#     timestamp = int(time.time())
#     random_str = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4))
#     return f"{prefix}-{timestamp}-{random_str}"

def generate_unique_org_name(email, prefix="GH-Canarys"):
    """Generate a unique organization name using email's first part"""
    # Extract firstname from email before the @ symbol
    firstname = email.split("@")[0].split(".")[0].capitalize()
    
    # Get timestamp or short random string
    random_str = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4))
    
    return f"{prefix}-{firstname}-{random_str}"


def create_organization(email, org_login=None):
    """Create a new GitHub organization and make the user an owner"""
    if not is_valid_email(email):
        return {"success": False, "message": "Invalid email address"}
    
    # Generate unique org name if not provided
    if not org_login:
        org_login = generate_unique_org_name(email)
    
    org_name = org_login.replace("-", " ")
    
    # Try to find GitHub username from email
    github_username = get_github_username_from_email(email)
    admin_logins = [github_username] if github_username else []
    
    # Create the organization using GraphQL API
    create_org_mutation = f"""
    mutation {{
      createEnterpriseOrganization(
        input: {{
          enterpriseId: "{ENTERPRISE_ID}"
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
    
    # Check for errors
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
    
    # If no GitHub username was found, invite user by email
    if "data" in result and result["data"]["createEnterpriseOrganization"]["organization"]:
        org_id = result["data"]["createEnterpriseOrganization"]["organization"]["id"]
        invite_user_rest(email, org_login)  # NEW REST-based fallback


    
    # Return success
    return {
        "success": True, 
        "message": f"Organization '{org_login}' created successfully!",
        "org_login": org_login
    }

def invite_user_rest(email, org_login):
    url = f"https://api.github.com/orgs/{org_login}/invitations"
    payload = {
        "email": email,
        "role": "admin"  # This makes them OWNER
    }
    response = requests.post(url, headers=headers_rest, json=payload)
    print(f"[+] REST Invite Status for {email}: {response.status_code}")
    print(response.json())
    return response.json()


def clone_repositories(org_login):
    """Clone repositories from source organization to target organization"""
    results = []
    
    for repo in REPOS_TO_CLONE:
        # Create empty private repo in new org
        create_repo_url = f"https://api.github.com/orgs/{org_login}/repos"
        payload = {
            "name": repo,
            "private": True,
            "description": f"Cloned from {SOURCE_ORG}/{repo}",
            "auto_init": False
        }
        
        r = requests.post(create_repo_url, headers=headers_rest, json=payload)
        
        if r.status_code == 422 and "name already exists" in r.text:
            results.append(f"Repository '{repo}' already exists in {org_login}. Skipping creation.")
            continue
        elif r.status_code != 201:
            results.append(f"Failed to create repository '{repo}' in {org_login}: {r.status_code} - {r.text}")
            continue
        
        # Clone the source repo (bare)
        repo_dir = f"{repo}.git"
        clone_url = f"https://x-access-token:{GITHUB_TOKEN}@github.com/{SOURCE_ORG}/{repo}.git"
        
        try:
            os.system(f"git clone --bare {clone_url}")
        
            # Push to new org
            os.chdir(repo_dir)
            push_url = f"https://x-access-token:{GITHUB_TOKEN}@github.com/{org_login}/{repo}.git"
            os.system(f"git push --mirror {push_url}")
            os.chdir("..")
            
            # Cleanup with permission fix (for Windows)
            try:
                def force_remove_readonly(func, path, _):
                    os.chmod(path, os.stat.S_IWRITE)
                    func(path)
                
                shutil.rmtree(repo_dir, onerror=force_remove_readonly)
            except Exception as e:
                results.append(f"Cleanup failed for {repo_dir}: {e}")
            
            results.append(f"Successfully cloned repository '{repo}' to {org_login}")
        except Exception as e:
            results.append(f"Error cloning repository '{repo}': {e}")
    
    return results

# --- Flask App ---
app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/create_workshop', methods=['POST'])
def create_workshop():
    data = request.get_json()
    emails = data.get('emails', [])
    
    if not emails:
        return jsonify({"success": False, "message": "No email addresses provided"})
    
    results = []
    for email in emails:
        # Create org for each email
        create_result = create_organization(email)
        
        if create_result["success"]:
            # Clone repos to the new org
            org_login = create_result["org_login"]
            clone_results = clone_repositories(org_login)
            
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
    
    return jsonify({"success": True, "results": results})

# Create templates directory and index.html
def setup_templates():
    os.makedirs('templates', exist_ok=True)
    
    html_content = """<!DOCTYPE html>
<html>
<head>
    <title>GitHub Workshop Orchestrator</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }
        h1 {
            color: #24292e;
        }
        .form-group {
            margin-bottom: 15px;
        }
        label {
            display: block;
            margin-bottom: 5px;
            font-weight: bold;
        }
        textarea {
            width: 100%;
            height: 150px;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 3px;
        }
        button {
            background-color: #2ea44f;
            color: white;
            border: none;
            padding: 10px 16px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
        }
        button:hover {
            background-color: #2c974b;
        }
        #result {
            margin-top: 20px;
            padding: 15px;
            border-radius: 3px;
            display: none;
        }
        .success {
            background-color: #f0fff4;
            border: 1px solid #dcffe4;
        }
        .error {
            background-color: #fff5f5;
            border: 1px solid #fed7d7;
        }
        .loading {
            display: none;
            text-align: center;
            margin: 20px 0;
        }
        .repo-result {
            margin-left: 20px;
            font-size: 14px;
            color: #666;
        }
    </style>
</head>
<body>
    <h1>GitHub Workshop Orchestrator</h1>
    <p>Enter participant email addresses (one per line) to create a GitHub organization for each participant.</p>
    
    <div class="form-group">
        <label for="emails">Participant Email Addresses:</label>
        <textarea id="emails" placeholder="Enter email addresses, one per line"></textarea>
    </div>
    
    <button id="createBtn">Create Workshop Environments</button>
    
    <div class="loading" id="loading">
        <p>Creating organizations and repositories... This may take a few minutes.</p>
    </div>
    
    <div id="result"></div>
    
    <script>
        document.getElementById('createBtn').addEventListener('click', async function() {
            const emailsText = document.getElementById('emails').value.trim();
            if (!emailsText) {
                alert('Please enter at least one email address');
                return;
            }
            
            const emails = emailsText.split('\\n').map(email => email.trim()).filter(email => email);
            
            document.getElementById('loading').style.display = 'block';
            document.getElementById('result').style.display = 'none';
            
            try {
                const response = await fetch('/create_workshop', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ emails })
                });
                
                const data = await response.json();
                
                document.getElementById('loading').style.display = 'none';
                const resultDiv = document.getElementById('result');
                resultDiv.style.display = 'block';
                
                if (data.success) {
                    resultDiv.className = 'success';
                    let html = '<h3>Results:</h3>';
                    
                    data.results.forEach(result => {
                        if (result.success) {
                            html += `<p>&#x2705; <strong>${result.email}</strong>: ${result.message}</p>`;
                            
                            if (result.repo_results && result.repo_results.length > 0) {
                                html += '<div class="repo-result">';
                                result.repo_results.forEach(repoResult => {
                                    html += `<p>${repoResult}</p>`;
                                });
                                html += '</div>';
                            }
                        } else {
                            html += `<p>&#x274C; <strong>${result.email}</strong>: ${result.message}</p>`;
                        }
                    });
                    
                    resultDiv.innerHTML = html;
                } else {
                    resultDiv.className = 'error';
                    resultDiv.innerHTML = `<p>Error: ${data.message}</p>`;
                }
            } catch (error) {
                document.getElementById('loading').style.display = 'none';
                const resultDiv = document.getElementById('result');
                resultDiv.style.display = 'block';
                resultDiv.className = 'error';
                resultDiv.innerHTML = `<p>Error: ${error.message}</p>`;
            }
        });
    </script>
</body>
</html>"""
    
    with open('templates/index.html', 'w', encoding='utf-8') as f:
        f.write(html_content)

if __name__ == "__main__":
    # Check if token is set
    if GITHUB_TOKEN == "your_new_token_here":
        print("ERROR: GitHub token not set. Please update the GITHUB_TOKEN variable in the script.")
        exit(1)
    
    # Create templates and HTML file
    setup_templates()
    
    # Start the Flask app
    print("Starting GitHub Workshop Orchestrator on http://127.0.0.1:5050")
    app.run(debug=True, port=5050)
