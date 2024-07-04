import requests
import re
import os
import json
from dotenv import load_dotenv
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Load credentials from environment variables
load_dotenv()
username = os.getenv('USERNAME')
password = os.getenv('PASSWORD')
google_sheets_creds = os.getenv('GOOGLE_SHEETS_CREDS')

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


# Fetch DockerHub data
token = get_dockerhub_token(username, password)
repositories = get_organization_repositories(org_name, token)

repo_data = {}
for repo in repositories:
    repo_name = repo["name"]
    pull_count, _ = get_repository_details(repo_name, org_name, token)
    repo_data[repo_name] = pull_count


# Authenticate with Google Sheets API
credentials = service_account.Credentials.from_service_account_info(
    json.loads(json.loads(google_sheets_creds)), scopes=["https://www.googleapis.com/auth/spreadsheets"]
)
service = build("sheets", "v4", credentials=credentials)
spreadsheet_id = "1NnB0GAdZa_ggG14NZ2am6zidudQMGh3FkTSjEOgOlV0"

# Read the existing sheet data, Raw tab
sheet = service.spreadsheets()
raw_tab_data = sheet.values().get(spreadsheetId=spreadsheet_id, range="Raw").execute()
values = raw_tab_data.get('values', [])

# Get today's date
today_date = datetime.now().strftime('%d/%m/%Y')

# Find the header row and existing columns
header_row = values[0]
latest_col_index = header_row.index("Latest")

# Find the first empty column to the right for today's date
empty_col_index = len(header_row)
for i, header in enumerate(header_row):
    if header == '':
        empty_col_index = i
        break

# Ensure the header row has today's date at the empty column
if len(header_row) <= empty_col_index:
    header_row.extend([''] * (empty_col_index - len(header_row) + 1))
header_row[empty_col_index] = today_date

# Update the sheet data with new pull counts
for row in values[1:]:
    code = row[0]
    if code in repo_data:
        # Update the Latest column
        if len(row) <= latest_col_index:
            row.extend([''] * (latest_col_index - len(row) + 1))
        row[latest_col_index] = repo_data[code]

        # Ensure the row is long enough
        if len(row) <= empty_col_index:
            row.extend([''] * (empty_col_index - len(row) + 1))
        row[empty_col_index] = repo_data[code]

# Prepare the updated values for the sheet
values[0] = header_row
data = {
    "values": values
}

# Update the Google Sheets document
request = sheet.values().update(
    spreadsheetId=spreadsheet_id,
    range="Raw",
    valueInputOption="RAW",
    body=data
)
response = request.execute()

print("Data saved to Raw tab")

# Update the Pre-processed tab with formulas
preprocessed_tab_data = sheet.values().get(spreadsheetId=spreadsheet_id, range="Pre-processed").execute()
preprocessed_values = preprocessed_tab_data.get('values', [])

# Ensure header row is updated with the new date
header_row = preprocessed_values[0]
if len(header_row) <= empty_col_index:
    header_row.extend([''] * (empty_col_index - len(header_row) + 1))
header_row[empty_col_index] = today_date
preprocessed_values[0] = header_row

# Update Pre-processed tab
for row_idx, row in enumerate(preprocessed_values[1:], start=2):
    # Update the next available column with the formula
    if len(row) <= empty_col_index:
        row.extend([''] * (empty_col_index - len(row) + 1))
    raw_col_letter = chr(65 + empty_col_index)
    raw_prev_col_letter = chr(65 + empty_col_index - 1)
    row[empty_col_index] = f"=Raw!{raw_col_letter}{row_idx} - Raw!{raw_prev_col_letter}{row_idx}"

    # Update the Latest column
    if len(row) <= latest_col_index:
        row.extend([''] * (latest_col_index - len(row) + 1))
    row[latest_col_index] = str(row[empty_col_index])

preprocessed_data = {"values": preprocessed_values}

preprocessed_request = sheet.values().update(
    spreadsheetId=spreadsheet_id,
    range="Pre-processed",
    valueInputOption="USER_ENTERED",
    body=preprocessed_data
)
preprocessed_response = preprocessed_request.execute()

print("Data saved to Pre-processed tab with formulas")
