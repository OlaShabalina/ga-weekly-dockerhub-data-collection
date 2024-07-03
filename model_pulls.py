import requests
import csv
import re
import os
from dotenv import load_dotenv
from datetime import datetime


# load docker creds from env
load_dotenv()
username = os.getenv('USERNAME')
password = os.getenv('PASSWORD')

org_name = "ersiliaos"


def get_dockerhub_token(username, password):
    url = "https://hub.docker.com/v2/users/login/"
    payload = {"username": username, "password": password}
    response = requests.post(url, json=payload)
    response.raise_for_status()
    return response.json()["token"]


def get_organization_repositories(org_name, token):
    url = f"https://hub.docker.com/v2/repositories/{org_name}/"
    headers = {"Authorization": f"JWT {token}"}
    repositories = []

    while url:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        repositories.extend(data["results"])
        url = data["next"]  # Next page URL

    return repositories


def extract_overview(full_description):
    if not full_description:
        return ""
    match = re.search(r'# ([^\n]+)\n', full_description)
    if match:
        print(match.group(1).strip())
        return match.group(1).strip()
    return ""


def get_repository_details(repo_name, org_name, token):
    url = f"https://hub.docker.com/v2/repositories/{org_name}/{repo_name}/"
    headers = {"Authorization": f"JWT {token}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()
    pull_count = data["pull_count"]
    full_description = data.get("full_description", "")
    overview = extract_overview(full_description)
    return pull_count, overview


token = get_dockerhub_token(username, password)
repositories = get_organization_repositories(org_name, token)

repo_data = []

for repo in repositories:
    repo_name = repo["name"]
    pull_count, overview = get_repository_details(repo_name, org_name, token)
    repo_data.append([repo_name, pull_count, overview])

# Get today's date
today_date = datetime.now().strftime('%Y-%m-%d')

# Save to CSV
csv_file = f"dockerhub-repositories-{today_date}.csv"
with open(csv_file, mode='w', newline='', encoding='utf-8') as file:
    writer = csv.writer(file)
    writer.writerow(["Repository Name", "Pull Count", "Overview"])
    writer.writerows(repo_data)

print(f"Data saved to {csv_file}")
