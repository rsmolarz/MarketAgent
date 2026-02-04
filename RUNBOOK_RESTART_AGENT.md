# Runbook: Restart Failed Agent

**Purpose**: Recover from a failed agent execution  
**Severity**: High  
**Estimated Time**: 10 minutes  
**Requires**: Terminal access, agent logs

---

## When to Use This Runbook

Use this when:
- A specific agent fails repeatedly
- Error logs show "Agent timeout" or "Agent crashed"
- Manual restart is needed
- Agent doesn't recover automatically

**Do NOT use if**: System has multiple agent failures (see System-Wide Failure runbook instead)

---

## Pre-Flight Checklist

- [ ] Identified which agent failed
- [ ] Have terminal access
- [ ] Application is running

---

### Step 1: Check Agent Status

```bash
# Check current agent status
curl -s http://localhost:5000/api/agents | python -m json.tool

# Look for the specific agent status
curl -s http://localhost:5000/api/agents/[agent_name]
```

**Status**: [ ] Running [ ] Stopped [ ] Error

---

### Step 2: Review Error Logs

```bash
# Find recent errors for this agent
grep "[agent_name]" /tmp/logs/Start_application_*.log | tail -20

# Check for specific error patterns
grep -i "error\|failed\|exception" /tmp/logs/Start_application_*.log | grep "[agent_name]" | tail -10
```

**Error Type**: [ ] API Error [ ] Database Error [ ] Timeout [ ] Code Error [ ] Unknown

---

### Step 3: Check Quarantine Status

```bash
# View quarantine status
cat meta_supervisor/quarantine_status.json

# If agent is quarantined, clear it
python3 << 'PYEOF'
import json
agent_name = "[agent_name]"
with open('meta_supervisor/quarantine_status.json', 'r') as f:
    status = json.load(f)
if agent_name in status:
    status[agent_name]['quarantined'] = False
    status[agent_name]['failure_count'] = 0
    with open('meta_supervisor/quarantine_status.json', 'w') as f:
        json.dump(status, f, indent=2)
    print(f"Cleared quarantine for {agent_name}")
else:
    print(f"{agent_name} not in quarantine")
PYEOF
```

**Status**: [ ] Not quarantined [ ] Quarantine cleared

---

### Step 4: Verify Database Connection

```bash
# Test database connectivity
curl -s http://localhost:5000/api/health | python -m json.tool
```

**Status**: [ ] Database connected [ ] Database error

---

### Step 5: Restart the Agent

```bash
# Stop the agent (if running)
curl -X POST http://localhost:5000/api/agents/[agent_name]/stop

# Wait for graceful shutdown
sleep 5

# Start the agent
curl -X POST http://localhost:5000/api/agents/[agent_name]/start

# Wait 10 seconds for startup
sleep 10

# Check restart status
grep "Started agent" /tmp/logs/Start_application_*.log | tail -3
```

**Confirm**: "Started agent [agent_name]" appears in logs

---

### Step 6: Verify Agent Execution

```bash
# Check agent health
curl -s http://localhost:5000/api/agents/[agent_name]

# Expected JSON response with status "healthy" or "running"
```

**Status**: [ ] Healthy [ ] Still failing [ ] Timeout

---

### Step 7: Monitor for 5 Minutes

```bash
# Watch logs for errors
tail -f /tmp/logs/Start_application_*.log | grep -i "[agent_name]\|error"

# Press Ctrl+C after 5 minutes
```

**Check**: Any new errors appearing?

---

## Success Criteria

✅ Agent restarted successfully  
✅ No errors in logs for 5 minutes  
✅ Agent execution completed  
✅ Data persisted to database

---

## Rollback (If Restart Fails)

If agent still fails after restart:

```bash
# Check last successful execution
grep "SUCCESS" /tmp/logs/Start_application_*.log | grep "[agent_name]" | tail -1

# Review agent code for recent changes
git log --oneline agents/[agent_name].py | head -5

# If database corruption suspected:
# Contact admin for database rollback

# Contact: @rsmolarz for persistent failures
```

---

## System Agents (Always Run)

These agents bypass regime rotation and should always be running:
- **CodeGuardianAgent** - Code quality monitoring
- **HealthCheckAgent** - System health checks
- **MetaSupervisorAgent** - Agent supervision

If any of these fail, escalate immediately.

---

## Documentation

**Executed by**: ________________  
**Date/Time**: ________________  
**Agent**: ________________  
**Result**: [ ] Success [ ] Partial [ ] Failed  
**Notes**:

---

## Related Runbooks

- System-Wide Failure Recovery
- Database Recovery from Backup
- Performance Degradation Diagnosis
