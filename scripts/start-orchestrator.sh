#!/bin/bash

# Start Orchestrator for Autonomous Development
# Usage: ./start-orchestrator.sh [session-name]

SESSION_NAME=${1:-"orchestrator"}

# Check if tmux session already exists
if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    echo "Orchestrator session '$SESSION_NAME' already exists."
    echo "Attaching to existing session..."
    tmux attach-session -t "$SESSION_NAME"
else
    echo "Starting new Orchestrator session: $SESSION_NAME"
    
    # Create new tmux session for orchestrator
    tmux new-session -d -s "$SESSION_NAME"
    
    # Start Claude in the orchestrator session
    tmux send-keys -t "$SESSION_NAME:0" 'claude' Enter
    
    # Wait for Claude to start
    sleep 2
    
    # Send initial briefing to orchestrator
    tmux send-keys -t "$SESSION_NAME:0" "You are the Orchestrator Agent. Read /orchestrator command documentation to understand your role. You coordinate autonomous development by spawning PM agents for features and Engineer agents for issues. Start by reading PROJECT_CONTEXT.md to understand the application, then await user commands for autonomous development." Enter
    
    echo "Orchestrator started in session: $SESSION_NAME"
    echo "Attaching to session..."
    
    # Attach to the session
    tmux attach-session -t "$SESSION_NAME"
fi