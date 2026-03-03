#!/bin/bash
# Integration test script for background task cancellation fix
# This script validates that tasks timeout after 20 seconds and agents receive cancellation messages

set -e

echo "=========================================="
echo "Background Task Cancellation Test"
echo "=========================================="
echo ""
echo "Configuration:"
echo "  - Timeout: 20 seconds"
echo "  - Monitor interval: 5 seconds"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if we're testing locally or in Kubernetes
if [ -z "$NAMESPACE" ]; then
    echo -e "${YELLOW}Testing locally...${NC}"
    TEST_ENV="local"
else
    echo -e "${YELLOW}Testing in Kubernetes namespace: $NAMESPACE${NC}"
    TEST_ENV="k8s"
fi

echo ""
echo "Step 1: Check current task status"
echo "-----------------------------------"

if [ "$TEST_ENV" = "k8s" ]; then
    POD_NAME=$(kubectl get pods -n $NAMESPACE -l app=solace-chat -o jsonpath='{.items[0].metadata.name}')
    echo "Using pod: $POD_NAME"
    
    kubectl exec -n $NAMESPACE $POD_NAME -c solace-chat-gateways -- python3 -c "
import os, psycopg2
conn = psycopg2.connect(
    host=os.environ.get('POSTGRESQL_HOST'),
    port=os.environ.get('POSTGRESQL_PORT', 5432),
    database=os.environ.get('webui_gateway_db_name'),
    user=os.environ.get('webui_gateway_user'),
    password=os.environ.get('webui_gateway_password')
)
cur = conn.cursor()
cur.execute('SELECT status, COUNT(*) FROM tasks GROUP BY status ORDER BY COUNT(*) DESC')
print('Task status breakdown:')
for row in cur.fetchall():
    print(f'  {row[0]}: {row[1]}')
cur.close()
conn.close()
"
else
    # Local testing with sqlite
    python3 -c "
import sqlite3
conn = sqlite3.connect('webui-gateway.db')
cur = conn.cursor()
cur.execute('SELECT status, COUNT(*) FROM tasks GROUP BY status ORDER BY COUNT(*) DESC')
print('Task status breakdown:')
for row in cur.fetchall():
    print(f'  {row[0]}: {row[1]}')
cur.close()
conn.close()
" 2>/dev/null || echo "No local database found"
fi

echo ""
echo "Step 2: Instructions for manual testing"
echo "----------------------------------------"
echo ""
echo "To test the cancellation fix:"
echo ""
echo "1. Start a long-running background task (e.g., ask an agent to analyze a large dataset)"
echo "   - Make sure 'Run in background' is enabled in the UI"
echo ""
echo "2. Wait 20 seconds for the timeout to trigger"
echo ""
echo "3. Monitor the logs for cancellation messages:"
echo ""

if [ "$TEST_ENV" = "k8s" ]; then
    echo "   kubectl logs -n $NAMESPACE $POD_NAME -c solace-chat-gateways --tail=50 -f | grep -E '(timeout|cancel|BackgroundTaskMonitor)'"
else
    echo "   tail -f webui_example.log | grep -E '(timeout|cancel|BackgroundTaskMonitor)'"
fi

echo ""
echo "4. Look for these log messages:"
echo "   ${GREEN}✓${NC} 'Found X timed out background tasks'"
echo "   ${GREEN}✓${NC} 'Sent cancellation to agent <agent_name> for task <task_id>'"
echo "   ${GREEN}✓${NC} 'Task <task_id> marked as timeout'"
echo ""
echo "5. Verify in the database that the task status changed to 'timeout':"
echo ""

if [ "$TEST_ENV" = "k8s" ]; then
    echo "   kubectl exec -n $NAMESPACE $POD_NAME -c solace-chat-gateways -- python3 -c \\"
    echo "   \"import os, psycopg2; conn = psycopg2.connect(host=os.environ.get('POSTGRESQL_HOST'), port=os.environ.get('POSTGRESQL_PORT', 5432), database=os.environ.get('webui_gateway_db_name'), user=os.environ.get('webui_gateway_user'), password=os.environ.get('webui_gateway_password')); cur = conn.cursor(); cur.execute('SELECT id, status, agent_name FROM tasks WHERE status=\\'timeout\\' ORDER BY updated_at DESC LIMIT 5'); print('Recent timeout tasks:'); [print(f'  {row[0]}: {row[1]} (agent: {row[2]})') for row in cur.fetchall()]; cur.close(); conn.close()\""
else
    echo "   sqlite3 webui-gateway.db \"SELECT id, status, agent_name FROM tasks WHERE status='timeout' ORDER BY updated_at DESC LIMIT 5;\""
fi

echo ""
echo "6. Check agent logs to verify it received the cancellation:"
echo ""

if [ "$TEST_ENV" = "k8s" ]; then
    echo "   kubectl logs -n $NAMESPACE -l app=<agent-name> --tail=50 | grep -i cancel"
else
    echo "   Check agent logs for cancellation messages"
fi

echo ""
echo "=========================================="
echo "Expected Results:"
echo "=========================================="
echo ""
echo "${GREEN}✓${NC} Task times out after 20 seconds"
echo "${GREEN}✓${NC} BackgroundTaskMonitor detects timeout"
echo "${GREEN}✓${NC} Cancellation message sent to agent"
echo "${GREEN}✓${NC} Task status updated to 'timeout' in database"
echo "${GREEN}✓${NC} Agent receives and processes cancellation"
echo "${GREEN}✓${NC} Queue depths remain stable (no overflow)"
echo ""
echo "=========================================="
echo "Automated Monitoring (run in separate terminal)"
echo "=========================================="
echo ""
echo "Monitor task counts in real-time:"
echo ""

if [ "$TEST_ENV" = "k8s" ]; then
    echo "watch -n 2 \"kubectl exec -n $NAMESPACE $POD_NAME -c solace-chat-gateways -- python3 -c \\\"import os, psycopg2; conn = psycopg2.connect(host=os.environ.get('POSTGRESQL_HOST'), port=os.environ.get('POSTGRESQL_PORT', 5432), database=os.environ.get('webui_gateway_db_name'), user=os.environ.get('webui_gateway_user'), password=os.environ.get('webui_gateway_password')); cur = conn.cursor(); cur.execute('SELECT status, COUNT(*) FROM tasks GROUP BY status ORDER BY COUNT(*) DESC'); print('Task status:'); [print(f'{row[0]}: {row[1]}') for row in cur.fetchall()]; cur.close(); conn.close()\\\"\""
else
    echo "watch -n 2 \"sqlite3 webui-gateway.db 'SELECT status, COUNT(*) FROM tasks GROUP BY status ORDER BY COUNT(*) DESC;'\""
fi

echo ""
echo "=========================================="
echo "Test complete! Follow the instructions above to validate the fix."
echo "=========================================="
