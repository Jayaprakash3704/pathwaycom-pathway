# 🔧 Practical Guide: Running the System with Real Data

This guide shows you how to use the system to detect and respond to **real errors** in production-like environments.

---

## 📋 Table of Contents

1. [Quick Start (Demo Mode)](#quick-start-demo-mode)
2. [Connect to Real Log Sources](#connect-to-real-log-sources)
3. [Integrate with Real Systems](#integrate-with-real-systems)
4. [Common Real-World Scenarios](#common-real-world-scenarios)
5. [Troubleshooting Real Issues](#troubleshooting-real-issues)
6. [Production Deployment](#production-deployment)

---

## Quick Start (Demo Mode)

### Step 1: Basic Setup (2 minutes)

```bash
# Clone and setup
git clone https://github.com/Jayaprakash3704/pathwaycom-pathway.git
cd pathwaycom-pathway

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your GROQ_API_KEY or OPENAI_API_KEY
```

### Step 2: Run Demo Mode (60 seconds)

```bash
python main.py
```

**What happens**:
- Simulated logs stream at 5 logs/second
- Anomalies are injected randomly
- Agents detect, analyze, and respond
- You'll see output like:

```
[LOG] 2025-12-26T10:30:01Z - api-gateway - INFO - Request processed
[LOG] 2025-12-26T10:30:02Z - auth-service - ERROR - Authentication failed
[LOG] 2025-12-26T10:30:03Z - auth-service - ERROR - Authentication failed
[CRITICAL] ANOMALY DETECTED: error_spike in auth-service
[REASONING] Root cause: Database connection pool exhaustion
[ACTION] Executing: restart_service → SUCCESS
```

**Stop with**: Ctrl+C

---

## Connect to Real Log Sources

### Option 1: File Tailing (Production Logs)

**Use Case**: Monitor existing log files from running services

```python
# pipelines/log_stream.py

import pathway as pw
import json
from pathlib import Path

def create_file_log_stream(log_file_path: str):
    """
    Tail a log file (like 'tail -f')
    """
    
    # Read from file with streaming mode
    logs = pw.io.fs.read(
        path=log_file_path,
        format="json",
        mode="streaming",  # Continuously watch for new lines
        autocommit_duration_ms=100,
    )
    
    # Transform to our schema
    enriched = logs.select(
        timestamp=pw.this.timestamp,
        level=pw.this.level,
        service=pw.this.service,
        message=pw.this.message,
        source="file"
    )
    
    return enriched

# Usage:
# log_stream = create_file_log_stream("/var/log/my-service/app.log")
```

**Test with real logs**:

```bash
# 1. Point to your actual log file
# Edit pipelines/log_stream.py to use file reader

# 2. Make sure your log file outputs JSON format like:
# {"timestamp": "2025-12-26T10:30:00Z", "level": "ERROR", "service": "auth-service", "message": "Connection failed"}

# 3. Run the system
python main.py
```

### Option 2: HTTP/REST Endpoint (Push Logs)

**Use Case**: Applications send logs via HTTP POST

```python
# pipelines/log_stream.py

import pathway as pw

def create_http_log_stream(host: str = "0.0.0.0", port: int = 8888):
    """
    Accept logs via HTTP POST
    """
    
    # Define schema
    schema = pw.schema_builder(
        columns={
            "timestamp": pw.column_definition(dtype=str),
            "level": pw.column_definition(dtype=str),
            "service": pw.column_definition(dtype=str),
            "message": pw.column_definition(dtype=str),
        }
    )
    
    # Create HTTP connector
    logs = pw.io.http.rest_connector(
        host=host,
        port=port,
        schema=schema,
        delete_completed_queries=True,
    )
    
    return logs

# Usage:
# log_stream = create_http_log_stream(host="0.0.0.0", port=8888)
```

**Send logs from your application**:

```bash
# Python app
import requests
import json

log_entry = {
    "timestamp": "2025-12-26T10:30:00Z",
    "level": "ERROR",
    "service": "payment-service",
    "message": "Payment gateway timeout after 5s"
}

requests.post("http://localhost:8888", json=log_entry)
```

### Option 3: Kafka Consumer (Real-Time Stream)

**Use Case**: Consume from existing Kafka topics

```python
# pipelines/log_stream.py

import pathway as pw

def create_kafka_log_stream(
    bootstrap_servers: str = "localhost:9092",
    topic: str = "application-logs"
):
    """
    Consume logs from Kafka
    """
    
    logs = pw.io.kafka.read(
        rdkafka_settings={
            "bootstrap.servers": bootstrap_servers,
            "group.id": "pathway-incident-response",
            "auto.offset.reset": "latest",
        },
        topic=topic,
        format="json",
        autocommit_duration_ms=1000,
    )
    
    return logs

# Usage:
# log_stream = create_kafka_log_stream(
#     bootstrap_servers="kafka.production.com:9092",
#     topic="prod-logs"
# )
```

**Producer side** (your applications):

```python
# Your app sends logs to Kafka
from kafka import KafkaProducer
import json

producer = KafkaProducer(
    bootstrap_servers=['localhost:9092'],
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

log_entry = {
    "timestamp": "2025-12-26T10:30:00Z",
    "level": "ERROR",
    "service": "auth-service",
    "message": "Redis connection failed"
}

producer.send('application-logs', log_entry)
```

### Option 4: Database Polling (Existing Log Tables)

**Use Case**: Poll logs from PostgreSQL/MySQL

```python
# pipelines/log_stream.py

import pathway as pw

def create_database_log_stream(
    connection_string: str = "postgresql://user:pass@localhost:5432/logs_db"
):
    """
    Poll logs from database table
    """
    
    logs = pw.io.postgres.read(
        connection_string=connection_string,
        table_name="application_logs",
        autocommit_duration_ms=5000,  # Poll every 5 seconds
    )
    
    return logs

# Usage:
# log_stream = create_database_log_stream(
#     connection_string="postgresql://admin:secret@prod-db:5432/monitoring"
# )
```

---

## Integrate with Real Systems

### Real Action Executors

Replace simulated executors with actual integrations:

#### 1. PagerDuty Integration

```python
# agents/action_agent.py

import requests

class PagerDutyExecutor:
    def __init__(self, api_key: str, service_id: str):
        self.api_key = api_key
        self.service_id = service_id
        self.base_url = "https://api.pagerduty.com"
    
    def execute(self, incident_context: dict) -> dict:
        """Create PagerDuty incident"""
        
        payload = {
            "incident": {
                "type": "incident",
                "title": f"CRITICAL: {incident_context['anomaly_type']} in {incident_context['source']}",
                "service": {
                    "id": self.service_id,
                    "type": "service_reference"
                },
                "urgency": "high" if incident_context['severity'] >= 4 else "low",
                "body": {
                    "type": "incident_body",
                    "details": incident_context['root_cause']
                }
            }
        }
        
        headers = {
            "Authorization": f"Token token={self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.pagerduty+json;version=2"
        }
        
        response = requests.post(
            f"{self.base_url}/incidents",
            json=payload,
            headers=headers
        )
        
        if response.status_code == 201:
            return {
                "status": "success",
                "incident_id": response.json()["incident"]["id"]
            }
        else:
            return {
                "status": "failed",
                "error": response.text
            }

# Configure in .env
# PAGERDUTY_API_KEY=your_api_key
# PAGERDUTY_SERVICE_ID=your_service_id
```

#### 2. Kubernetes Pod Restart

```python
# agents/action_agent.py

from kubernetes import client, config

class KubernetesExecutor:
    def __init__(self, namespace: str = "default"):
        config.load_kube_config()  # Load ~/.kube/config
        self.api = client.CoreV1Api()
        self.apps_api = client.AppsV1Api()
        self.namespace = namespace
    
    def execute(self, incident_context: dict) -> dict:
        """Restart pods for a service"""
        
        service_name = incident_context['source']
        
        # Find deployment by label
        deployments = self.apps_api.list_namespaced_deployment(
            namespace=self.namespace,
            label_selector=f"app={service_name}"
        )
        
        if not deployments.items:
            return {
                "status": "failed",
                "error": f"No deployment found for {service_name}"
            }
        
        deployment = deployments.items[0]
        
        # Trigger rolling restart by updating annotation
        if deployment.spec.template.metadata.annotations is None:
            deployment.spec.template.metadata.annotations = {}
        
        deployment.spec.template.metadata.annotations['kubectl.kubernetes.io/restartedAt'] = \
            datetime.utcnow().isoformat()
        
        self.apps_api.patch_namespaced_deployment(
            name=deployment.metadata.name,
            namespace=self.namespace,
            body=deployment
        )
        
        return {
            "status": "success",
            "deployment": deployment.metadata.name,
            "pods_restarted": deployment.spec.replicas
        }

# Install: pip install kubernetes
# Configure: Ensure kubectl is configured with cluster access
```

#### 3. Slack Notification

```python
# agents/action_agent.py

import requests

class SlackExecutor:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
    
    def execute(self, incident_context: dict) -> dict:
        """Send Slack alert"""
        
        severity_emoji = {
            5: "🔴",
            4: "🟠",
            3: "🟡",
            2: "🟢",
            1: "⚪"
        }
        
        message = {
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"{severity_emoji.get(incident_context['severity'], '⚠️')} INCIDENT DETECTED"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Service:*\n{incident_context['source']}"},
                        {"type": "mrkdwn", "text": f"*Type:*\n{incident_context['anomaly_type']}"},
                        {"type": "mrkdwn", "text": f"*Severity:*\n{incident_context['severity']}/5"},
                        {"type": "mrkdwn", "text": f"*Priority:*\n{incident_context.get('priority', 'UNKNOWN')}"}
                    ]
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Root Cause:*\n{incident_context.get('root_cause', 'Analyzing...')}"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Actions Taken:*\n" + "\n".join([f"• {action}" for action in incident_context.get('actions_taken', [])])
                    }
                }
            ]
        }
        
        response = requests.post(self.webhook_url, json=message)
        
        return {
            "status": "success" if response.status_code == 200 else "failed"
        }

# Get webhook URL from Slack:
# 1. Go to https://api.slack.com/apps
# 2. Create app → Incoming Webhooks
# 3. Add to workspace → Copy webhook URL
# 4. Set in .env: SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
```

#### 4. AWS Auto Scaling

```python
# agents/action_agent.py

import boto3

class AWSAutoScalingExecutor:
    def __init__(self, region: str = "us-east-1"):
        self.client = boto3.client('autoscaling', region_name=region)
    
    def execute(self, incident_context: dict) -> dict:
        """Scale up auto-scaling group"""
        
        service_name = incident_context['source']
        asg_name = f"{service_name}-asg"  # Your naming convention
        
        try:
            # Get current capacity
            response = self.client.describe_auto_scaling_groups(
                AutoScalingGroupNames=[asg_name]
            )
            
            if not response['AutoScalingGroups']:
                return {
                    "status": "failed",
                    "error": f"ASG {asg_name} not found"
                }
            
            asg = response['AutoScalingGroups'][0]
            current_capacity = asg['DesiredCapacity']
            max_capacity = asg['MaxSize']
            
            # Calculate new capacity (increase by 50%, max 2x)
            new_capacity = min(
                int(current_capacity * 1.5),
                current_capacity + 5,  # Max +5 instances
                max_capacity
            )
            
            if new_capacity > current_capacity:
                self.client.set_desired_capacity(
                    AutoScalingGroupName=asg_name,
                    DesiredCapacity=new_capacity,
                    HonorCooldown=False
                )
                
                return {
                    "status": "success",
                    "asg": asg_name,
                    "previous_capacity": current_capacity,
                    "new_capacity": new_capacity
                }
            else:
                return {
                    "status": "skipped",
                    "reason": "Already at max capacity"
                }
        
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }

# Install: pip install boto3
# Configure: AWS credentials in ~/.aws/credentials or IAM role
```

---

## Common Real-World Scenarios

### Scenario 1: Database Connection Pool Exhaustion

**Setup**: Simulate a real database issue

```bash
# 1. Create test log file
cat > /tmp/test_logs.jsonl << EOF
{"timestamp": "2025-12-26T10:30:00Z", "level": "INFO", "service": "api-gateway", "message": "Request received"}
{"timestamp": "2025-12-26T10:30:01Z", "level": "ERROR", "service": "api-gateway", "message": "Connection pool exhausted"}
{"timestamp": "2025-12-26T10:30:02Z", "level": "ERROR", "service": "api-gateway", "message": "Connection pool exhausted"}
{"timestamp": "2025-12-26T10:30:03Z", "level": "ERROR", "service": "api-gateway", "message": "Connection pool exhausted"}
{"timestamp": "2025-12-26T10:30:04Z", "level": "ERROR", "service": "api-gateway", "message": "Connection pool exhausted"}
{"timestamp": "2025-12-26T10:30:05Z", "level": "ERROR", "service": "api-gateway", "message": "Connection pool exhausted"}
EOF

# 2. Configure system to read from file
# Edit pipelines/log_stream.py to use file reader

# 3. Run system
python main.py
```

**Expected Detection**:
```
[CRITICAL] ANOMALY DETECTED: error_spike in api-gateway
[REASONING] Root cause: Database connection pool exhausted, no connections available
[REASONING] Confidence: 0.87
[PLANNING] Recommended actions: restart_service, scale_up, check_database
[ACTION] Executing: restart_service → SUCCESS
```

### Scenario 2: Payment Gateway Timeout

**Setup**: Test high-impact service degradation

```python
# test_payment_failure.py
import requests
import time
import json

# Send logs to HTTP endpoint
endpoint = "http://localhost:8888"

# Normal traffic
for i in range(10):
    requests.post(endpoint, json={
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "level": "INFO",
        "service": "payment-service",
        "message": "Payment processed successfully"
    })
    time.sleep(0.5)

# Sudden failures
for i in range(20):
    requests.post(endpoint, json={
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "level": "ERROR",
        "service": "payment-service",
        "message": "Payment gateway timeout after 5000ms"
    })
    time.sleep(0.1)
```

**Run**:
```bash
# Terminal 1: Start system
python main.py

# Terminal 2: Send test logs
python test_payment_failure.py
```

**Expected Response**:
- Error spike detected (error rate > 30%)
- Severity: 5/5 (payment is critical)
- Priority: P1-CRITICAL
- Actions: alert_oncall, restart_service, check_external_api

### Scenario 3: Memory Leak Detection

**Setup**: Gradual performance degradation

```python
# test_memory_leak.py
import requests
import time
import random

endpoint = "http://localhost:8888"

# Simulate gradual memory increase
for hour in range(24):
    memory_usage = 50 + (hour * 2)  # MB, increasing 2MB/hour
    
    if memory_usage > 90:
        level = "CRITICAL"
        message = f"Memory usage critical: {memory_usage}% (OOM imminent)"
    elif memory_usage > 80:
        level = "ERROR"
        message = f"Memory usage high: {memory_usage}%"
    else:
        level = "WARN"
        message = f"Memory usage elevated: {memory_usage}%"
    
    requests.post(endpoint, json={
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "level": level,
        "service": "user-service",
        "message": message,
        "metrics": {"memory_mb": memory_usage * 10}
    })
    
    time.sleep(1)  # 1 second = 1 hour in simulation
```

---

## Troubleshooting Real Issues

### Issue 1: No Anomalies Detected

**Problem**: System running but not detecting errors

**Diagnosis**:
```bash
# Check log ingestion
python -c "from pipelines import log_stream; print(log_stream.create_log_stream())"

# Check anomaly thresholds
grep "ANOMALY_THRESHOLD" .env
grep "ERROR_RATE_THRESHOLD" .env
```

**Solutions**:
1. **Lower thresholds**: Edit `.env`
   ```
   ANOMALY_THRESHOLD=3  # Default is 5
   ERROR_RATE_THRESHOLD=0.2  # Default is 0.3 (30%)
   ```

2. **Check log format**: Ensure logs match expected schema
   ```python
   # Expected format:
   {
       "timestamp": "ISO 8601 string",
       "level": "ERROR",  # Must be uppercase
       "service": "service-name",
       "message": "Error description"
   }
   ```

3. **Enable debug logging**:
   ```python
   # main.py
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

### Issue 2: LLM API Failures

**Problem**: "LLM API call failed" errors

**Diagnosis**:
```bash
# Test API key
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('GROQ_API_KEY')[:10])"

# Test connectivity
curl -H "Authorization: Bearer $GROQ_API_KEY" https://api.groq.com/openai/v1/models
```

**Solutions**:
1. **Check API key**: Verify `.env` has correct key
2. **Enable fallback**: System uses rule-based logic if LLM fails
3. **Switch provider**: Change to OpenAI if Groq is down
   ```
   LLM_BASE_URL=https://api.openai.com/v1
   LLM_MODEL=gpt-4o-mini
   OPENAI_API_KEY=sk-...
   ```

### Issue 3: High Memory Usage

**Problem**: System consuming too much RAM

**Diagnosis**:
```bash
# Check Pathway table sizes
python -c "from state.incident_store import PathwayIncidentStore; store = PathwayIncidentStore(); print(len(store.incidents))"
```

**Solutions**:
1. **Limit memory window**: Keep only recent data
   ```python
   # state/incident_store.py
   # Add time-based filtering
   recent_incidents = incidents_table.filter(
       pw.this.created_at > pw.now() - timedelta(hours=24)
   )
   ```

2. **Increase flush frequency**: Write to storage more often
3. **Use external database**: Don't keep all state in memory

### Issue 4: Action Executors Failing

**Problem**: Actions not executing successfully

**Diagnosis**:
```bash
# Check executor configuration
python -c "from agents.action_agent import ActionAgent; agent = ActionAgent(); print(agent.executors.keys())"
```

**Solutions**:
1. **Verify credentials**: Check API keys, Kubernetes config, AWS credentials
2. **Test connectivity**: Ensure network access to external services
3. **Enable dry-run mode**: Test without actual execution
   ```
   DRY_RUN=true  # In .env
   ```

---

## Production Deployment

### Step 1: Replace Simulated Components

```python
# main.py - Production configuration

from pipelines.log_stream import create_kafka_log_stream
from agents.action_agent import (
    PagerDutyExecutor,
    KubernetesExecutor,
    SlackExecutor,
    AWSAutoScalingExecutor
)

# Real log source
log_stream = create_kafka_log_stream(
    bootstrap_servers=os.getenv("KAFKA_BROKERS"),
    topic="production-logs"
)

# Real action executors
executors = {
    "alert_oncall": PagerDutyExecutor(
        api_key=os.getenv("PAGERDUTY_API_KEY"),
        service_id=os.getenv("PAGERDUTY_SERVICE_ID")
    ),
    "restart_service": KubernetesExecutor(
        namespace="production"
    ),
    "notify_slack": SlackExecutor(
        webhook_url=os.getenv("SLACK_WEBHOOK_URL")
    ),
    "scale_up": AWSAutoScalingExecutor(
        region=os.getenv("AWS_REGION", "us-east-1")
    )
}
```

### Step 2: Configure Monitoring

```python
# monitoring.py - Add observability

from prometheus_client import Counter, Histogram, start_http_server

# Metrics
incidents_detected = Counter('incidents_detected_total', 'Total incidents detected', ['service', 'type'])
agent_latency = Histogram('agent_processing_seconds', 'Agent processing time', ['agent_name'])
actions_executed = Counter('actions_executed_total', 'Actions executed', ['action_type', 'status'])

# Start metrics server
start_http_server(9090)
```

### Step 3: Add Health Checks

```python
# health.py

from fastapi import FastAPI
from datetime import datetime

app = FastAPI()

health_status = {
    "pathway_running": False,
    "agents_active": False,
    "last_log_processed": None,
    "last_incident_detected": None
}

@app.get("/health")
def health_check():
    # Check if processing is recent (within 5 minutes)
    if health_status["last_log_processed"]:
        time_since_last_log = (datetime.now() - health_status["last_log_processed"]).seconds
        if time_since_last_log > 300:
            return {"status": "unhealthy", "reason": "No logs processed recently"}
    
    return {"status": "healthy", "details": health_status}

@app.get("/metrics")
def get_metrics():
    return {
        "total_incidents": len(incident_store.get_all_incidents()),
        "active_incidents": len([i for i in incident_store.get_all_incidents() if i.escalation_status != "resolved"]),
        "last_24h_incidents": len(incident_store.get_recent_incidents(hours=24))
    }
```

### Step 4: Deploy with Docker

```dockerfile
# Dockerfile

FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Environment variables via docker-compose or k8s secrets
ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
```

```yaml
# docker-compose.yml

version: '3.8'

services:
  pathway-backend:
    build: .
    environment:
      - GROQ_API_KEY=${GROQ_API_KEY}
      - KAFKA_BROKERS=kafka:9092
      - PAGERDUTY_API_KEY=${PAGERDUTY_API_KEY}
      - SLACK_WEBHOOK_URL=${SLACK_WEBHOOK_URL}
    depends_on:
      - kafka
    restart: unless-stopped

  kafka:
    image: confluentinc/cp-kafka:latest
    environment:
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
    depends_on:
      - zookeeper

  zookeeper:
    image: confluentinc/cp-zookeeper:latest
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
```

---

## Testing Checklist

Before production:

- [ ] Test with real log files (not simulated)
- [ ] Verify anomaly detection thresholds match your traffic
- [ ] Test each action executor in staging environment
- [ ] Confirm LLM API rate limits are sufficient
- [ ] Set up monitoring and alerts for the system itself
- [ ] Test failover scenarios (LLM API down, Kafka unavailable)
- [ ] Document runbooks for common issues
- [ ] Set up log rotation and storage limits
- [ ] Configure backup LLM provider
- [ ] Test human override workflows via interface

---

## Quick Reference

### Finding Errors in Real Systems

```bash
# 1. Point to your logs
export LOG_SOURCE="/var/log/myapp/*.log"

# 2. Run system
python main.py

# 3. Watch dashboard
cd ../pathwaycom-llm-app
python client/dashboard.py watch 5

# 4. Check what was detected
python client/dashboard.py recent 24
```

### Testing Specific Scenarios

```bash
# Database issues
grep -i "connection" /var/log/myapp/*.log | python inject_logs.py

# Memory leaks
grep -i "memory" /var/log/myapp/*.log | python inject_logs.py

# External API failures
grep -i "timeout\|503\|504" /var/log/myapp/*.log | python inject_logs.py
```

---

This guide gets you from demo mode to production-ready incident response. Start with simulated logs, then gradually integrate real systems.
