#!/usr/bin/env python3
"""
Enhanced tmux utilities for autonomous agent monitoring and management.
Integrates with the existing framework to provide programmatic monitoring capabilities.
"""

import subprocess
import json
import time
import re
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

@dataclass
class AgentStatus:
    """Represents the status of an autonomous agent."""
    session_name: str
    window_index: int
    window_name: str
    is_active: bool
    last_activity: str
    content_preview: str
    agent_type: str  # orchestrator, pm, engineer
    feature_name: Optional[str] = None
    issue_number: Optional[str] = None
    estimated_health: str = "unknown"  # healthy, stuck, unresponsive, error

@dataclass
class SystemSnapshot:
    """Complete system monitoring snapshot for Claude analysis."""
    timestamp: str
    total_sessions: int
    orchestrator_status: Optional[AgentStatus]
    pm_agents: List[AgentStatus]
    engineer_agents: List[AgentStatus]
    resource_utilization: Dict[str, Any]
    recent_activity: List[str]
    potential_issues: List[str]

class TmuxUtils:
    """Enhanced tmux utilities for autonomous agent monitoring."""
    
    def __init__(self, max_engineers: int = 3):
        self.max_engineers = max_engineers
        self.session_patterns = {
            'orchestrator': r'^orchestrator$',
            'pm': r'^pm-([a-zA-Z0-9-]+)$',
            'engineer': r'^eng-([a-zA-Z0-9-]+)-(\d+)$'
        }
    
    def get_all_sessions(self) -> List[Dict[str, str]]:
        """Get all tmux sessions with basic info."""
        try:
            result = subprocess.run(
                ['tmux', 'list-sessions', '-F', '#{session_name}:#{?session_attached,attached,not_attached}'],
                capture_output=True, text=True, check=True
            )
            sessions = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = line.split(':')
                    if len(parts) >= 2:
                        sessions.append({
                            'name': parts[0],
                            'attached': parts[1] == 'attached'
                        })
            return sessions
        except subprocess.CalledProcessError:
            return []
    
    def get_window_content(self, session_name: str, window_index: int = 0, num_lines: int = 50) -> str:
        """Capture content from a specific tmux window."""
        try:
            result = subprocess.run(
                ['tmux', 'capture-pane', '-t', f'{session_name}:{window_index}', '-p'],
                capture_output=True, text=True, check=True
            )
            lines = result.stdout.strip().split('\n')
            # Return last num_lines
            return '\n'.join(lines[-num_lines:]) if lines else ""
        except subprocess.CalledProcessError as e:
            return f"Error capturing content: {e}"
    
    def get_window_info(self, session_name: str, window_index: int = 0) -> Dict[str, Any]:
        """Get detailed window information."""
        try:
            result = subprocess.run([
                'tmux', 'list-windows', '-t', session_name, '-F',
                '#{window_index}:#{window_name}:#{?window_active,active,inactive}:#{window_last_flag}'
            ], capture_output=True, text=True, check=True)
            
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = line.split(':')
                    if len(parts) >= 3 and parts[0] == str(window_index):
                        return {
                            'index': int(parts[0]),
                            'name': parts[1],
                            'active': parts[2] == 'active',
                            'last_activity': parts[3] if len(parts) > 3 else 'unknown'
                        }
            return {'index': window_index, 'name': 'unknown', 'active': False, 'last_activity': 'unknown'}
        except subprocess.CalledProcessError:
            return {'index': window_index, 'name': 'unknown', 'active': False, 'last_activity': 'unknown'}
    
    def analyze_agent_health(self, content: str, agent_type: str) -> str:
        """Analyze agent health based on terminal content."""
        if not content or len(content.strip()) < 10:
            return "unresponsive"
        
        # Look for error indicators
        error_patterns = [
            r'error|Error|ERROR',
            r'failed|Failed|FAILED',
            r'exception|Exception|EXCEPTION',
            r'traceback|Traceback|TRACEBACK'
        ]
        
        for pattern in error_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return "error"
        
        # Look for activity indicators
        activity_patterns = [
            r'claude>',  # Claude prompt
            r'Reading|Writing|Implementing|Testing',
            r'Status update|Progress|Complete',
            r'Issue #\d+',
            r'tmux send-keys'
        ]
        
        recent_activity = False
        for pattern in activity_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                recent_activity = True
                break
        
        # Look for stuck indicators
        stuck_patterns = [
            r'waiting|Waiting|WAITING',
            r'timeout|Timeout|TIMEOUT',
            r'hanging|Hanging|HANGING'
        ]
        
        for pattern in stuck_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return "stuck"
        
        return "healthy" if recent_activity else "unresponsive"
    
    def classify_session(self, session_name: str) -> Dict[str, Optional[str]]:
        """Classify session type and extract metadata."""
        for agent_type, pattern in self.session_patterns.items():
            match = re.match(pattern, session_name)
            if match:
                result = {'type': agent_type, 'feature': None, 'issue': None}
                if agent_type == 'pm' and match.groups():
                    result['feature'] = match.group(1)
                elif agent_type == 'engineer' and len(match.groups()) >= 2:
                    result['feature'] = match.group(1)
                    result['issue'] = match.group(2)
                return result
        return {'type': 'unknown', 'feature': None, 'issue': None}
    
    def get_agent_status(self, session_name: str, window_index: int = 0) -> AgentStatus:
        """Get comprehensive status for a single agent."""
        window_info = self.get_window_info(session_name, window_index)
        content = self.get_window_content(session_name, window_index, 20)
        classification = self.classify_session(session_name)
        
        agent_status = AgentStatus(
            session_name=session_name,
            window_index=window_index,
            window_name=window_info.get('name', 'unknown'),
            is_active=window_info.get('active', False),
            last_activity=window_info.get('last_activity', 'unknown'),
            content_preview=content[-500:] if content else "",  # Last 500 chars
            agent_type=classification['type'],
            feature_name=classification['feature'],
            issue_number=classification['issue'],
            estimated_health=self.analyze_agent_health(content, classification['type'])
        )
        
        return agent_status
    
    def get_all_agent_statuses(self) -> List[AgentStatus]:
        """Get status for all autonomous agents."""
        sessions = self.get_all_sessions()
        agent_statuses = []
        
        for session in sessions:
            # Only monitor our autonomous agent sessions
            classification = self.classify_session(session['name'])
            if classification['type'] != 'unknown':
                status = self.get_agent_status(session['name'])
                agent_statuses.append(status)
        
        return agent_statuses
    
    def create_monitoring_snapshot(self) -> SystemSnapshot:
        """Create comprehensive monitoring snapshot for Claude analysis."""
        all_agents = self.get_all_agent_statuses()
        
        # Categorize agents
        orchestrator = None
        pm_agents = []
        engineer_agents = []
        
        for agent in all_agents:
            if agent.agent_type == 'orchestrator':
                orchestrator = agent
            elif agent.agent_type == 'pm':
                pm_agents.append(agent)
            elif agent.agent_type == 'engineer':
                engineer_agents.append(agent)
        
        # Calculate resource utilization
        active_engineers = len([e for e in engineer_agents if e.estimated_health in ['healthy', 'stuck']])
        resource_utilization = {
            'engineers_active': active_engineers,
            'engineers_max': self.max_engineers,
            'utilization_percentage': (active_engineers / self.max_engineers) * 100,
            'pm_agents_active': len([p for p in pm_agents if p.estimated_health in ['healthy', 'stuck']]),
            'orchestrator_active': orchestrator is not None and orchestrator.estimated_health in ['healthy', 'stuck']
        }
        
        # Identify recent activity
        recent_activity = []
        for agent in all_agents:
            if agent.estimated_health == 'healthy':
                if agent.agent_type == 'engineer':
                    recent_activity.append(f"Engineer {agent.session_name}: Working on issue #{agent.issue_number}")
                elif agent.agent_type == 'pm':
                    recent_activity.append(f"PM {agent.feature_name}: Managing {len([e for e in engineer_agents if e.feature_name == agent.feature_name])} engineers")
                elif agent.agent_type == 'orchestrator':
                    recent_activity.append("Orchestrator: Coordinating autonomous development")
        
        # Identify potential issues
        potential_issues = []
        for agent in all_agents:
            if agent.estimated_health == 'error':
                potential_issues.append(f"Agent {agent.session_name} in error state")
            elif agent.estimated_health == 'unresponsive':
                potential_issues.append(f"Agent {agent.session_name} appears unresponsive")
            elif agent.estimated_health == 'stuck':
                potential_issues.append(f"Agent {agent.session_name} may be stuck")
        
        if active_engineers == 0 and len(pm_agents) > 0:
            potential_issues.append("PM agents active but no engineers working")
        
        if active_engineers > 0 and orchestrator is None:
            potential_issues.append("Engineers active but no orchestrator coordination")
        
        return SystemSnapshot(
            timestamp=datetime.now().isoformat(),
            total_sessions=len(all_agents),
            orchestrator_status=orchestrator,
            pm_agents=pm_agents,
            engineer_agents=engineer_agents,
            resource_utilization=resource_utilization,
            recent_activity=recent_activity,
            potential_issues=potential_issues
        )
    
    def send_safe_message(self, target: str, message: str, confirmation: bool = True) -> bool:
        """Send message to tmux session with safety confirmation."""
        if confirmation:
            response = input(f"Send message to {target}? (y/N): ")
            if response.lower() != 'y':
                print("Message cancelled.")
                return False
        
        try:
            subprocess.run([
                'tmux', 'send-keys', '-t', target, message
            ], check=True)
            
            time.sleep(0.5)
            
            subprocess.run([
                'tmux', 'send-keys', '-t', target, 'Enter'
            ], check=True)
            
            print(f"Message sent to {target}: {message}")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"Error sending message: {e}")
            return False
    
    def find_sessions_by_pattern(self, pattern: str) -> List[str]:
        """Find session names matching a pattern."""
        sessions = self.get_all_sessions()
        matching = []
        
        for session in sessions:
            if re.search(pattern, session['name'], re.IGNORECASE):
                matching.append(session['name'])
        
        return matching
    
    def kill_unresponsive_agents(self, dry_run: bool = True) -> List[str]:
        """Kill agents that appear unresponsive."""
        all_agents = self.get_all_agent_statuses()
        unresponsive = [a for a in all_agents if a.estimated_health == 'unresponsive']
        
        killed_sessions = []
        
        for agent in unresponsive:
            print(f"Found unresponsive agent: {agent.session_name}")
            
            if not dry_run:
                try:
                    subprocess.run([
                        'tmux', 'kill-session', '-t', agent.session_name
                    ], check=True)
                    killed_sessions.append(agent.session_name)
                    print(f"Killed session: {agent.session_name}")
                except subprocess.CalledProcessError as e:
                    print(f"Error killing session {agent.session_name}: {e}")
            else:
                print(f"DRY RUN: Would kill {agent.session_name}")
        
        return killed_sessions
    
    def generate_claude_analysis_prompt(self) -> str:
        """Generate a comprehensive prompt for Claude to analyze system state."""
        snapshot = self.create_monitoring_snapshot()
        
        prompt = f"""## Autonomous Development System Monitoring Report

**Generated**: {snapshot.timestamp}
**Total Active Sessions**: {snapshot.total_sessions}

### System Resource Status
- **Engineers Active**: {snapshot.resource_utilization['engineers_active']}/{snapshot.resource_utilization['engineers_max']} ({snapshot.resource_utilization['utilization_percentage']:.1f}% utilization)
- **PM Agents Active**: {snapshot.resource_utilization['pm_agents_active']}
- **Orchestrator Active**: {snapshot.resource_utilization['orchestrator_active']}

### Orchestrator Status
"""
        
        if snapshot.orchestrator_status:
            prompt += f"- **Session**: {snapshot.orchestrator_status.session_name}\n"
            prompt += f"- **Health**: {snapshot.orchestrator_status.estimated_health}\n"
            prompt += f"- **Recent Activity**: {snapshot.orchestrator_status.content_preview[-100:] if snapshot.orchestrator_status.content_preview else 'No content'}\n"
        else:
            prompt += "- **Status**: No orchestrator agent active\n"
        
        prompt += "\n### PM Agents Status\n"
        if snapshot.pm_agents:
            for pm in snapshot.pm_agents:
                prompt += f"- **{pm.feature_name}** ({pm.session_name}): {pm.estimated_health}\n"
                if pm.content_preview:
                    prompt += f"  - Recent: {pm.content_preview[-100:]}\n"
        else:
            prompt += "- No PM agents active\n"
        
        prompt += "\n### Engineer Agents Status\n"
        if snapshot.engineer_agents:
            for eng in snapshot.engineer_agents:
                prompt += f"- **Issue #{eng.issue_number}** in {eng.feature_name} ({eng.session_name}): {eng.estimated_health}\n"
                if eng.content_preview:
                    prompt += f"  - Recent: {eng.content_preview[-100:]}\n"
        else:
            prompt += "- No engineer agents active\n"
        
        prompt += "\n### Recent Activity\n"
        if snapshot.recent_activity:
            for activity in snapshot.recent_activity:
                prompt += f"- {activity}\n"
        else:
            prompt += "- No recent activity detected\n"
        
        prompt += "\n### Potential Issues\n"
        if snapshot.potential_issues:
            for issue in snapshot.potential_issues:
                prompt += f"- ⚠️ {issue}\n"
        else:
            prompt += "- ✅ No issues detected\n"
        
        prompt += f"""
### Action Recommendations
Based on this monitoring data, please:
1. Assess the overall health of the autonomous development system
2. Identify any agents that need attention or restart
3. Recommend resource reallocation if needed
4. Suggest next steps for maintaining development momentum
5. Highlight any coordination issues between agents

**Raw Monitoring Data** (for detailed analysis):
```json
{json.dumps(asdict(snapshot), indent=2)}
```
"""
        
        return prompt


def main():
    """CLI interface for tmux utilities."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Enhanced tmux utilities for autonomous agent monitoring')
    parser.add_argument('--snapshot', action='store_true', help='Create monitoring snapshot')
    parser.add_argument('--status', type=str, help='Get status for specific session')
    parser.add_argument('--health-check', action='store_true', help='Check health of all agents')
    parser.add_argument('--claude-prompt', action='store_true', help='Generate Claude analysis prompt')
    parser.add_argument('--kill-unresponsive', action='store_true', help='Kill unresponsive agents')
    parser.add_argument('--dry-run', action='store_true', help='Dry run mode (no actual changes)')
    parser.add_argument('--find', type=str, help='Find sessions by pattern')
    parser.add_argument('--send', nargs=2, metavar=('TARGET', 'MESSAGE'), help='Send message to session')
    
    args = parser.parse_args()
    utils = TmuxUtils()
    
    if args.snapshot:
        snapshot = utils.create_monitoring_snapshot()
        print(json.dumps(asdict(snapshot), indent=2))
    
    elif args.status:
        status = utils.get_agent_status(args.status)
        print(json.dumps(asdict(status), indent=2))
    
    elif args.health_check:
        agents = utils.get_all_agent_statuses()
        print("Agent Health Check:")
        for agent in agents:
            print(f"  {agent.session_name}: {agent.estimated_health}")
    
    elif args.claude_prompt:
        prompt = utils.generate_claude_analysis_prompt()
        print(prompt)
    
    elif args.kill_unresponsive:
        killed = utils.kill_unresponsive_agents(dry_run=args.dry_run)
        if killed:
            print(f"Killed sessions: {', '.join(killed)}")
        else:
            print("No unresponsive sessions found" if not args.dry_run else "No sessions would be killed")
    
    elif args.find:
        sessions = utils.find_sessions_by_pattern(args.find)
        print(f"Found sessions: {', '.join(sessions) if sessions else 'None'}")
    
    elif args.send:
        target, message = args.send
        utils.send_safe_message(target, message, confirmation=not args.dry_run)
    
    else:
        # Default: show basic status
        agents = utils.get_all_agent_statuses()
        print(f"Total autonomous agents: {len(agents)}")
        for agent in agents:
            print(f"  {agent.session_name} ({agent.agent_type}): {agent.estimated_health}")


if __name__ == '__main__':
    main()