# 📱 Flutter App Integration Guide - Step by Step

**Complete beginner-friendly guide to connect your Flutter app with the incident response system.**

---

## 🎯 What You'll Achieve

Your Flutter app will:
1. Send errors/crashes to the incident monitoring system
2. Get automatic alerts when critical issues occur
3. See all errors in a dashboard

---

## 📋 Prerequisites

- Flutter project already created
- VS Code with Flutter extension installed
- Both repositories cloned on your computer

---

## Step 1: Install HTTP Package in Flutter (2 minutes)

### 1.1 Open your Flutter project in VS Code

```bash
# Navigate to your Flutter project
cd path/to/your/flutter/project
code .
```

### 1.2 Add the http package

Open `pubspec.yaml` and add under `dependencies`:

```yaml
dependencies:
  flutter:
    sdk: flutter
  http: ^1.1.0  # Add this line
```

### 1.3 Install the package

**In VS Code terminal** (View → Terminal or Ctrl+`):

```bash
flutter pub get
```

---

## Step 2: Create Logger Class in Flutter (5 minutes)

### 2.1 Create a new file

Create `lib/services/incident_logger.dart`:

```dart
// lib/services/incident_logger.dart

import 'dart:convert';
import 'package:http/http.dart' as http;

class IncidentLogger {
  // Change this to your computer's IP if running on real device
  // For emulator, use 'http://10.0.2.2:8888'
  // For iOS simulator, use 'http://localhost:8888'
  final String endpoint;
  final String serviceName;
  
  IncidentLogger({
    this.endpoint = 'http://10.0.2.2:8888', // Android emulator
    this.serviceName = 'flutter-app',
  });
  
  /// Log an error to the incident monitoring system
  Future<void> logError(
    String message, {
    String level = 'ERROR',
    Map<String, dynamic>? extra,
  }) async {
    try {
      final logEntry = {
        'timestamp': DateTime.now().toUtc().toIso8601String(),
        'level': level.toUpperCase(),
        'service': serviceName,
        'message': message,
        if (extra != null) ...extra,
      };
      
      await http.post(
        Uri.parse(endpoint),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(logEntry),
      ).timeout(
        const Duration(seconds: 2),
        onTimeout: () {
          // Don't let logging errors crash your app
          print('Failed to send log (timeout)');
          return http.Response('Timeout', 408);
        },
      );
    } catch (e) {
      // Don't let logging errors crash your app
      print('Failed to send log: $e');
    }
  }
  
  /// Log critical errors (crashes, payment failures, etc.)
  Future<void> logCritical(String message, {Map<String, dynamic>? extra}) async {
    await logError(message, level: 'CRITICAL', extra: extra);
  }
  
  /// Log warnings (performance issues, deprecated API usage, etc.)
  Future<void> logWarning(String message, {Map<String, dynamic>? extra}) async {
    await logError(message, level: 'WARN', extra: extra);
  }
  
  /// Log info (successful operations, state changes, etc.)
  Future<void> logInfo(String message, {Map<String, dynamic>? extra}) async {
    await logError(message, level: 'INFO', extra: extra);
  }
}
```

### 2.2 Understanding the endpoints

**Important**: The endpoint depends on where your app is running:

| Running on | Endpoint | Reason |
|------------|----------|--------|
| Android Emulator | `http://10.0.2.2:8888` | Emulator's special IP for host machine |
| iOS Simulator | `http://localhost:8888` | Simulator shares host network |
| Real Device | `http://192.168.x.x:8888` | Your computer's local network IP |

**To find your computer's IP** (for real device):

Windows:
```bash
ipconfig
# Look for "IPv4 Address" under your WiFi adapter
```

Mac/Linux:
```bash
ifconfig
# Look for "inet" under en0 or wlan0
```

---

## Step 3: Use Logger in Your Flutter App (3 minutes)

### 3.1 Initialize the logger

In `lib/main.dart`:

```dart
import 'package:flutter/material.dart';
import 'services/incident_logger.dart';

// Create global logger instance
final incidentLogger = IncidentLogger(
  endpoint: 'http://10.0.2.2:8888', // Change based on where you're running
  serviceName: 'my-flutter-app', // Change to your app name
);

void main() {
  // Catch Flutter framework errors
  FlutterError.onError = (FlutterErrorDetails details) {
    FlutterError.presentError(details);
    
    // Send to incident monitoring
    incidentLogger.logCritical(
      'Flutter Framework Error: ${details.exception}',
      extra: {
        'error_type': 'flutter_error',
        'stack_trace': details.stack.toString(),
        'library': details.library ?? 'unknown',
      },
    );
  };
  
  runApp(MyApp());
}

class MyApp extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'My App',
      home: MyHomePage(),
    );
  }
}
```

### 3.2 Log errors in your code

**Example 1: Network errors**

```dart
// In your API call
Future<void> fetchUserData() async {
  try {
    final response = await http.get(Uri.parse('https://api.example.com/user'));
    
    if (response.statusCode == 200) {
      // Success
      final data = jsonDecode(response.body);
      // Use data...
    } else {
      // API returned error
      await incidentLogger.logError(
        'API returned error: ${response.statusCode}',
        extra: {
          'error_type': 'api_error',
          'status_code': response.statusCode,
          'endpoint': '/user',
        },
      );
    }
  } catch (e) {
    // Network error or timeout
    await incidentLogger.logCritical(
      'Network request failed: $e',
      extra: {
        'error_type': 'network_error',
        'endpoint': '/user',
      },
    );
    
    // Show error to user
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('Network error. Please try again.')),
    );
  }
}
```

**Example 2: Payment errors**

```dart
// In your payment handling
Future<void> processPayment(double amount) async {
  try {
    final result = await paymentGateway.charge(amount);
    
    if (!result.success) {
      await incidentLogger.logCritical(
        'Payment failed: ${result.error}',
        extra: {
          'error_type': 'payment_failure',
          'amount': amount,
          'error_code': result.errorCode,
          'user_id': currentUser.id,
        },
      );
    }
  } catch (e) {
    await incidentLogger.logCritical(
      'Payment gateway error: $e',
      extra: {
        'error_type': 'payment_gateway_error',
        'amount': amount,
      },
    );
  }
}
```

**Example 3: Database errors**

```dart
// In your local database operations
Future<void> saveUserPreferences(Map<String, dynamic> prefs) async {
  try {
    await database.insert('preferences', prefs);
  } catch (e) {
    await incidentLogger.logError(
      'Failed to save preferences: $e',
      extra: {
        'error_type': 'database_error',
        'operation': 'insert',
        'table': 'preferences',
      },
    );
  }
}
```

---

## Step 4: Run Everything Together in VS Code (5 minutes)

### 4.1 Open Multiple Terminals in VS Code

**Terminal 1: Incident Response System (Backend)**

```bash
# Open new terminal (Terminal → New Terminal or Ctrl+Shift+`)
cd C:\Users\Jayaprakash\Desktop\IIT-M\pathwaycom-pathway
python main.py
```

You should see:
```
[INFO] Starting Pathway Real-Time Incident Response System
[INFO] LangGraph agent workflow initialized
[INFO] Listening for logs on http://0.0.0.0:8888
```

**Terminal 2: Interface Dashboard**

```bash
# Open another new terminal (click + icon)
cd C:\Users\Jayaprakash\Desktop\IIT-M\pathwaycom-llm-app
python client/dashboard.py watch 5
```

You should see the dashboard refreshing every 5 seconds.

**Terminal 3: Your Flutter App**

```bash
# Open another new terminal
cd path/to/your/flutter/project
flutter run
```

### 4.2 Alternative: Use VS Code's Split Terminal

1. Open Terminal (Ctrl+`)
2. Click the split icon (⊞) to split horizontally
3. Run each command in a different pane
4. You can see all outputs at once!

---

## Step 5: Test the Integration (2 minutes)

### 5.1 Create a Test Error in Your Flutter App

Add a test button to trigger an error:

```dart
// In your widget
ElevatedButton(
  onPressed: () async {
    // Simulate an error
    await incidentLogger.logError(
      'Test error from Flutter app',
      extra: {
        'error_type': 'test_error',
        'button_pressed': 'test_button',
        'timestamp': DateTime.now().toString(),
      },
    );
    
    // Show confirmation
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('Error sent to monitoring system')),
    );
  },
  child: Text('Test Error Logging'),
)
```

### 5.2 Test It

1. Make sure all 3 terminals are running:
   - Backend: `python main.py`
   - Dashboard: `python client/dashboard.py watch 5`
   - Flutter: `flutter run`

2. In your Flutter app, tap the "Test Error Logging" button

3. Watch Terminal 1 (Backend) - You should see:
   ```
   [LOG] 2025-12-26T10:30:00Z - flutter-app - ERROR - Test error from Flutter app
   ```

4. Watch Terminal 2 (Dashboard) - You should see your error appear!

---

## Step 6: Test Real Error Scenarios (5 minutes)

### Scenario 1: Simulate Network Error

```dart
// Add this test button
ElevatedButton(
  onPressed: () async {
    // Simulate 10 network errors (will trigger anomaly detection)
    for (int i = 0; i < 10; i++) {
      await incidentLogger.logError(
        'Network timeout - API request failed',
        extra: {
          'error_type': 'network_timeout',
          'endpoint': '/api/users',
          'attempt': i + 1,
        },
      );
      await Future.delayed(Duration(milliseconds: 100));
    }
    
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('Sent 10 errors - check dashboard!')),
    );
  },
  child: Text('Simulate Network Errors'),
)
```

**Expected Result**:
- Backend detects error spike
- Reasoning agent analyzes: "Network connectivity issues"
- Actions taken: alert_oncall
- Dashboard shows CRITICAL incident

### Scenario 2: Simulate Payment Failure

```dart
ElevatedButton(
  onPressed: () async {
    await incidentLogger.logCritical(
      'Payment gateway timeout - transaction failed',
      extra: {
        'error_type': 'payment_timeout',
        'amount': 99.99,
        'gateway': 'stripe',
        'user_id': 'user_123',
        'order_id': 'ORD-${DateTime.now().millisecondsSinceEpoch}',
      },
    );
    
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('Payment error sent')),
    );
  },
  child: Text('Simulate Payment Error'),
)
```

---

## Common Issues & Solutions

### Issue 1: "Connection refused" or "Failed to send log"

**Problem**: Flutter app can't reach the backend

**Solutions**:

1. **Check if backend is running**:
   ```bash
   # In Terminal 1
   python main.py
   # Should show "Listening for logs on http://0.0.0.0:8888"
   ```

2. **Check your endpoint URL**:
   - Android Emulator: Use `http://10.0.2.2:8888`
   - iOS Simulator: Use `http://localhost:8888`
   - Real Device: Use your computer's IP like `http://192.168.1.100:8888`

3. **Find your computer's IP**:
   ```bash
   # Windows
   ipconfig
   # Look for IPv4 Address (e.g., 192.168.1.100)
   
   # Mac/Linux
   ifconfig | grep "inet "
   ```

4. **Test connectivity**:
   ```bash
   # From your terminal
   curl -X POST http://localhost:8888 -H "Content-Type: application/json" -d '{"test":"data"}'
   # Should work if backend is running
   ```

### Issue 2: Errors not showing in dashboard

**Problem**: Backend receives logs but dashboard doesn't update

**Solutions**:

1. **Check if interface is running**:
   ```bash
   # Terminal 2
   python client/dashboard.py watch 5
   ```

2. **Check storage directory exists**:
   ```bash
   # In pathwaycom-pathway folder
   ls output/  # Should see incidents.json
   ```

3. **Manually check incidents**:
   ```bash
   cd pathwaycom-llm-app
   python client/dashboard.py overview
   ```

### Issue 3: Flutter app crashes when logging

**Problem**: Logger causes app to freeze or crash

**Solution**: Make sure you're using `async`/`await` properly:

```dart
// ❌ WRONG - Blocks UI
incidentLogger.logError('Error');  

// ✅ CORRECT - Non-blocking
await incidentLogger.logError('Error');

// ✅ ALSO CORRECT - Fire and forget (even better)
incidentLogger.logError('Error').catchError((e) {
  print('Failed to log: $e');
});
```

### Issue 4: "Port 8888 already in use"

**Problem**: Another process is using port 8888

**Solutions**:

1. **Change the port**:
   ```dart
   // In incident_logger.dart
   endpoint: 'http://10.0.2.2:8889', // Use different port
   ```
   
   ```python
   # In pathwaycom-pathway/pipelines/log_stream.py
   port=8889  # Change to match
   ```

2. **Or kill the process**:
   ```bash
   # Windows
   netstat -ano | findstr :8888
   taskkill /PID <process_id> /F
   
   # Mac/Linux
   lsof -ti:8888 | xargs kill -9
   ```

---

## Complete VS Code Workspace Setup

### Save this as a workspace configuration

Create `.vscode/tasks.json` in your Flutter project:

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Start Incident Backend",
      "type": "shell",
      "command": "python",
      "args": ["main.py"],
      "options": {
        "cwd": "C:/Users/Jayaprakash/Desktop/IIT-M/pathwaycom-pathway"
      },
      "isBackground": true,
      "problemMatcher": []
    },
    {
      "label": "Start Dashboard",
      "type": "shell",
      "command": "python",
      "args": ["client/dashboard.py", "watch", "5"],
      "options": {
        "cwd": "C:/Users/Jayaprakash/Desktop/IIT-M/pathwaycom-llm-app"
      },
      "isBackground": true,
      "problemMatcher": []
    },
    {
      "label": "Start All Monitoring",
      "dependsOn": ["Start Incident Backend", "Start Dashboard"],
      "problemMatcher": []
    }
  ]
}
```

**To use**:
1. Press `Ctrl+Shift+P`
2. Type "Tasks: Run Task"
3. Select "Start All Monitoring"
4. Then run your Flutter app normally (F5 or `flutter run`)

---

## Quick Reference

### Starting Everything

```bash
# Terminal 1: Backend
cd pathwaycom-pathway
python main.py

# Terminal 2: Dashboard  
cd pathwaycom-llm-app
python client/dashboard.py watch 5

# Terminal 3: Flutter App
cd your-flutter-project
flutter run
```

### Testing Integration

```dart
// In your Flutter app - Add test button
ElevatedButton(
  onPressed: () async {
    await incidentLogger.logError('Test error');
  },
  child: Text('Send Test Error'),
)
```

### Checking Logs

```bash
# View incidents
cd pathwaycom-llm-app
python client/dashboard.py recent 24

# View specific incident
python client/dashboard.py details INC-20251226-001
```

---

## What Happens When You Log an Error

```
1. Flutter App
   └─> incidentLogger.logError('Payment failed')
       │
       ├─> HTTP POST to localhost:8888
       │
2. Backend (pathwaycom-pathway)
   └─> Receives log
       │
       ├─> Stores in Pathway table
       ├─> Checks for anomaly (error spike, high rate)
       │
       [IF ANOMALY DETECTED]
       │
       ├─> Observer Agent: "New incident detected"
       ├─> Reasoning Agent: "Payment gateway timeout - API credentials may be expired"
       ├─> Planning Agent: "Recommend: alert_oncall, restart_service"
       ├─> Action Agent: "Executing actions..."
       └─> Memory Agent: "Storing for future reference"
       │
3. Interface (pathwaycom-llm-app)
   └─> Reads incident from backend
       │
       ├─> Dashboard shows incident
       ├─> Can acknowledge/override
       └─> Can generate LLM explanation
```

---

## Next Steps

Once everything works:

1. **Add more error logging** to critical parts of your app
2. **Configure alerts** (PagerDuty, Slack) in the backend
3. **Customize anomaly thresholds** in `.env`
4. **Add monitoring** to your admin panel
5. **Test with real devices** using your network IP

---

## Getting Help

**If you're stuck:**

1. Check all terminals are running (3 terminals needed)
2. Verify endpoint URL matches where app is running
3. Test with `curl` to isolate issues
4. Check firewall isn't blocking port 8888
5. Look at terminal output for error messages

**Quick test command**:
```bash
curl -X POST http://localhost:8888 -H "Content-Type: application/json" -d '{"timestamp":"2025-12-26T10:30:00Z","level":"ERROR","service":"test","message":"Hello"}'
```

If this works, your backend is fine and the issue is in Flutter app configuration.

---

You're now monitoring your Flutter app with enterprise-grade incident response! 🚀
