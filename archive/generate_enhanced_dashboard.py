"""
Generate Enhanced Interactive HTML Dashboard with All Chats View
"""

import json
from datetime import datetime
from pathlib import Path
from mission_analyzer import MissionAnalyzer, find_latest_export


DEFAULT_DASHBOARD_PATH = Path('public') / 'mission_dashboard.html'


def generate_enhanced_dashboard(analyzer, output_file=None):
    """Generate an enhanced interactive HTML dashboard with all chats"""
    
    summary = analyzer.get_summary()
    leaderboard = analyzer.get_leaderboard(sort_by='completions')
    mission_breakdown = analyzer.get_mission_breakdown()
    
    output_path = Path(output_file) if output_file else DEFAULT_DASHBOARD_PATH
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Get all chats with categorization
    all_chats = []
    mission_chat_ids = set(chat['chat_num'] for chat in analyzer.mission_chats)
    
    for i, item in enumerate(analyzer.data, 1):
        chat = item.get('chat', {})
        models = chat.get('models', [])
        messages = chat.get('messages', [])
        
        is_mission = i in mission_chat_ids
        completed = False
        
        if is_mission:
            mission_chat = next((c for c in analyzer.mission_chats if c['chat_num'] == i), None)
            if mission_chat:
                completed = mission_chat['completed']
        
        user_id = item.get('user_id', 'Unknown')
        user_name = analyzer.get_user_name(user_id)
        
        all_chats.append({
            'num': i,
            'title': item.get('title', 'Untitled'),
            'user_id': user_id,
            'user_name': user_name,
            'created_at': item.get('created_at'),
            'model': models[0] if models else 'Unknown',
            'message_count': len(messages),
            'is_mission': is_mission,
            'completed': completed,
            'messages': messages[:3]  # First 3 messages for preview
        })
    
    # Model usage stats
    model_stats = {}
    for chat in all_chats:
        model = chat['model']
        if model not in model_stats:
            model_stats[model] = {'total': 0, 'mission': 0, 'completed': 0}
        model_stats[model]['total'] += 1
        if chat['is_mission']:
            model_stats[model]['mission'] += 1
        if chat['completed']:
            model_stats[model]['completed'] += 1
    
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
            max-width: 1600px;
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
        
        .tabs {{
            display: flex;
            gap: 10px;
            margin: 30px 0 20px 0;
            border-bottom: 2px solid #e5e7eb;
        }}
        
        .tab {{
            padding: 15px 30px;
            cursor: pointer;
            border: none;
            background: none;
            font-size: 1.1em;
            font-weight: 600;
            color: #666;
            border-bottom: 3px solid transparent;
            transition: all 0.3s ease;
        }}
        
        .tab:hover {{
            color: #667eea;
            background: #f8f9ff;
        }}
        
        .tab.active {{
            color: #667eea;
            border-bottom-color: #667eea;
            background: #f8f9ff;
        }}
        
        .tab-content {{
            display: none;
        }}
        
        .tab-content.active {{
            display: block;
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }}
        
        .stat-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 25px;
            border-radius: 15px;
            text-align: center;
            box-shadow: 0 8px 20px rgba(102, 126, 234, 0.4);
            transition: transform 0.3s ease;
        }}
        
        .stat-card:hover {{
            transform: translateY(-5px);
        }}
        
        .stat-value {{
            font-size: 3em;
            font-weight: bold;
            margin: 10px 0;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
        }}
        
        .stat-label {{
            font-size: 1em;
            opacity: 0.95;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        
        .stat-sublabel {{
            font-size: 0.85em;
            opacity: 0.8;
            margin-top: 5px;
        }}
        
        .section {{
            margin: 40px 0;
        }}
        
        .section-title {{
            color: #667eea;
            font-size: 1.8em;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 3px solid #667eea;
        }}
        
        .filters {{
            background: #f8f9ff;
            padding: 20px;
            border-radius: 12px;
            margin: 20px 0;
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
            align-items: center;
        }}
        
        .filter-label {{
            font-weight: 600;
            color: #667eea;
        }}
        
        .filter-input {{
            padding: 8px 15px;
            border: 2px solid #e0e7ff;
            border-radius: 8px;
            font-size: 0.95em;
            min-width: 200px;
        }}
        
        .filter-input:focus {{
            outline: none;
            border-color: #667eea;
        }}
        
        .filter-button {{
            padding: 8px 20px;
            border: 2px solid #667eea;
            background: #667eea;
            color: white;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.3s ease;
        }}
        
        .filter-button:hover {{
            background: #5568d3;
            border-color: #5568d3;
        }}
        
        .filter-button.secondary {{
            background: white;
            color: #667eea;
        }}
        
        .filter-button.secondary:hover {{
            background: #f8f9ff;
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
            padding: 15px 12px;
            text-align: left;
            font-weight: 600;
            font-size: 0.95em;
        }}
        
        td {{
            padding: 12px;
            border-bottom: 1px solid #eee;
            font-size: 0.9em;
        }}
        
        tbody tr:hover {{
            background-color: #f8f9ff;
        }}
        
        tbody tr:nth-child(even) {{
            background-color: #fafafa;
        }}
        
        .badge {{
            display: inline-block;
            padding: 5px 12px;
            border-radius: 15px;
            font-size: 0.8em;
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
        
        .badge-mission {{
            background-color: #e0e7ff;
            color: #4338ca;
        }}
        
        .badge-regular {{
            background-color: #f3f4f6;
            color: #6b7280;
        }}
        
        .chat-preview {{
            max-width: 300px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            color: #666;
            font-size: 0.85em;
        }}
        
        .expandable {{
            cursor: pointer;
            color: #667eea;
            text-decoration: underline;
        }}
        
        .chat-details {{
            display: none;
            background: #f8f9ff;
            padding: 15px;
            margin-top: 10px;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }}
        
        .chat-details.show {{
            display: block;
        }}
        
        .message {{
            background: white;
            padding: 10px;
            margin: 8px 0;
            border-radius: 8px;
            border-left: 3px solid #667eea;
        }}
        
        .message-role {{
            font-weight: 600;
            color: #667eea;
            margin-bottom: 5px;
        }}
        
        .progress-bar {{
            background-color: #e5e7eb;
            border-radius: 10px;
            height: 20px;
            overflow: hidden;
        }}
        
        .progress-fill {{
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: 600;
            font-size: 0.8em;
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
        
        .model-card {{
            background: #f8f9ff;
            padding: 20px;
            border-radius: 12px;
            margin: 15px 0;
            border-left: 5px solid #667eea;
        }}
        
        .model-card h4 {{
            color: #667eea;
            margin-bottom: 10px;
        }}
        
        .model-stats {{
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
            margin-top: 10px;
        }}
        
        .model-stat {{
            background: white;
            padding: 10px 15px;
            border-radius: 8px;
            font-size: 0.9em;
        }}
        
        .model-stat strong {{
            color: #667eea;
        }}
        
        code {{
            background: #f0f0f0;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Amivero's Mission: AI Possible</h1>
            <div class="subtitle">🎯 Mission Challenge Dashboard</div>
            <div class="timestamp">Last Updated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</div>
        </div>
        
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
            
            <div class="stat-card">
                <div class="stat-label">Models Used</div>
                <div class="stat-value">{len(model_stats)}</div>
                <div class="stat-sublabel">Unique Models</div>
            </div>
        </div>
        
        <div class="tabs">
            <button class="tab active" onclick="showTab('overview')">📊 Overview</button>
            <button class="tab" onclick="showTab('allchats')">💬 All Chats</button>
            <button class="tab" onclick="showTab('missions')">🎯 Missions</button>
            <button class="tab" onclick="showTab('models')">🤖 Models</button>
        </div>
"""

    # Overview Tab
    html += """
        <div id="overview" class="tab-content active">
"""
    
    if summary['mission_attempts'] == 0:
        html += """
            <div class="no-data">
                <h2>🚀 No Mission Attempts Yet</h2>
                <p>The mission system is ready and waiting for employees to participate!</p>
                <p style="margin-top: 20px;">Employees can access missions at:</p>
                <p style="font-family: monospace; background: #f0f0f0; padding: 15px; border-radius: 8px; display: inline-block; margin-top: 10px;">
                    https://amichat.prod.amivero-solutions.com/?model=maip---week-1---challenge-1
                </p>
            </div>
"""
    else:
        # Leaderboard
        html += """
            <div class="section">
                <h2 class="section-title">🏆 Leaderboard - Top Performers</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Rank</th>
                            <th>User</th>
                            <th>Completions</th>
                            <th>Attempts</th>
                            <th>Success Rate</th>
                            <th>Messages</th>
                        </tr>
                    </thead>
                    <tbody>
"""
        
        for i, user in enumerate(leaderboard[:10], 1):
            user_name = analyzer.get_user_name(user['user_id'])
            html += f"""
                        <tr>
                            <td><strong>#{i}</strong></td>
                            <td><strong>{user_name}</strong><br><small style="color: #999;"><code>{user['user_id'][:25]}...</code></small></td>
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
                        </tr>
"""
        
        html += """
                    </tbody>
                </table>
            </div>
"""
    
    html += """
        </div>
"""
    
    # All Chats Tab
    html += f"""
        <div id="allchats" class="tab-content">
            <div class="section">
                <h2 class="section-title">💬 All Conversations ({len(all_chats)} total)</h2>
                
                <div class="filters">
                    <span class="filter-label">Filter:</span>
                    <input type="text" id="searchInput" class="filter-input" placeholder="Search by title, user, or model..." onkeyup="filterChats()">
                    <select id="typeFilter" class="filter-input" onchange="filterChats()">
                        <option value="all">All Chats</option>
                        <option value="mission">Mission Chats Only</option>
                        <option value="regular">Regular Chats Only</option>
                        <option value="completed">Completed Missions</option>
                    </select>
                    <button class="filter-button secondary" onclick="resetFilters()">Clear Filters</button>
                </div>
                
                <table id="chatsTable">
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>Title</th>
                            <th>User</th>
                            <th>Model</th>
                            <th>Type</th>
                            <th>Messages</th>
                            <th>Status</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
"""
    
    for chat in all_chats:
        chat_type = 'mission' if chat['is_mission'] else 'regular'
        type_badge = 'badge-mission' if chat['is_mission'] else 'badge-regular'
        type_text = '🎯 Mission' if chat['is_mission'] else '💬 Regular'
        
        status = ''
        if chat['is_mission']:
            if chat['completed']:
                status = '<span class="badge badge-success">✓ Completed</span>'
            else:
                status = '<span class="badge badge-warning">⏳ In Progress</span>'
        else:
            status = '<span class="badge badge-info">-</span>'
        
        # Get first message preview
        preview = ''
        if chat['messages']:
            first_msg = chat['messages'][0]
            content = first_msg.get('content', '')[:100]
            preview = content + '...' if len(content) == 100 else content
        
        html += f"""
                        <tr class="chat-row" data-type="{chat_type}" data-completed="{str(chat['completed']).lower()}">
                            <td>{chat['num']}</td>
                            <td><strong>{chat['title']}</strong></td>
                            <td><strong>{chat['user_name']}</strong><br><small style="color: #999;">{chat['user_id'][:20]}...</small></td>
                            <td><code>{chat['model']}</code></td>
                            <td><span class="badge {type_badge}">{type_text}</span></td>
                            <td>{chat['message_count']}</td>
                            <td>{status}</td>
                            <td><span class="expandable" onclick="toggleDetails({chat['num']})">View</span></td>
                        </tr>
                        <tr id="details-{chat['num']}" class="chat-details-row">
                            <td colspan="8">
                                <div class="chat-details">
                                    <strong>First Messages Preview:</strong>
"""
        
        for j, msg in enumerate(chat['messages'][:3], 1):
            role = msg.get('role', 'unknown').title()
            content = msg.get('content', '')[:200]
            if len(content) == 200:
                content += '...'
            html += f"""
                                    <div class="message">
                                        <div class="message-role">{role}:</div>
                                        <div>{content}</div>
                                    </div>
"""
        
        if chat['message_count'] > 3:
            html += f"""
                                    <p style="margin-top: 10px; color: #666; font-style: italic;">
                                        ... and {chat['message_count'] - 3} more messages
                                    </p>
"""
        
        html += """
                                </div>
                            </td>
                        </tr>
"""
    
    html += """
                    </tbody>
                </table>
            </div>
        </div>
"""
    
    # Missions Tab
    html += """
        <div id="missions" class="tab-content">
"""
    
    if summary['mission_attempts'] > 0:
        html += """
            <div class="section">
                <h2 class="section-title">🎯 Mission Breakdown</h2>
"""
        
        for mission in mission_breakdown:
            html += f"""
            <div class="model-card">
                <h4>{mission['mission']}</h4>
                <div class="model-stats">
                    <div class="model-stat">
                        <strong>Attempts:</strong> {mission['attempts']}
                    </div>
                    <div class="model-stat">
                        <strong>Completions:</strong> {mission['completions']}
                    </div>
                    <div class="model-stat">
                        <strong>Success Rate:</strong> {mission['success_rate']:.1f}%
                    </div>
                    <div class="model-stat">
                        <strong>Unique Users:</strong> {mission['unique_users']}
                    </div>
                </div>
                <div class="progress-bar" style="margin-top: 15px;">
                    <div class="progress-fill" style="width: {mission['success_rate']}%">
                        {mission['success_rate']:.0f}% Success
                    </div>
                </div>
"""
            
            # Show participants who completed this mission
            mission_chats = [c for c in analyzer.mission_chats if c['mission_info']['mission_id'] == mission['mission']]
            completed_chats = [c for c in mission_chats if c['completed']]
            
            if completed_chats:
                html += """
                <div style="margin-top: 20px; padding-top: 15px; border-top: 2px solid #e5e7eb;">
                    <h5 style="color: #667eea; margin-bottom: 10px;">✓ Successful Completions:</h5>
"""
                for chat in completed_chats:
                    user_name = analyzer.get_user_name(chat['user_id'])
                    html += f"""
                    <div style="background: white; padding: 15px; margin: 10px 0; border-radius: 8px; border-left: 4px solid #10b981;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                            <strong style="color: #10b981;">✓ {user_name}</strong>
                            <span style="color: #666; font-size: 0.9em;">{chat['message_count']} messages</span>
                        </div>
                        <div style="font-size: 0.9em; color: #666;">
                            <strong>Chat:</strong> {chat['title']}
                        </div>
"""
                    # Show first few messages
                    if chat['messages']:
                        html += '<div style="margin-top: 10px;"><strong style="font-size: 0.9em;">Conversation Preview:</strong></div>'
                        for i, msg in enumerate(chat['messages'][:4], 1):
                            role = msg.get('role', 'unknown')
                            content = msg.get('content', '')[:150]
                            if len(msg.get('content', '')) > 150:
                                content += '...'
                            
                            bg_color = '#e0e7ff' if role == 'user' else '#f3f4f6'
                            html += f"""
                            <div style="background: {bg_color}; padding: 8px; margin: 5px 0; border-radius: 5px; font-size: 0.85em;">
                                <strong>{role.title()}:</strong> {content}
                            </div>
"""
                        if len(chat['messages']) > 4:
                            html += f'<div style="font-size: 0.85em; color: #999; margin-top: 5px;">... and {len(chat["messages"]) - 4} more messages</div>'
                    
                    html += """
                    </div>
"""
                html += """
                </div>
"""
            
            html += """
            </div>
"""
        
        html += """
            </div>
"""
    else:
        html += """
            <div class="no-data">
                <h2>No Mission Data Yet</h2>
                <p>Once employees start attempting missions, detailed statistics will appear here.</p>
            </div>
"""
    
    html += """
        </div>
"""
    
    # Models Tab
    html += """
        <div id="models" class="tab-content">
            <div class="section">
                <h2 class="section-title">🤖 Model Usage Statistics</h2>
"""
    
    for model, stats in sorted(model_stats.items(), key=lambda x: x[1]['total'], reverse=True):
        mission_pct = (stats['mission'] / stats['total'] * 100) if stats['total'] > 0 else 0
        
        html += f"""
                <div class="model-card">
                    <h4><code>{model}</code></h4>
                    <div class="model-stats">
                        <div class="model-stat">
                            <strong>Total Chats:</strong> {stats['total']}
                        </div>
                        <div class="model-stat">
                            <strong>Mission Chats:</strong> {stats['mission']}
                        </div>
                        <div class="model-stat">
                            <strong>Completed Missions:</strong> {stats['completed']}
                        </div>
                        <div class="model-stat">
                            <strong>Mission %:</strong> {mission_pct:.1f}%
                        </div>
                    </div>
                </div>
"""
    
    html += """
            </div>
        </div>
"""
    
    # JavaScript
    html += """
        <script>
            function showTab(tabName) {
                // Hide all tab contents
                document.querySelectorAll('.tab-content').forEach(tab => {
                    tab.classList.remove('active');
                });
                
                // Remove active class from all tabs
                document.querySelectorAll('.tab').forEach(tab => {
                    tab.classList.remove('active');
                });
                
                // Show selected tab
                document.getElementById(tabName).classList.add('active');
                
                // Add active class to clicked tab
                event.target.classList.add('active');
            }
            
            function toggleDetails(chatNum) {
                const detailsRow = document.getElementById('details-' + chatNum);
                const details = detailsRow.querySelector('.chat-details');
                details.classList.toggle('show');
            }
            
            function filterChats() {
                const searchValue = document.getElementById('searchInput').value.toLowerCase();
                const typeFilter = document.getElementById('typeFilter').value;
                const rows = document.querySelectorAll('.chat-row');
                
                rows.forEach(row => {
                    const text = row.textContent.toLowerCase();
                    const type = row.getAttribute('data-type');
                    const completed = row.getAttribute('data-completed');
                    
                    let showBySearch = searchValue === '' || text.includes(searchValue);
                    let showByType = true;
                    
                    if (typeFilter === 'mission') {
                        showByType = type === 'mission';
                    } else if (typeFilter === 'regular') {
                        showByType = type === 'regular';
                    } else if (typeFilter === 'completed') {
                        showByType = type === 'mission' && completed === 'true';
                    }
                    
                    if (showBySearch && showByType) {
                        row.style.display = '';
                        row.nextElementSibling.style.display = '';
                    } else {
                        row.style.display = 'none';
                        row.nextElementSibling.style.display = 'none';
                    }
                });
            }
            
            function resetFilters() {
                document.getElementById('searchInput').value = '';
                document.getElementById('typeFilter').value = 'all';
                filterChats();
            }
        </script>
    </div>
</body>
</html>
"""
    
    # Write to file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"Enhanced dashboard generated: {output_path}")
    return str(output_path)


if __name__ == '__main__':
    # Find latest export
    latest_file = find_latest_export()
    
    if not latest_file:
        print("No export files found!")
        exit(1)
    
    print(f"Generating enhanced dashboard from: {latest_file}\n")
    
    # Analyze
    analyzer = MissionAnalyzer(latest_file)
    analyzer.analyze_missions()
    
    # Generate dashboard
    dashboard_file = generate_enhanced_dashboard(analyzer)
    
    print(f"\nEnhanced dashboard ready: {dashboard_file}")
    print("Open it in your browser to view all chats!")
