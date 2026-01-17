#\!/bin/bash
WORKER_ID=$1
CUISINE=$2
TARGET=$3
QUERIES=$4

WORKER_SESSION="ingestion-worker-$WORKER_ID"
INGESTION_DIR="/Users/ramiz/ekitchen/ekitchen-ingestion"

# Kill existing worker session if running
if tmux has-session -t $WORKER_SESSION 2>/dev/null; then
  tmux kill-session -t $WORKER_SESSION
fi

# Create new worker session
tmux new-session -d -s $WORKER_SESSION

# Setup environment
tmux send-keys -t $WORKER_SESSION:0 "cd $INGESTION_DIR" Enter
tmux send-keys -t $WORKER_SESSION:0 "clear" Enter

# Start Claude and wait for it to be ready
echo "🤖 Starting Claude in worker $WORKER_ID session..."
tmux send-keys -t $WORKER_SESSION:0 "claude" Enter
sleep 3

# Launch worker with session verification instructions
tmux send-keys -t $WORKER_SESSION:0 "echo '⚙️ INGESTION WORKER $WORKER_ID STARTING...'" Enter
tmux send-keys -t $WORKER_SESSION:0 "echo ''" Enter
tmux send-keys -t $WORKER_SESSION:0 "echo '🔍 CRITICAL: Worker must discover boss session name before communication\!'" Enter
tmux send-keys -t $WORKER_SESSION:0 "echo '✅ Worker session: $WORKER_SESSION'" Enter
tmux send-keys -t $WORKER_SESSION:0 "echo ''" Enter
tmux send-keys -t $WORKER_SESSION:0 "echo '📋 Instructions: Follow .ai/orchestrator/ingestion-worker-agent.md exactly'" Enter
tmux send-keys -t $WORKER_SESSION:0 "echo '📖 Pipeline: Follow revised-recipe-ingestion-orchestration.md precisely'" Enter
tmux send-keys -t $WORKER_SESSION:0 "echo '🎯 STEP 1: Run session discovery to find boss before any communication\!'" Enter
tmux send-keys -t $WORKER_SESSION:0 "echo ''" Enter
tmux send-keys -t $WORKER_SESSION:0 "echo '🚀 Worker $WORKER_ID: Begin with session discovery, then autonomous operation\!'" Enter

echo "✅ Worker $WORKER_ID spawned: $CUISINE cuisine, target $TARGET recipes"
