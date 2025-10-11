"""
Fetch chat data directly from OpenWebUI API
Eliminates need for manual export
"""

import requests
import json
from datetime import datetime
import os
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"

class OpenWebUIFetcher:
    def __init__(self, base_url, api_key):
        """
        Initialize OpenWebUI API client
        
        Args:
            base_url: OpenWebUI instance URL (e.g., 'https://amichat.prod.amivero-solutions.com')
            api_key: API key from OpenWebUI admin settings
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
    
    def fetch_all_chats(self):
        """Fetch all chats from OpenWebUI"""
        print("Fetching chats from OpenWebUI...")
        
        try:
            # OpenWebUI API endpoint for chats
            url = f"{self.base_url}/api/v1/chats"
            
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            chats = response.json()
            print(f"✓ Successfully fetched {len(chats)} chats")
            
            return chats
            
        except requests.exceptions.RequestException as e:
            print(f"✗ Error fetching chats: {e}")
            return None
    
    def fetch_user_info(self):
        """Fetch user information from OpenWebUI"""
        print("Fetching user information...")
        
        try:
            url = f"{self.base_url}/api/v1/users"
            
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            users = response.json()
            print(f"✓ Successfully fetched {len(users)} users")
            
            return users
            
        except requests.exceptions.RequestException as e:
            print(f"✗ Error fetching users: {e}")
            return None
    
    def save_export(self, chats, filename=None):
        """Save chats to JSON file in same format as manual export"""
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        if filename is None:
            timestamp = int(datetime.now().timestamp() * 1000)
            filename = f'all-chats-export-{timestamp}.json'
        
        export_path = Path(filename)
        if not export_path.is_absolute():
            export_path = DATA_DIR / export_path

        with open(export_path, 'w', encoding='utf-8') as f:
            json.dump(chats, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Saved to: {export_path}")
        return str(export_path)
    
    def create_user_mapping(self, users):
        """Create user_names.json from user data"""
        if not users:
            return
        
        user_mapping = {
            "_comment": "Auto-generated from OpenWebUI API",
            "_updated": datetime.now().isoformat()
        }
        
        for user in users:
            user_id = user.get('id')
            name = user.get('name', '')
            email = user.get('email', '')
            
            # Use name or email as display name
            display_name = name if name else email.split('@')[0] if email else f"User {user_id[:8]}"
            
            if user_id:
                user_mapping[user_id] = display_name
        
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        user_mapping_path = DATA_DIR / 'user_names.json'

        with open(user_mapping_path, 'w', encoding='utf-8') as f:
            json.dump(user_mapping, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Created {user_mapping_path.name} with {len(user_mapping)-2} users at {user_mapping_path}")


def main():
    """Main function - configure and run"""
    
    # Configuration - UPDATE THESE VALUES
    OPENWEBUI_URL = "https://amichat.prod.amivero-solutions.com"
    API_KEY = os.environ.get('OPENWEBUI_API_KEY', '')
    
    # Check if API key is set
    if not API_KEY:
        print("="*80)
        print("SETUP REQUIRED")
        print("="*80)
        print("\nTo use direct API access, you need an API key from OpenWebUI.")
        print("\nHow to get API key:")
        print("  1. Go to OpenWebUI")
        print("  2. Click your profile → Settings")
        print("  3. Go to 'Account' or 'API' section")
        print("  4. Generate/Copy API key")
        print("\nThen either:")
        print("  A) Set environment variable: OPENWEBUI_API_KEY=your-key-here")
        print("  B) Edit this file and paste key in API_KEY variable")
        print("\n" + "="*80)
        return
    
    # Initialize fetcher
    fetcher = OpenWebUIFetcher(OPENWEBUI_URL, API_KEY)
    
    # Fetch data
    print("\n" + "="*80)
    print("FETCHING DATA FROM OPENWEBUI")
    print("="*80 + "\n")
    
    # Get chats
    chats = fetcher.fetch_all_chats()
    if not chats:
        print("Failed to fetch chats. Check your API key and URL.")
        return
    
    # Get users (for name mapping)
    users = fetcher.fetch_user_info()
    
    # Save export
    filename = fetcher.save_export(chats)
    
    # Create user mapping if we got user data
    if users:
        fetcher.create_user_mapping(users)
    
    print("\n" + "="*80)
    print("FETCH COMPLETE")
    print("="*80)
    print(f"\n✓ Exported {len(chats)} chats to: {filename}")
    
    # Automatically run analysis
    print("\nRunning analysis...")
    os.system('python analyze_missions.py')


if __name__ == '__main__':
    main()
