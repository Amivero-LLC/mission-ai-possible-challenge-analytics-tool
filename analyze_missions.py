"""
Mission Analysis - Main Entry Point
Easy-to-use script with filters and options
"""

import sys
import os
from mission_analyzer import MissionAnalyzer, find_latest_export
from generate_enhanced_dashboard import generate_enhanced_dashboard


def print_banner():
    print("="*80)
    print("  MISSION CHALLENGE ANALYZER")
    print("  OpenWebUI Employee Engagement Tracker")
    print("="*80)
    print()


def print_help():
    print("""
Usage: python analyze_missions.py [options]

Options:
  --help              Show this help message
  --file <path>       Use specific JSON file (default: latest export)
  --week <number>     Filter by week number (e.g., --week 1)
  --challenge <num>   Filter by challenge number (e.g., --challenge 1)
  --user <user_id>    Filter by specific user ID
  --no-dashboard      Skip HTML dashboard generation
  --export-json       Export results to JSON file
  --export-csv        Export results to CSV file

Examples:
  python analyze_missions.py
  python analyze_missions.py --week 1
  python analyze_missions.py --week 1 --challenge 1
  python analyze_missions.py --user abc123...
  python analyze_missions.py --export-csv
  
""")


def export_to_json(analyzer, filename='mission_results.json'):
    """Export analysis results to JSON"""
    import json
    
    summary = analyzer.get_summary()
    leaderboard = analyzer.get_leaderboard(sort_by='completions')
    breakdown = analyzer.get_mission_breakdown()
    
    results = {
        'summary': summary,
        'leaderboard': leaderboard,
        'mission_breakdown': breakdown,
        'mission_chats': [
            {
                'user_id': chat['user_id'],
                'mission': chat['mission_info']['mission_id'],
                'completed': chat['completed'],
                'message_count': chat['message_count'],
                'created_at': chat['created_at']
            }
            for chat in analyzer.mission_chats
        ]
    }
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"Results exported to: {filename}")


def export_to_csv(analyzer, filename='mission_results.csv'):
    """Export leaderboard to CSV"""
    import csv
    
    leaderboard = analyzer.get_leaderboard(sort_by='completions')
    
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['Rank', 'User ID', 'Attempts', 'Completions', 'Success Rate (%)', 
                     'Total Messages', 'Unique Missions Attempted', 'Unique Missions Completed']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        
        writer.writeheader()
        for i, user in enumerate(leaderboard, 1):
            writer.writerow({
                'Rank': i,
                'User ID': user['user_id'],
                'Attempts': user['attempts'],
                'Completions': user['completions'],
                'Success Rate (%)': f"{user['efficiency']:.1f}",
                'Total Messages': user['total_messages'],
                'Unique Missions Attempted': user['unique_missions_attempted'],
                'Unique Missions Completed': user['unique_missions_completed']
            })
    
    print(f"Leaderboard exported to: {filename}")


def main():
    print_banner()
    
    # Parse command line arguments
    args = sys.argv[1:]
    
    if '--help' in args or '-h' in args:
        print_help()
        return
    
    # Get options
    json_file = None
    filter_week = None
    filter_challenge = None
    filter_user = None
    generate_dash = True
    export_json_flag = False
    export_csv_flag = False
    
    i = 0
    while i < len(args):
        if args[i] == '--file' and i + 1 < len(args):
            json_file = args[i + 1]
            i += 2
        elif args[i] == '--week' and i + 1 < len(args):
            filter_week = int(args[i + 1])
            i += 2
        elif args[i] == '--challenge' and i + 1 < len(args):
            filter_challenge = int(args[i + 1])
            i += 2
        elif args[i] == '--user' and i + 1 < len(args):
            filter_user = args[i + 1]
            i += 2
        elif args[i] == '--no-dashboard':
            generate_dash = False
            i += 1
        elif args[i] == '--export-json':
            export_json_flag = True
            i += 1
        elif args[i] == '--export-csv':
            export_csv_flag = True
            i += 1
        else:
            print(f"Unknown option: {args[i]}")
            print("Use --help for usage information")
            return
            i += 1
    
    # Find file
    if not json_file:
        json_file = find_latest_export()
    
    if not json_file or not os.path.exists(json_file):
        print("No export file found!")
        print("\nPlease ensure you have a chat export JSON file in the current directory.")
        print("File should be named: all-chats-export-<timestamp>.json")
        return
    
    print(f"Using file: {json_file}")
    
    # Show active filters
    filters_active = []
    if filter_week:
        filters_active.append(f"Week {filter_week}")
    if filter_challenge:
        filters_active.append(f"Challenge {filter_challenge}")
    if filter_user:
        filters_active.append(f"User {filter_user[:20]}...")
    
    if filters_active:
        print(f"Active filters: {', '.join(filters_active)}")
    
    print()
    
    # Initialize analyzer
    analyzer = MissionAnalyzer(json_file)
    
    # Analyze with filters
    mission_count = analyzer.analyze_missions(
        filter_week=filter_week,
        filter_challenge=filter_challenge,
        filter_user=filter_user
    )
    
    # Get summary
    summary = analyzer.get_summary()
    
    # Display results
    print()
    print("="*80)
    print("ANALYSIS RESULTS")
    print("="*80)
    print(f"Total Chats in Export: {summary['total_chats']}")
    print(f"Mission Attempts Found: {mission_count}")
    print(f"Mission Completions: {summary['mission_completions']}")
    print(f"Success Rate: {summary['success_rate']:.1f}%")
    print(f"Unique Participants: {summary['unique_users']}")
    
    if summary['missions_list']:
        print(f"\nMissions Identified:")
        for mission in summary['missions_list']:
            print(f"  - {mission}")
    
    print()
    
    if mission_count == 0:
        print("="*80)
        print("NO MISSION ATTEMPTS YET")
        print("="*80)
        print()
        print("The system is ready! Employees can access missions at:")
        print("  https://amichat.prod.amivero-solutions.com/?model=maip---week-1---challenge-1")
        print()
        print("Tips:")
        print("  - Share the mission link with employees")
        print("  - Send reminder emails about the challenge")
        print("  - Run this script again after employees participate")
        print()
    else:
        # Show top performers
        print("="*80)
        print("TOP PERFORMERS")
        print("="*80)
        leaderboard = analyzer.get_leaderboard(sort_by='completions')
        
        for i, user in enumerate(leaderboard[:10], 1):
            rank = f"#{i}"
            print(f"{rank:>4} {user['user_id'][:35]}...")
            print(f"     Completions: {user['completions']} | Attempts: {user['attempts']} | "
                  f"Success Rate: {user['efficiency']:.1f}% | Messages: {user['total_messages']}")
        
        # Mission breakdown
        print()
        print("="*80)
        print("MISSION BREAKDOWN")
        print("="*80)
        breakdown = analyzer.get_mission_breakdown()
        
        for mission_stats in breakdown:
            print(f"\n{mission_stats['mission']}")
            print(f"   Attempts: {mission_stats['attempts']} | "
                  f"Completions: {mission_stats['completions']} | "
                  f"Success Rate: {mission_stats['success_rate']:.1f}% | "
                  f"Participants: {mission_stats['unique_users']}")
    
    print()
    print("="*80)
    
    # Generate outputs
    if export_json_flag:
        print()
        export_to_json(analyzer)
    
    if export_csv_flag:
        print()
        export_to_csv(analyzer)
    
    if generate_dash:
        print()
        print("Generating enhanced dashboard...")
        dashboard_file = generate_enhanced_dashboard(analyzer)
        print()
        print(f"Dashboard ready: {dashboard_file}")
        print("  Open it in your browser to view all chats and results!")
        
        # Try to open in browser
        try:
            import webbrowser
            webbrowser.open(dashboard_file)
            print("  (Opening in browser...)")
        except:
            pass
    
    print()
    print("="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)
    print()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nAnalysis interrupted by user")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

