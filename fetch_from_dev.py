"""
Fetch chat data from DEV environment
"""

import requests
import json
from datetime import datetime
import os

# DEV ENVIRONMENT CONFIGURATION
OPENWEBUI_URL = "https://amichat.dev.amivero-solutions.com"
API_KEY = os.environ.get('OPENWEBUI_API_KEY_DEV', os.environ.get('OPENWEBUI_API_KEY', ''))

def fetch_chats_from_dev():
    """Fetch chats from dev environment"""
    
    if not API_KEY:
        print("="*80)
        print("API KEY REQUIRED")
        print("="*80)
        print("\nTo fetch from DEV environment, you need an API key.")
        print("\nHow to get it:")
        print("  1. Go to: https://amichat.dev.amivero-solutions.com")
        print("  2. Login as admin")
        print("  3. Settings → Account/API → Generate Key")
        print("\nThen set environment variable:")
        print("  $env:OPENWEBUI_API_KEY_DEV = 'your-dev-api-key'")
        print("\nOr export manually:")
        print("  1. Go to https://amichat.dev.amivero-solutions.com")
        print("  2. Admin Panel → Export Chats")
        print("  3. Save to this folder")
        print("  4. Run: python analyze_missions.py")
        print("="*80)
        return
    
    print("="*80)
    print("FETCHING FROM DEV ENVIRONMENT")
    print("="*80)
    print(f"URL: {OPENWEBUI_URL}")
    print()
    
    headers = {
        'Authorization': f'Bearer {API_KEY}',
        'Content-Type': 'application/json'
    }
    
    try:
        # Fetch chats
        print("Fetching chats...")
        url = f"{OPENWEBUI_URL}/api/v1/chats"
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        chats = response.json()
        print(f"✓ Fetched {len(chats)} chats from DEV")
        
        # Fetch users
        print("Fetching user information...")
        try:
            url = f"{OPENWEBUI_URL}/api/v1/users"
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            users = response.json()
            print(f"✓ Fetched {len(users)} users from DEV")
            
            # Create user mapping
            user_mapping = {}
            for user in users:
                user_id = user.get('id')
                name = user.get('name', '')
                email = user.get('email', '')
                display = name if name else (email.split('@')[0] if email else user_id[:8])
                if user_id:
                    user_mapping[user_id] = display
            
            with open('user_names.json', 'w', encoding='utf-8') as f:
                json.dump(user_mapping, f, indent=2, ensure_ascii=False)
            print(f"✓ Created user_names.json with {len(user_mapping)} users")
            
        except Exception as e:
            print(f"! Could not fetch users: {e}")
            print("  (Continuing with chats only)")
        
        # Save export
        timestamp = int(datetime.now().timestamp() * 1000)
        filename = f'all-chats-export-DEV-{timestamp}.json'
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(chats, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Saved to: {filename}")
        print()
        print("="*80)
        print("FETCH COMPLETE - Running analysis...")
        print("="*80)
        print()
        
        # Run analysis
        os.system('python analyze_missions.py')
        
    except requests.exceptions.RequestException as e:
        print(f"\n✗ Error: {e}")
        print("\nPossible issues:")
        print("  - API key is invalid")
        print("  - No access to dev environment")
        print("  - Network connectivity issue")
        print("  - Dev environment is down")
        print("\nTry manual export instead:")
        print("  1. Visit: https://amichat.dev.amivero-solutions.com")
        print("  2. Admin Panel → Export Chats")
        print("  3. Save file here and run: python analyze_missions.py")

if __name__ == '__main__':
    # Check if requests is installed
    try:
        import requests
    except ImportError:
        print("Installing requests library...")
        os.system('pip install requests')
        import requests
    
    fetch_chats_from_dev()

