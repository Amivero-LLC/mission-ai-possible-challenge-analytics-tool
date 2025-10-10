"""
Generate Interactive HTML Dashboard for Mission Analysis
"""

import json
from datetime import datetime
from mission_analyzer import MissionAnalyzer, find_latest_export


def generate_html_dashboard(analyzer, output_file='mission_dashboard.html'):
    """Generate a beautiful interactive HTML dashboard"""
    
    summary = analyzer.get_summary()
    leaderboard = analyzer.get_leaderboard(sort_by='completions')
    mission_breakdown = analyzer.get_mission_breakdown()
    
    # Calculate additional stats
    participation_rate = (summary['unique_users'] / summary['total_chats'] * 100) if summary['total_chats'] > 0 else 0
    
    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mission Challenge Dashboard - Amivero</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            min-height: 100vh;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            padding: 40px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }}
        
        .header {{
            text-align: center;
            margin-bottom: 40px;
            padding-bottom: 20px;
            border-bottom: 3px solid #667eea;
        }}
        
        .header h1 {{
            color: #667eea;
            font-size: 2.8em;
            margin-bottom: 10px;
        }}
        
        .header .subtitle {{
            color: #666;
            font-size: 1.2em;
        }}
        
        .header .timestamp {{
            color: #999;
            font-size: 0.9em;
            margin-top: 10px;
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }}
        
        .stat-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 15px;
            text-align: center;
            box-shadow: 0 8px 20px rgba(102, 126, 234, 0.4);
            transition: transform 0.3s ease;
        }}
        
        .stat-card:hover {{
            transform: translateY(-5px);
        }}
        
        .stat-value {{
            font-size: 3.5em;
            font-weight: bold;
            margin: 15px 0;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
        }}
        
        .stat-label {{
            font-size: 1.1em;
            opacity: 0.95;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        
        .stat-sublabel {{
            font-size: 0.9em;
            opacity: 0.8;
            margin-top: 5px;
        }}
        
        .section {{
            margin: 50px 0;
        }}
        
        .section-title {{
            color: #667eea;
            font-size: 2em;
            margin-bottom: 25px;
            padding-bottom: 10px;
            border-bottom: 3px solid #667eea;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            border-radius: 10px;
            overflow: hidden;
        }}
        
        thead {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }}
        
        th {{
            padding: 18px 15px;
            text-align: left;
            font-weight: 600;
            font-size: 1.05em;
        }}
        
        td {{
            padding: 15px;
            border-bottom: 1px solid #eee;
        }}
        
        tbody tr:hover {{
            background-color: #f8f9ff;
        }}
        
        tbody tr:nth-child(even) {{
            background-color: #fafafa;
        }}
        
        .medal {{
            font-size: 1.8em;
            margin-right: 10px;
        }}
        
        .badge {{
            display: inline-block;
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: 600;
        }}
        
        .badge-success {{
            background-color: #d1fae5;
            color: #065f46;
        }}
        
        .badge-warning {{
            background-color: #fef3c7;
            color: #92400e;
        }}
        
        .badge-info {{
            background-color: #dbeafe;
            color: #1e40af;
        }}
        
        .progress-bar {{
            background-color: #e5e7eb;
            border-radius: 10px;
            height: 25px;
            overflow: hidden;
            margin: 10px 0;
        }}
        
        .progress-fill {{
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: 600;
            font-size: 0.9em;
            transition: width 0.5s ease;
        }}
        
        .no-data {{
            text-align: center;
            padding: 60px 20px;
            color: #666;
        }}
        
        .no-data h2 {{
            color: #667eea;
            font-size: 2em;
            margin-bottom: 15px;
        }}
        
        .no-data p {{
            font-size: 1.2em;
            margin: 10px 0;
        }}
        
        .filters {{
            background: #f8f9ff;
            padding: 25px;
            border-radius: 15px;
            margin: 30px 0;
            border: 2px solid #e0e7ff;
        }}
        
        .filters h3 {{
            color: #667eea;
            margin-bottom: 15px;
        }}
        
        .filter-group {{
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
        }}
        
        .filter-button {{
            padding: 10px 20px;
            border: 2px solid #667eea;
            background: white;
            color: #667eea;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.3s ease;
        }}
        
        .filter-button:hover {{
            background: #667eea;
            color: white;
        }}
        
        .mission-card {{
            background: #f8f9ff;
            padding: 20px;
            border-radius: 12px;
            margin: 15px 0;
            border-left: 5px solid #667eea;
        }}
        
        .mission-card h4 {{
            color: #667eea;
            margin-bottom: 10px;
        }}
        
        .mission-stats {{
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
            margin-top: 10px;
        }}
        
        .mission-stat {{
            background: white;
            padding: 10px 15px;
            border-radius: 8px;
            font-size: 0.95em;
        }}
        
        .mission-stat strong {{
            color: #667eea;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎯 Mission Challenge Dashboard</h1>
            <div class="subtitle">OpenWebUI Employee Engagement Tracker</div>
            <div class="timestamp">Last Updated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</div>
        </div>
"""

    # Stats Grid
    html += f"""
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-label">Total Chats</div>
                <div class="stat-value">{summary['total_chats']}</div>
                <div class="stat-sublabel">In System</div>
            </div>
            
            <div class="stat-card">
                <div class="stat-label">Mission Attempts</div>
                <div class="stat-value">{summary['mission_attempts']}</div>
                <div class="stat-sublabel">Across All Missions</div>
            </div>
            
            <div class="stat-card">
                <div class="stat-label">Completions</div>
                <div class="stat-value">{summary['mission_completions']}</div>
                <div class="stat-sublabel">{summary['success_rate']:.1f}% Success Rate</div>
            </div>
            
            <div class="stat-card">
                <div class="stat-label">Participants</div>
                <div class="stat-value">{summary['unique_users']}</div>
                <div class="stat-sublabel">{participation_rate:.1f}% Participation</div>
            </div>
        </div>
"""

    if summary['mission_attempts'] == 0:
        # No mission data yet
        html += """
        <div class="no-data">
            <h2>🚀 No Mission Attempts Yet</h2>
            <p>The mission system is ready and waiting for employees to participate!</p>
            <p style="margin-top: 20px;">Employees can access missions at:</p>
            <p style="font-family: monospace; background: #f0f0f0; padding: 15px; border-radius: 8px; display: inline-block; margin-top: 10px;">
                https://amichat.prod.amivero-solutions.com/?model=maip---week-1---challenge-1
            </p>
            <p style="margin-top: 30px; font-size: 1.1em; color: #667eea; font-weight: 600;">
                💡 Promote the mission link to encourage participation!
            </p>
        </div>
"""
    else:
        # Show leaderboard and mission breakdown
        html += """
        <div class="section">
            <h2 class="section-title">🏆 Leaderboard - Top Performers</h2>
            <table>
                <thead>
                    <tr>
                        <th>Rank</th>
                        <th>User ID</th>
                        <th>Completions</th>
                        <th>Attempts</th>
                        <th>Success Rate</th>
                        <th>Messages</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
"""
        
        medals = ['🥇', '🥈', '🥉']
        for i, user in enumerate(leaderboard, 1):
            medal = medals[i-1] if i <= 3 else f"{i}"
            status_badge = 'badge-success' if user['completions'] > 0 else 'badge-warning'
            status_text = f"{user['completions']} Complete" if user['completions'] > 0 else "In Progress"
            
            html += f"""
                    <tr>
                        <td><span class="medal">{medal}</span></td>
                        <td><code>{user['user_id'][:35]}...</code></td>
                        <td><strong>{user['completions']}</strong></td>
                        <td>{user['attempts']}</td>
                        <td>
                            <div class="progress-bar">
                                <div class="progress-fill" style="width: {user['efficiency']}%">
                                    {user['efficiency']:.0f}%
                                </div>
                            </div>
                        </td>
                        <td>{user['total_messages']}</td>
                        <td><span class="badge {status_badge}">{status_text}</span></td>
                    </tr>
"""
        
        html += """
                </tbody>
            </table>
        </div>
"""
        
        # Mission Breakdown
        html += """
        <div class="section">
            <h2 class="section-title">📊 Mission Breakdown</h2>
"""
        
        if mission_breakdown:
            for mission in mission_breakdown:
                html += f"""
            <div class="mission-card">
                <h4>{mission['mission']}</h4>
                <div class="mission-stats">
                    <div class="mission-stat">
                        <strong>Attempts:</strong> {mission['attempts']}
                    </div>
                    <div class="mission-stat">
                        <strong>Completions:</strong> {mission['completions']}
                    </div>
                    <div class="mission-stat">
                        <strong>Success Rate:</strong> {mission['success_rate']:.1f}%
                    </div>
                    <div class="mission-stat">
                        <strong>Unique Users:</strong> {mission['unique_users']}
                    </div>
                </div>
                <div class="progress-bar" style="margin-top: 15px;">
                    <div class="progress-fill" style="width: {mission['success_rate']}%">
                        {mission['success_rate']:.0f}% Success
                    </div>
                </div>
            </div>
"""
        else:
            html += "<p>No mission data available yet.</p>"
        
        html += """
        </div>
"""
    
    # Footer
    html += f"""
        <div style="text-align: center; margin-top: 50px; padding-top: 30px; border-top: 2px solid #eee; color: #999;">
            <p>Dashboard auto-generated from: {analyzer.json_file}</p>
            <p style="margin-top: 10px;">Run <code>python analyze_missions.py</code> to update</p>
        </div>
    </div>
</body>
</html>
"""
    
    # Write to file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"Dashboard generated: {output_file}")
    return output_file


if __name__ == '__main__':
    # Find latest export
    latest_file = find_latest_export()
    
    if not latest_file:
        print("No export files found!")
        exit(1)
    
    print(f"Generating dashboard from: {latest_file}\n")
    
    # Analyze
    analyzer = MissionAnalyzer(latest_file)
    analyzer.analyze_missions()
    
    # Generate dashboard
    dashboard_file = generate_html_dashboard(analyzer)
    
    print(f"\nDashboard ready: {dashboard_file}")
    print("Open it in your browser to view the results!")

