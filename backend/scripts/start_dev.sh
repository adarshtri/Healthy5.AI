#!/bin/bash

# This script helps boot the entire Event-Driven backend for local testing.
# It assumes Redis is already running on the system (via Docker or brew services).

echo "🚀 Starting Healthy5.AI Backend Services..."

# Ensure we are in the backend directory
cd "$(dirname "$0")/.."

# Activate virtual environment
source venv/bin/activate

# Function to handle cleanup on Ctrl+C
cleanup() {
    echo "🛑 Shutting down services..."
    kill $(jobs -p) 2>/dev/null
    exit
}

trap cleanup SIGINT SIGTERM

# Fix for macOS Python Forking issues (e.g. objc[...]: +[NSMutableString initialize]...)
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES

echo "----------------------------------------"
echo "📦 Starting API Gateway (Port 8000)..."
uvicorn src.gateway.main:app --host 0.0.0.0 --port 8000 &
GATEWAY_PID=$!

echo "🧠 Starting Agent Worker (Listening to 'incoming_messages')..."
# Set higher timeout if generation takes long
rq worker incoming_messages --name agent_worker &
AGENT_PID=$!

echo "✉️ Starting Egress Worker (Listening to 'outgoing_messages')..."
rq worker outgoing_messages --name egress_worker &
EGRESS_PID=$!

echo "----------------------------------------"
echo "✅ All services running in background."
echo "Press Ctrl+C to stop all services."
echo ""
echo "Logs will appear below:"
echo "----------------------------------------"

# Wait for all background processes
wait
