# 🔌 Integration Guide: Connect Your Projects

This guide shows you how to **integrate your existing projects** with this incident response system, monitor them, and receive automated responses.

---

## 📋 Table of Contents

1. [Integration Overview](#integration-overview)
2. [Send Logs from Your Application](#send-logs-from-your-application)
3. [Receive Automated Responses](#receive-automated-responses)
4. [Monitor Your Projects](#monitor-your-projects)
5. [Language-Specific Examples](#language-specific-examples)
6. [Integration Patterns](#integration-patterns)

---

## Integration Overview

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  YOUR EXISTING PROJECTS                     │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │   Web App   │  │   API       │  │  Microservice│        │
│  │  (Node.js)  │  │  (Python)   │  │   (Java)    │        │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘        │
│         │                 │                 │               │
│         └─────────────────┴─────────────────┘               │
│                           │                                 │
│                           │ Logs (JSON)                     │
│                           │                                 │
└───────────────────────────┼─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│           PATHWAY INCIDENT RESPONSE SYSTEM                  │
│                                                             │
│  1. Receives logs ──┐                                       │
│  2. Detects anomalies                                       │
│  3. Analyzes with LLM                                       │
│  4. Takes automated actions ──┐                             │
│                               │                             │
└───────────────────────────────┼─────────────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │  Automated Actions    │
                    │  • PagerDuty alert    │
                    │  • Slack notification │
                    │  • Restart service    │
                    │  • Scale up           │
                    └───────────────────────┘
```

### Three Steps to Integration

1. **Instrument Your Code**: Add logging/monitoring to your application
2. **Send Data**: Push logs to the incident response system
3. **Receive Actions**: Get automated responses and alerts

---

## Send Logs from Your Application

### Method 1: HTTP Endpoint (Simplest)

**Configure the system to accept HTTP logs**:

```python
# In pathwaycom-pathway/pipelines/log_stream.py

import pathway as pw

def create_http_log_stream():
    """Accept logs via HTTP POST to port 8888"""
    
    schema = pw.schema_builder(
        columns={
            "timestamp": pw.column_definition(dtype=str),
            "level": pw.column_definition(dtype=str),
            "service": pw.column_definition(dtype=str),
            "message": pw.column_definition(dtype=str),
            "error_type": pw.column_definition(dtype=str, default=""),
            "stack_trace": pw.column_definition(dtype=str, default=""),
            "user_id": pw.column_definition(dtype=str, default=""),
            "request_id": pw.column_definition(dtype=str, default=""),
        }
    )
    
    logs = pw.io.http.rest_connector(
        host="0.0.0.0",
        port=8888,
        schema=schema,
        delete_completed_queries=True,
    )
    
    return logs

# Update main.py to use this
```

**Send logs from your Python app**:

```python
# your_application.py

import requests
import json
from datetime import datetime

class IncidentLogger:
    def __init__(self, endpoint="http://localhost:8888"):
        self.endpoint = endpoint
        self.service_name = "your-service-name"
    
    def log(self, level, message, **extra):
        """Send log to incident response system"""
        
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": level.upper(),
            "service": self.service_name,
            "message": message,
            **extra
        }
        
        try:
            requests.post(self.endpoint, json=log_entry, timeout=1)
        except Exception as e:
            # Don't let logging errors break your app
            print(f"Failed to send log: {e}")

# Usage in your code
logger = IncidentLogger()

try:
    # Your business logic
    result = process_payment(user_id, amount)
except PaymentGatewayTimeout as e:
    # This will be detected as an anomaly
    logger.log(
        "ERROR",
        f"Payment gateway timeout after {e.duration}ms",
        error_type="timeout",
        user_id=user_id,
        request_id=request_id,
        stack_trace=str(e)
    )
    raise

try:
    connection = database.connect()
except ConnectionPoolExhausted as e:
    logger.log(
        "CRITICAL",
        "Database connection pool exhausted",
        error_type="connection_pool",
        pool_size=e.max_connections,
        active_connections=e.current_connections
    )
    raise
```

**Send logs from Node.js app**:

```javascript
// your_node_app.js

const axios = require('axios');

class IncidentLogger {
  constructor(endpoint = 'http://localhost:8888') {
    this.endpoint = endpoint;
    this.serviceName = 'your-service-name';
  }
  
  async log(level, message, extra = {}) {
    const logEntry = {
      timestamp: new Date().toISOString(),
      level: level.toUpperCase(),
      service: this.serviceName,
      message: message,
      ...extra
    };
    
    try {
      await axios.post(this.endpoint, logEntry, { timeout: 1000 });
    } catch (error) {
      // Don't let logging errors break your app
      console.error('Failed to send log:', error.message);
    }
  }
}

// Usage
const logger = new IncidentLogger();

app.post('/api/payment', async (req, res) => {
  try {
    const result = await processPayment(req.body);
    res.json(result);
  } catch (error) {
    // This error will be monitored
    await logger.log(
      'ERROR',
      `Payment failed: ${error.message}`,
      {
        error_type: error.code,
        user_id: req.user.id,
        request_id: req.id,
        stack_trace: error.stack
      }
    );
    res.status(500).json({ error: 'Payment failed' });
  }
});
```

**Send logs from Java app**:

```java
// IncidentLogger.java

import com.fasterxml.jackson.databind.ObjectMapper;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.net.URI;
import java.time.Instant;
import java.util.HashMap;
import java.util.Map;

public class IncidentLogger {
    private final String endpoint;
    private final String serviceName;
    private final HttpClient client;
    private final ObjectMapper mapper;
    
    public IncidentLogger(String endpoint, String serviceName) {
        this.endpoint = endpoint;
        this.serviceName = serviceName;
        this.client = HttpClient.newHttpClient();
        this.mapper = new ObjectMapper();
    }
    
    public void log(String level, String message, Map<String, String> extra) {
        Map<String, Object> logEntry = new HashMap<>();
        logEntry.put("timestamp", Instant.now().toString());
        logEntry.put("level", level.toUpperCase());
        logEntry.put("service", serviceName);
        logEntry.put("message", message);
        if (extra != null) {
            logEntry.putAll(extra);
        }
        
        try {
            String json = mapper.writeValueAsString(logEntry);
            HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(endpoint))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(json))
                .build();
            
            client.sendAsync(request, HttpResponse.BodyHandlers.ofString());
        } catch (Exception e) {
            // Don't let logging errors break your app
            System.err.println("Failed to send log: " + e.getMessage());
        }
    }
}

// Usage
IncidentLogger logger = new IncidentLogger("http://localhost:8888", "order-service");

try {
    processOrder(orderId);
} catch (DatabaseException e) {
    Map<String, String> extra = new HashMap<>();
    extra.put("error_type", "database");
    extra.put("order_id", orderId);
    extra.put("stack_trace", getStackTrace(e));
    
    logger.log("ERROR", "Database query failed: " + e.getMessage(), extra);
    throw e;
}
```

---

### Method 2: Kafka Integration (Production-Grade)

**For high-throughput applications, use Kafka**:

```python
# In pathwaycom-pathway/pipelines/log_stream.py

import pathway as pw

def create_kafka_log_stream():
    """Consume logs from Kafka topic"""
    
    logs = pw.io.kafka.read(
        rdkafka_settings={
            "bootstrap.servers": "your-kafka:9092",
            "group.id": "incident-response-system",
            "auto.offset.reset": "latest",
        },
        topic="application-logs",
        format="json",
        autocommit_duration_ms=1000,
    )
    
    return logs
```

**Send logs to Kafka from your Python app**:

```python
# your_application.py

from kafka import KafkaProducer
import json
from datetime import datetime

class KafkaIncidentLogger:
    def __init__(self, bootstrap_servers, topic="application-logs"):
        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        self.topic = topic
        self.service_name = "your-service"
    
    def log(self, level, message, **extra):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": level.upper(),
            "service": self.service_name,
            "message": message,
            **extra
        }
        
        self.producer.send(self.topic, log_entry)

# Usage
logger = KafkaIncidentLogger(['kafka:9092'])

# Your existing logging automatically goes to incident system
import logging
logging.basicConfig(level=logging.INFO)

# Or explicit error logging
try:
    risky_operation()
except Exception as e:
    logger.log("ERROR", str(e), error_type=type(e).__name__)
```

**Send from Node.js to Kafka**:

```javascript
// your_node_app.js

const { Kafka } = require('kafkajs');

class KafkaIncidentLogger {
  constructor(brokers, topic = 'application-logs') {
    this.kafka = new Kafka({ brokers });
    this.producer = this.kafka.producer();
    this.topic = topic;
    this.serviceName = 'your-service';
    this.producer.connect();
  }
  
  async log(level, message, extra = {}) {
    const logEntry = {
      timestamp: new Date().toISOString(),
      level: level.toUpperCase(),
      service: this.serviceName,
      message: message,
      ...extra
    };
    
    await this.producer.send({
      topic: this.topic,
      messages: [{ value: JSON.stringify(logEntry) }],
    });
  }
}

// Usage
const logger = new KafkaIncidentLogger(['kafka:9092']);

// Integrate with existing error handler
app.use((err, req, res, next) => {
  logger.log('ERROR', err.message, {
    error_type: err.name,
    url: req.url,
    method: req.method,
    user_id: req.user?.id,
    stack_trace: err.stack
  });
  
  res.status(500).json({ error: 'Internal server error' });
});
```

---

### Method 3: File-Based (Existing Logs)

**If you already write logs to files**:

```python
# In pathwaycom-pathway/pipelines/log_stream.py

import pathway as pw

def create_file_log_stream(log_pattern="/var/log/myapp/*.log"):
    """Tail existing log files"""
    
    logs = pw.io.fs.read(
        path=log_pattern,
        format="json",
        mode="streaming",  # Like 'tail -f'
        autocommit_duration_ms=100,
    )
    
    return logs
```

**Just ensure your app writes JSON logs**:

```python
# your_application.py

import logging
import json
from datetime import datetime

class JSONFileLogger:
    def __init__(self, log_file):
        self.log_file = log_file
        self.service_name = "your-service"
    
    def log(self, level, message, **extra):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": level.upper(),
            "service": self.service_name,
            "message": message,
            **extra
        }
        
        with open(self.log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')

# Configure standard logging to write JSON
import logging.config

LOGGING_CONFIG = {
    'version': 1,
    'handlers': {
        'json_file': {
            'class': 'logging.FileHandler',
            'filename': '/var/log/myapp/app.log',
            'formatter': 'json'
        }
    },
    'formatters': {
        'json': {
            'format': '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "service": "your-service", "message": "%(message)s"}'
        }
    },
    'root': {
        'level': 'INFO',
        'handlers': ['json_file']
    }
}

logging.config.dictConfig(LOGGING_CONFIG)
```

---

## Receive Automated Responses

### How the System Responds

When an incident is detected, the system can:
1. **Alert your team** (PagerDuty, Slack)
2. **Take automated actions** (restart, scale, rollback)
3. **Update your dashboard** (interface layer)

### Webhook Callbacks

**Configure the system to call your endpoint when incidents occur**:

```python
# In pathwaycom-pathway/agents/action_agent.py

class WebhookExecutor:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
    
    def execute(self, incident_context: dict) -> dict:
        """Call your webhook with incident details"""
        
        payload = {
            "event": "incident_detected",
            "incident_id": incident_context['incident_id'],
            "service": incident_context['source'],
            "severity": incident_context['severity'],
            "root_cause": incident_context.get('root_cause', ''),
            "recommended_actions": incident_context.get('recommended_actions', []),
            "detected_at": incident_context['detected_at']
        }
        
        response = requests.post(
            self.webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        return {
            "status": "success" if response.status_code == 200 else "failed",
            "response": response.text
        }

# Configure in agents/action_agent.py
executors = {
    "notify_webhook": WebhookExecutor(
        webhook_url=os.getenv("INCIDENT_WEBHOOK_URL")
    )
}
```

**Handle webhook in your application**:

```python
# your_application.py - Flask example

from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/incident-webhook', methods=['POST'])
def handle_incident():
    """Receive incident notifications"""
    
    incident = request.json
    
    # Your custom logic
    if incident['severity'] >= 4:
        # Critical incident - wake up the team
        send_sms_to_oncall(incident)
        create_war_room(incident)
    
    if incident['service'] == 'payment-service':
        # Payment issues - switch to backup processor
        enable_backup_payment_gateway()
    
    if 'scale_up' in incident['recommended_actions']:
        # Auto-scaling recommended
        trigger_autoscaling(incident['service'])
    
    return jsonify({"status": "received"})

# Set in .env: INCIDENT_WEBHOOK_URL=https://yourapp.com/incident-webhook
```

**Node.js webhook handler**:

```javascript
// your_node_app.js

app.post('/incident-webhook', async (req, res) => {
  const incident = req.body;
  
  console.log(`Incident detected: ${incident.incident_id}`);
  
  // Your custom response logic
  if (incident.service === 'user-auth') {
    // Auth service issues - enable fallback
    await enableAuthFallback();
  }
  
  if (incident.severity >= 5) {
    // Critical - create Slack channel
    await createIncidentChannel(incident);
  }
  
  // Log to your monitoring
  await yourMonitoring.recordIncident(incident);
  
  res.json({ status: 'handled' });
});
```

---

### Query Incident Status

**Check incident status from your application**:

```python
# your_application.py

import requests

class IncidentClient:
    def __init__(self, interface_url="http://localhost:8000"):
        self.base_url = interface_url
    
    def get_active_incidents(self, service=None):
        """Get current incidents for your service"""
        
        params = {"severity_min": 3}
        if service:
            params["source"] = service
        
        response = requests.get(
            f"{self.base_url}/api/incidents",
            params=params
        )
        return response.json()
    
    def get_service_health(self, service):
        """Check if service has active incidents"""
        
        incidents = self.get_active_incidents(service=service)
        
        if not incidents:
            return {"status": "healthy", "incidents": 0}
        
        critical_count = sum(1 for i in incidents if i['severity'] >= 4)
        
        return {
            "status": "degraded" if critical_count > 0 else "warning",
            "incidents": len(incidents),
            "critical_incidents": critical_count
        }
    
    def acknowledge_incident(self, incident_id, operator, reason):
        """Mark incident as acknowledged"""
        
        response = requests.post(
            f"{self.base_url}/api/incidents/{incident_id}/acknowledge",
            json={"operator": operator, "reason": reason}
        )
        return response.json()

# Usage in your app
incident_client = IncidentClient()

# Before deploying, check if there are active incidents
health = incident_client.get_service_health("payment-service")
if health['critical_incidents'] > 0:
    print("WARNING: Cannot deploy - critical incidents active")
    sys.exit(1)

# After manual fix, acknowledge
incident_client.acknowledge_incident(
    incident_id="INC-123",
    operator="devops@company.com",
    reason="Database credentials rotated, system recovered"
)
```

---

## Monitor Your Projects

### Dashboard Integration

**Embed incident dashboard in your admin panel**:

```python
# your_admin_panel.py - Flask example

from flask import Flask, render_template
import requests

app = Flask(__name__)

@app.route('/admin/incidents')
def incidents_dashboard():
    """Show incidents in your admin panel"""
    
    # Get data from incident response system
    response = requests.get('http://localhost:8000/api/dashboard')
    dashboard_data = response.json()
    
    # Get recent incidents
    incidents_response = requests.get('http://localhost:8000/api/incidents?hours=24')
    recent_incidents = incidents_response.json()
    
    return render_template(
        'incidents.html',
        dashboard=dashboard_data,
        incidents=recent_incidents
    )

@app.route('/admin/service-health/<service_name>')
def service_health(service_name):
    """Show health for specific service"""
    
    response = requests.get(
        f'http://localhost:8000/api/incidents',
        params={"source": service_name, "hours": 24}
    )
    
    incidents = response.json()
    
    return render_template(
        'service_health.html',
        service=service_name,
        incidents=incidents,
        status="healthy" if not incidents else "degraded"
    )
```

**React component for incidents**:

```javascript
// IncidentsDashboard.jsx

import React, { useState, useEffect } from 'react';
import axios from 'axios';

const IncidentsDashboard = ({ serviceName }) => {
  const [incidents, setIncidents] = useState([]);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    const fetchIncidents = async () => {
      try {
        const response = await axios.get('http://localhost:8000/api/incidents', {
          params: {
            source: serviceName,
            hours: 24
          }
        });
        setIncidents(response.data);
      } catch (error) {
        console.error('Failed to fetch incidents:', error);
      } finally {
        setLoading(false);
      }
    };
    
    fetchIncidents();
    const interval = setInterval(fetchIncidents, 30000); // Refresh every 30s
    
    return () => clearInterval(interval);
  }, [serviceName]);
  
  if (loading) return <div>Loading...</div>;
  
  return (
    <div className="incidents-dashboard">
      <h2>Incidents for {serviceName}</h2>
      <div className="incidents-count">
        {incidents.length === 0 ? (
          <span className="status-healthy">✅ No active incidents</span>
        ) : (
          <span className="status-warning">⚠️ {incidents.length} active incidents</span>
        )}
      </div>
      
      <div className="incidents-list">
        {incidents.map(incident => (
          <div key={incident.incident_id} className={`incident severity-${incident.severity}`}>
            <h3>{incident.incident_id}</h3>
            <p><strong>Type:</strong> {incident.anomaly_type}</p>
            <p><strong>Detected:</strong> {new Date(incident.detected_at).toLocaleString()}</p>
            <p><strong>Root Cause:</strong> {incident.root_cause_analysis}</p>
            <p><strong>Actions:</strong> {incident.actions_taken.join(', ')}</p>
            {!incident.acknowledged_by && (
              <button onClick={() => acknowledgeIncident(incident.incident_id)}>
                Acknowledge
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

const acknowledgeIncident = async (incidentId) => {
  await axios.post(`http://localhost:8000/api/incidents/${incidentId}/acknowledge`, {
    operator: 'current-user@company.com',
    reason: 'Reviewing incident'
  });
  // Refresh incidents...
};

export default IncidentsDashboard;
```

---

### Metrics & Observability

**Export metrics to your monitoring system**:

```python
# In pathwaycom-pathway/monitoring/metrics.py

from prometheus_client import Counter, Histogram, Gauge, start_http_server
import time

# Define metrics
incidents_total = Counter(
    'incidents_detected_total',
    'Total incidents detected',
    ['service', 'severity', 'anomaly_type']
)

incident_resolution_time = Histogram(
    'incident_resolution_seconds',
    'Time to resolve incidents',
    ['service', 'priority']
)

active_incidents = Gauge(
    'active_incidents_count',
    'Number of active incidents',
    ['service']
)

agent_processing_time = Histogram(
    'agent_processing_seconds',
    'Time spent in each agent',
    ['agent_name']
)

# Instrument your code
def record_incident(incident):
    incidents_total.labels(
        service=incident['source'],
        severity=incident['severity'],
        anomaly_type=incident['anomaly_type']
    ).inc()
    
    active_incidents.labels(service=incident['source']).inc()

# Start metrics server
start_http_server(9090)
```

**Scrape metrics with Prometheus**:

```yaml
# prometheus.yml

scrape_configs:
  - job_name: 'incident-response'
    static_configs:
      - targets: ['localhost:9090']
    scrape_interval: 15s
```

**Grafana dashboard queries**:

```promql
# Incidents per service
sum by (service) (rate(incidents_detected_total[5m]))

# Active incidents
sum(active_incidents_count)

# P95 agent processing time
histogram_quantile(0.95, rate(agent_processing_seconds_bucket[5m]))

# Critical incidents rate
sum(rate(incidents_detected_total{severity="5"}[5m]))
```

---

## Complete Integration Example

### Example: E-commerce Application

**Your existing Flask app**:

```python
# app.py - Your e-commerce application

from flask import Flask, request, jsonify
import requests
from datetime import datetime

app = Flask(__name__)

# Integration with incident response system
class IncidentMonitoring:
    def __init__(self):
        self.log_endpoint = "http://incident-system:8888"
        self.query_endpoint = "http://incident-interface:8000"
        self.service_name = "ecommerce-api"
    
    def log_error(self, error_type, message, **extra):
        """Send error to monitoring"""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": "ERROR",
            "service": self.service_name,
            "message": message,
            "error_type": error_type,
            **extra
        }
        try:
            requests.post(self.log_endpoint, json=log_entry, timeout=1)
        except:
            pass  # Don't break app if monitoring is down
    
    def check_health(self):
        """Check if there are active incidents for this service"""
        try:
            response = requests.get(
                f"{self.query_endpoint}/api/incidents",
                params={"source": self.service_name, "severity_min": 4},
                timeout=2
            )
            incidents = response.json()
            return len(incidents) == 0
        except:
            return True  # Assume healthy if can't check

monitoring = IncidentMonitoring()

@app.route('/api/checkout', methods=['POST'])
def checkout():
    try:
        # Your checkout logic
        order = process_checkout(request.json)
        
        # Try payment
        try:
            payment_result = process_payment(order)
        except PaymentGatewayTimeout as e:
            # This will be detected and trigger automated response
            monitoring.log_error(
                "payment_timeout",
                f"Payment gateway timeout for order {order.id}",
                order_id=order.id,
                amount=order.total,
                gateway="stripe",
                duration_ms=e.duration
            )
            return jsonify({"error": "Payment temporarily unavailable"}), 503
        
        except PaymentDeclined as e:
            # Not an incident, just log for analytics
            monitoring.log_error(
                "payment_declined",
                f"Payment declined for order {order.id}",
                order_id=order.id,
                reason=e.reason
            )
            return jsonify({"error": "Payment declined"}), 400
        
        return jsonify({"order_id": order.id, "status": "confirmed"})
        
    except DatabaseConnectionError as e:
        # Critical error - will trigger alerts
        monitoring.log_error(
            "database_connection",
            "Database connection failed during checkout",
            error=str(e),
            pool_exhausted=True
        )
        return jsonify({"error": "Service temporarily unavailable"}), 503

@app.route('/health', methods=['GET'])
def health_check():
    """Health check includes incident status"""
    
    healthy = monitoring.check_health()
    
    return jsonify({
        "status": "healthy" if healthy else "degraded",
        "service": "ecommerce-api",
        "has_active_incidents": not healthy
    }), 200 if healthy else 503

@app.route('/admin/incidents', methods=['GET'])
def view_incidents():
    """Admin panel showing incidents"""
    response = requests.get(f"{monitoring.query_endpoint}/api/incidents?source={monitoring.service_name}")
    return jsonify(response.json())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
```

---

## Integration Checklist

Before going to production:

- [ ] **Instrumented your code** with error logging
- [ ] **Chosen integration method** (HTTP, Kafka, files)
- [ ] **Tested log sending** from your application
- [ ] **Configured webhook** to receive automated responses
- [ ] **Set up monitoring** in your admin dashboard
- [ ] **Tested incident flow** end-to-end
- [ ] **Configured alerts** (PagerDuty, Slack)
- [ ] **Added health checks** that query incident status
- [ ] **Documented integration** for your team
- [ ] **Set up metrics** (Prometheus/Grafana)

---

## Quick Start Integration

```bash
# 1. Start incident response system
cd pathwaycom-pathway
python main.py  # Listening on port 8888

# 2. In your application, send a test log
curl -X POST http://localhost:8888 \
  -H "Content-Type: application/json" \
  -d '{
    "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'",
    "level": "ERROR",
    "service": "my-app",
    "message": "Test error for integration"
  }'

# 3. Check if detected
cd pathwaycom-llm-app
python client/dashboard.py overview

# You should see your error detected!
```

---

This guide shows you exactly how to connect your projects to the incident response system and receive automated monitoring and responses! 🚀
