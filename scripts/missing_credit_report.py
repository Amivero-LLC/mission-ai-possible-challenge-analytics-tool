import pandas as pd
import re
import os
import requests
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Get the project root directory (parent of scripts directory)
script_dir = Path(__file__).parent
project_root = script_dir.parent

# Load environment variables from .env file
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)

# === 1. Check if data refresh is needed ===
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
fetch_metadata_file = project_root / "data" / "fetch_metadata.json"

def check_and_refresh_if_needed():
    """Check if data is stale and refresh if necessary."""
    needs_refresh = False

    # Check if metadata file exists
    if not fetch_metadata_file.exists():
        print("⚠️  No fetch metadata found - data refresh required")
        needs_refresh = True
    else:
        try:
            with open(fetch_metadata_file, 'r') as f:
                metadata = json.load(f)
                last_fetched_str = metadata.get('last_fetched')

                if not last_fetched_str:
                    print("⚠️  Invalid fetch metadata - data refresh required")
                    needs_refresh = True
                else:
                    # Parse the ISO timestamp
                    last_fetched = datetime.fromisoformat(last_fetched_str.replace('Z', '+00:00'))
                    now = datetime.now(timezone.utc)
                    time_since_refresh = now - last_fetched

                    # Check if more than 1 hour old
                    if time_since_refresh > timedelta(hours=1):
                        print(f"⚠️  Data is {time_since_refresh.total_seconds() / 3600:.1f} hours old - refreshing...")
                        needs_refresh = True
                    else:
                        print(f"✓ Data is fresh ({time_since_refresh.total_seconds() / 60:.1f} minutes old)")
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            print(f"⚠️  Error reading fetch metadata: {e} - data refresh required")
            needs_refresh = True

    if needs_refresh:
        print("\n🔄 Refreshing data from Open WebUI...")
        try:
            response = requests.post(f"{API_BASE_URL}/refresh", timeout=60)
            response.raise_for_status()
            result = response.json()
            print(f"✓ Data refresh successful!")
            print(f"  Last fetched: {result.get('last_fetched', 'unknown')}")
            print(f"  Data source: {result.get('data_source', 'unknown')}")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 400:
                print(f"✗ Warning: Cannot refresh - Open WebUI credentials not configured")
                print(f"  Set OPEN_WEBUI_HOSTNAME and OPEN_WEBUI_API_KEY to enable auto-refresh")
            else:
                print(f"✗ Warning: Data refresh failed: {e}")
            print(f"  Continuing with existing cached data...")
        except requests.exceptions.RequestException as e:
            print(f"✗ Warning: Data refresh failed: {e}")
            print(f"  Continuing with existing cached data...")

print("=== CHECKING DATA FRESHNESS ===")
check_and_refresh_if_needed()

print("\n=== FETCHING DATA FROM API ===")

# Fetch user challenge data from API
try:
    response = requests.get(f"{API_BASE_URL}/users", timeout=30)
    response.raise_for_status()
    users_data = response.json()
    print(f"✓ Successfully fetched data from API")
except requests.exceptions.RequestException as e:
    print(f"✗ Failed to fetch data from API: {e}")
    print("Make sure the FastAPI server is running on port 8000")
    exit(1)

# Convert API response to DataFrame format matching the old Excel structure
completed_records = []
for user in users_data['users']:
    user_name = user['user_name']
    user_email = user.get('email', '')

    for challenge in user['challenges']:
        if challenge['status'] == 'Completed':
            # Convert timestamp to datetime if needed
            completed_time = challenge.get('completed_time')
            if completed_time and isinstance(completed_time, (int, float)):
                completed_time = datetime.fromtimestamp(completed_time).isoformat()

            completed_records.append({
                'Name': user_name,
                'Email': user_email,
                'Challenge Name': challenge['challenge_name'],
                'Status': challenge['status'],
                'Points Earned': challenge['points'],
                'DateTime Completed': completed_time
            })

completed_df = pd.DataFrame(completed_records)

# Load awarded credit data from CSV file
awarded_df = pd.read_csv(project_root / "data" / "SubmittedActivityList.csv")

print("\n=== INITIAL DATA ===")
print(f"Total completed records: {len(completed_df)}")
print(f"Total awarded records: {len(awarded_df)}")

# === 2. Filter to only relevant rows ===
# Only keep challenges that were actually completed
completed_df = completed_df[completed_df['Status'] == 'Completed'].copy()
print(f"\nFiltered to completed challenges: {len(completed_df)} rows")

# Only keep activities where credit was actually given (Review Completed)
awarded_df = awarded_df[awarded_df['ActivityStatus'] == 'Review Completed'].copy()
print(f"Filtered to awarded credit: {len(awarded_df)} rows")

# === 3. Normalize challenge names ===
def normalize_challenge_name(name):
    """Extract core challenge name from various formats"""
    if pd.isna(name):
        return None
    # Remove "Week X -", "Mission:", and normalize difficulty text
    name = re.sub(r'Week \d+ - ', '', str(name))
    name = re.sub(r'Mission: ', '', name)
    name = re.sub(r' \(Easy\)', '', name)
    name = re.sub(r' \(Medium\)', '', name)
    name = re.sub(r' \(Hard\)', '', name)
    name = re.sub(r' \(Easy Difficulty\)', '', name)
    name = re.sub(r' \(Medium Difficulty\)', '', name)
    name = re.sub(r' \(Hard Difficulty\)', '', name)
    name = re.sub(r' Challenge$', '', name)
    return name.strip()

completed_df['normalized_challenge'] = completed_df['Challenge Name'].apply(normalize_challenge_name)
awarded_df['normalized_challenge'] = awarded_df['MissionChallenge'].apply(normalize_challenge_name)

print("\n=== NORMALIZED CHALLENGE NAMES ===")
print("Completed challenges:", completed_df['normalized_challenge'].unique())
print("Awarded challenges:", awarded_df['normalized_challenge'].unique())

# === 4. Normalize email addresses ===
completed_df['email_lower'] = completed_df['Email'].str.lower().str.strip()
awarded_df['email_lower'] = awarded_df['Email'].str.lower().str.strip()

# === 5. Create composite keys for matching ===
completed_df['match_key'] = completed_df['email_lower'] + '|' + completed_df['normalized_challenge']
awarded_df['match_key'] = awarded_df['email_lower'] + '|' + awarded_df['normalized_challenge']

# === 6. Merge to find who received credit ===
merged = completed_df.merge(
    awarded_df[['match_key', 'PointsAwarded']],
    on='match_key',
    how='left',
    indicator=True
)

# === 7. Flag who received credit ===
merged['received_credit'] = merged['_merge'] == 'both'

# === 8. Create detailed report ===
report = merged[[
    'Name', 'Email', 'Challenge Name', 'normalized_challenge',
    'Points Earned', 'PointsAwarded', 'received_credit',
    'DateTime Completed'
]].copy()

# Sort by received_credit (False first) and then by name
report = report.sort_values(['received_credit', 'Name'])

# === 9. Summary statistics ===
print("\n" + "="*60)
print("SUMMARY REPORT")
print("="*60)
total = len(report)
received = report['received_credit'].sum()
not_received = total - received

print(f"\n✅ Total completed challenges: {total}")
print(f"🏆 Received credit: {received}")
print(f"❌ Did NOT receive credit: {not_received}")
print(f"📊 Credit rate: {received/total*100:.1f}%")

# === 10. Show users who didn't receive credit ===
no_credit = report[~report['received_credit']]
if len(no_credit) > 0:
    print(f"\n⚠️  {len(no_credit)} CHALLENGES COMPLETED BUT NOT CREDITED:")
    print("-" * 60)
    for idx, row in no_credit.iterrows():
        print(f"  • {row['Name']} ({row['Email']})")
        print(f"    Challenge: {row['Challenge Name']}")
        print(f"    Completed: {row['DateTime Completed']}")
        print()

# === 11. Show unique users who are missing credit ===
users_missing_credit = no_credit.groupby(['Name', 'Email']).size().reset_index(name='challenges_missing')
if len(users_missing_credit) > 0:
    print(f"\n👥 {len(users_missing_credit)} USERS WITH MISSING CREDIT:")
    print("-" * 60)
    for idx, row in users_missing_credit.iterrows():
        print(f"  • {row['Name']} ({row['Email']}) - {row['challenges_missing']} challenge(s)")

# === 12. Print detailed missing credit report to console ===
if len(no_credit) > 0:
    # Extract week number from challenge name
    def extract_week(challenge_name):
        match = re.search(r'Week (\d+)', str(challenge_name))
        return match.group(1) if match else 'N/A'

    no_credit_display = no_credit.copy()
    no_credit_display['Week'] = no_credit_display['Challenge Name'].apply(extract_week)

    print(f"\n{'='*90}")
    print("DETAILED MISSING CREDIT REPORT")
    print(f"{'='*90}")
    print(f"\n{'Name':<25} {'Email':<30} {'Week':<6} {'Challenge':<35} {'Points':<10}")
    print(f"{'-'*25} {'-'*30} {'-'*6} {'-'*35} {'-'*10}")
    for idx, row in no_credit_display.iterrows():
        print(f"{row['Name']:<25} {row['Email']:<30} {row['Week']:<6} {row['normalized_challenge']:<35} {row['Points Earned']:<10}")
    print(f"{'-'*90}")
    print(f"Total missing credit: {len(no_credit)} challenges")

# === 13. Save combined output ===
exports_dir = project_root / "exports"
exports_dir.mkdir(exist_ok=True)  # Create exports directory if it doesn't exist

report.to_excel(exports_dir / "combined_report.xlsx", index=False)
print(f"\n📄 Full report saved as {exports_dir / 'combined_report.xlsx'}")

# Also save just the no-credit list for follow-up
if len(no_credit) > 0:
    no_credit.to_excel(exports_dir / "missing_credit_report.xlsx", index=False)
    print(f"📄 Missing credit report saved as {exports_dir / 'missing_credit_report.xlsx'}")
