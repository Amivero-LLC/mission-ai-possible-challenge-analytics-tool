"""
Mission Analysis System for OpenWebUI Challenge Tracking
Analyzes employee mission attempts, completions, and generates leaderboards
"""

import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"


class MissionAnalyzer:
    def __init__(self, json_file=None, user_names_file=None, verbose=True, data=None, user_names=None):
        """
        Initialize analyzer; accepts either a path to an export file or an in-memory
        chat list (useful when fetching data from external APIs).
        """
        if json_file is None and data is None:
            raise ValueError("Either json_file or data must be provided to MissionAnalyzer")

        self.json_file = Path(json_file) if json_file else None
        self.user_names_file = Path(user_names_file) if user_names_file else DATA_DIR / 'user_names.json'
        self.data = data or []
        self.mission_chats = []
        self.user_names = {}
        self.verbose = verbose
        self.user_stats = defaultdict(lambda: {
            'user_id': '',
            'missions_attempted': [],
            'missions_completed': [],
            'total_attempts': 0,
            'total_completions': 0,
            'total_messages': 0,
            'first_attempt': None,
            'last_attempt': None
        })
        
        # Mission model patterns
        self.mission_patterns = [
            r'maip.*challenge',
            r'maip.*week',
            r'.*mission.*',
            r'.*challenge.*'
        ]
        
        # Success indicators (keywords in AI responses that indicate success)
        self.success_keywords = [
            'congratulations', 'you did it', 'success', 'correct', 'well done',
            'you found it', 'unlocked', 'revealed', 'mission accomplished',
            'you passed', 'challenge complete', 'great job', 'excellent work',
            'you succeeded', 'you win', 'you got it'
        ]
        
        if user_names:
            self.user_names.update(user_names)
            self.load_user_names(merge=True)
        else:
            self.load_user_names()
        if not self.data:
            self.load_data()
    
    def load_user_names(self, merge=False):
        """Load user names from mapping file"""
        try:
            with open(self.user_names_file, 'r', encoding='utf-8') as f:
                file_names = json.load(f)
            # Remove comment fields
            file_names = {k: v for k, v in file_names.items() if not k.startswith('_')}
            if merge:
                original = len(self.user_names)
                self.user_names.update(file_names)
                if self.verbose:
                    print(f"Merged {len(file_names)} user name mappings (from {original} existing)")
            else:
                self.user_names = file_names
                if self.verbose:
                    print(f"Loaded {len(self.user_names)} user name mappings")
        except FileNotFoundError:
            if self.verbose:
                print(f"No user_names.json found at {self.user_names_file} - showing user IDs")
            if not merge:
                self.user_names = {}
        except json.JSONDecodeError:
            if self.verbose:
                print(f"Warning: Invalid user_names.json at {self.user_names_file} - using default names")
            if not merge:
                self.user_names = {}
    
    def get_user_name(self, user_id):
        """Get user name from ID, or show first part of UUID"""
        if user_id in self.user_names:
            return self.user_names[user_id]
        # Show first 13 characters of UUID for better identification
        return user_id[:13] if len(user_id) > 13 else user_id
    
    def load_data(self):
        """Load chat data from JSON file"""
        if not self.json_file:
            if self.verbose:
                print("No JSON file provided; using data supplied directly.")
            return

        try:
            with open(self.json_file, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
            if self.verbose:
                print(f"Loaded {len(self.data)} chats from {self.json_file}")
        except FileNotFoundError:
            if self.verbose:
                print(f"Error: File {self.json_file} not found")
            self.data = []
        except json.JSONDecodeError:
            if self.verbose:
                print(f"Error: Invalid JSON in {self.json_file}")
            self.data = []
    
    def is_mission_model(self, model_name):
        """Check if model name matches mission patterns"""
        model_lower = str(model_name).lower()
        for pattern in self.mission_patterns:
            if re.search(pattern, model_lower):
                return True
        return False
    
    def extract_mission_info(self, model_name):
        """Extract mission details from model name"""
        model_str = str(model_name).lower()
        
        # Try to extract week number
        week_match = re.search(r'week[-_]?(\d+)', model_str)
        week = int(week_match.group(1)) if week_match else None
        
        # Try to extract challenge number
        challenge_match = re.search(r'challenge[-_]?(\d+)', model_str)
        challenge = int(challenge_match.group(1)) if challenge_match else None
        
        return {
            'model': model_name,
            'week': week,
            'challenge': challenge,
            'mission_id': f"Week {week}, Challenge {challenge}" if week and challenge else model_name
        }
    
    def check_success(self, messages):
        """Check if mission was completed successfully"""
        for msg in messages:
            if msg.get('role') == 'assistant':
                content = msg.get('content', '').lower()
                if any(keyword in content for keyword in self.success_keywords):
                    return True
        return False
    
    def analyze_missions(self, filter_week=None, filter_challenge=None, filter_user=None):
        """
        Analyze mission attempts with optional filters
        
        Args:
            filter_week: Only analyze missions from specific week (e.g., 1, 2)
            filter_challenge: Only analyze specific challenge number (e.g., 1, 2)
            filter_user: Only analyze attempts from specific user ID
        """
        self.mission_chats = []
        
        for i, item in enumerate(self.data, 1):
            chat = item.get('chat', {})
            models = chat.get('models', [])
            messages = chat.get('messages', [])
            
            # Check if any model is a mission model
            mission_model = None
            for model in models:
                if self.is_mission_model(model):
                    mission_model = model
                    break
            
            # Also check individual messages
            if not mission_model:
                for msg in messages:
                    msg_model = msg.get('model', '')
                    if msg_model and self.is_mission_model(msg_model):
                        mission_model = msg_model
                        break
            
            if mission_model:
                mission_info = self.extract_mission_info(mission_model)
                user_id = item.get('user_id', 'Unknown')
                title = item.get('title', 'Untitled')
                created_at = item.get('created_at')
                
                # Apply filters
                if filter_week and mission_info['week'] != filter_week:
                    continue
                if filter_challenge and mission_info['challenge'] != filter_challenge:
                    continue
                if filter_user and user_id != filter_user:
                    continue
                
                # Check if completed
                completed = self.check_success(messages)
                
                mission_data = {
                    'chat_num': i,
                    'user_id': user_id,
                    'title': title,
                    'model': mission_model,
                    'mission_info': mission_info,
                    'messages': messages,
                    'message_count': len(messages),
                    'created_at': created_at,
                    'completed': completed
                }
                
                self.mission_chats.append(mission_data)
                
                # Update user stats
                self.user_stats[user_id]['user_id'] = user_id
                self.user_stats[user_id]['missions_attempted'].append(mission_info['mission_id'])
                self.user_stats[user_id]['total_attempts'] += 1
                self.user_stats[user_id]['total_messages'] += len(messages)
                
                if completed:
                    self.user_stats[user_id]['missions_completed'].append(mission_info['mission_id'])
                    self.user_stats[user_id]['total_completions'] += 1
                
                if not self.user_stats[user_id]['first_attempt']:
                    self.user_stats[user_id]['first_attempt'] = created_at
                self.user_stats[user_id]['last_attempt'] = created_at
        
        return len(self.mission_chats)
    
    def get_leaderboard(self, sort_by='completions'):
        """
        Get leaderboard sorted by various criteria
        
        Args:
            sort_by: 'completions', 'attempts', 'efficiency' (completions/attempts)
        """
        leaderboard = []
        
        for user_id, stats in self.user_stats.items():
            efficiency = (stats['total_completions'] / stats['total_attempts'] * 100) if stats['total_attempts'] > 0 else 0
            
            leaderboard.append({
                'user_id': user_id,
                'attempts': stats['total_attempts'],
                'completions': stats['total_completions'],
                'efficiency': efficiency,
                'total_messages': stats['total_messages'],
                'unique_missions_attempted': len(set(stats['missions_attempted'])),
                'unique_missions_completed': len(set(stats['missions_completed']))
            })
        
        # Sort based on criteria
        if sort_by == 'completions':
            leaderboard.sort(key=lambda x: (x['completions'], -x['attempts']), reverse=True)
        elif sort_by == 'attempts':
            leaderboard.sort(key=lambda x: x['attempts'], reverse=True)
        elif sort_by == 'efficiency':
            leaderboard.sort(key=lambda x: (x['efficiency'], x['completions']), reverse=True)
        
        return leaderboard
    
    def get_summary(self):
        """Get overall summary statistics"""
        total_attempts = len(self.mission_chats)
        total_completions = sum(1 for chat in self.mission_chats if chat['completed'])
        unique_users = len(self.user_stats)
        
        success_rate = (total_completions / total_attempts * 100) if total_attempts > 0 else 0
        
        # Get unique missions
        unique_missions = set()
        for chat in self.mission_chats:
            unique_missions.add(chat['mission_info']['mission_id'])
        
        return {
            'total_chats': len(self.data),
            'mission_attempts': total_attempts,
            'mission_completions': total_completions,
            'success_rate': success_rate,
            'unique_users': unique_users,
            'unique_missions': len(unique_missions),
            'missions_list': sorted(unique_missions)
        }
    
    def get_mission_breakdown(self):
        """Get breakdown by mission type"""
        breakdown = defaultdict(lambda: {'attempts': 0, 'completions': 0, 'users': set()})
        
        for chat in self.mission_chats:
            mission_id = chat['mission_info']['mission_id']
            breakdown[mission_id]['attempts'] += 1
            breakdown[mission_id]['users'].add(chat['user_id'])
            if chat['completed']:
                breakdown[mission_id]['completions'] += 1
        
        # Convert to list
        result = []
        for mission_id, stats in breakdown.items():
            result.append({
                'mission': mission_id,
                'attempts': stats['attempts'],
                'completions': stats['completions'],
                'success_rate': (stats['completions'] / stats['attempts'] * 100) if stats['attempts'] > 0 else 0,
                'unique_users': len(stats['users'])
            })
        
        result.sort(key=lambda x: x['attempts'], reverse=True)
        return result


def find_latest_export():
    """Find the most recent export file"""
    if not DATA_DIR.exists():
        return None

    json_files = sorted(DATA_DIR.glob('all-chats-export-*.json'), reverse=True)
    if not json_files:
        return None
    # Sort by filename (timestamp in filename)
    return str(json_files[0])


if __name__ == '__main__':
    # Find latest export
    latest_file = find_latest_export()
    
    if not latest_file:
        print("No export files found! Please add a chat export JSON file to the data/ directory.")
        exit(1)
    
    print(f"Using: {latest_file}\n")
    
    # Initialize analyzer
    analyzer = MissionAnalyzer(latest_file)
    
    # Analyze all missions
    mission_count = analyzer.analyze_missions()
    
    # Get summary
    summary = analyzer.get_summary()
    
    print("="*80)
    print("MISSION ANALYSIS SUMMARY")
    print("="*80)
    print(f"Total Chats in Export: {summary['total_chats']}")
    print(f"Mission Attempts: {mission_count}")
    print(f"Mission Completions: {summary['mission_completions']}")
    print(f"Success Rate: {summary['success_rate']:.1f}%")
    print(f"Unique Participants: {summary['unique_users']}")
    print(f"Unique Missions: {summary['unique_missions']}")
    
    if summary['missions_list']:
        print(f"\nMissions Found:")
        for mission in summary['missions_list']:
            print(f"  - {mission}")
    
    print("\n" + "="*80)
    
    if mission_count == 0:
        print("No mission attempts found yet!")
        print("\nWaiting for employees to attempt missions using models like:")
        print("  - maip---week-1---challenge-1")
        print("  - maip---week-1---challenge-2")
        print("  - etc.")
    else:
        # Show leaderboard
        print("\nTOP PERFORMERS (by completions):")
        print("-"*80)
        leaderboard = analyzer.get_leaderboard(sort_by='completions')
        
        for i, user in enumerate(leaderboard[:10], 1):
            print(f"{i}. User: {user['user_id'][:30]}...")
            print(f"   Completions: {user['completions']} | Attempts: {user['attempts']} | Efficiency: {user['efficiency']:.1f}%")
        
        # Mission breakdown
        print("\n" + "="*80)
        print("MISSION BREAKDOWN")
        print("="*80)
        breakdown = analyzer.get_mission_breakdown()
        for mission_stats in breakdown:
            print(f"\n{mission_stats['mission']}")
            print(f"  Attempts: {mission_stats['attempts']}")
            print(f"  Completions: {mission_stats['completions']}")
            print(f"  Success Rate: {mission_stats['success_rate']:.1f}%")
            print(f"  Unique Users: {mission_stats['unique_users']}")
    
    print("\n" + "="*80)
