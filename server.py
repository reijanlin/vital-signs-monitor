"""
Complete Vital Signs Server with Medical History Recording System
"""

from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
import json
import time
import os
from datetime import datetime
from collections import deque
import threading

app = Flask(__name__)
app.config['SECRET_KEY'] = 'vital_signs_secret_key_2024'
socketio = SocketIO(app, cors_allowed_origins="*")

# Global data storage for live monitoring
vital_signs_data = {
    'bpm': 0,
    'bpm_status': 'Not Connected',
    'spo2': 0,
    'spo2_status': 'Not Connected',
    'respiration_rate': 0,
    'rr_status': 'Not Connected',
    'temperature_c': 0,
    'temperature_f': 0,
    'temp_status': 'Not Connected',
    'signal_quality': 'No Signal',
    'camera_status': 'Not Active',
    'monitoring_status': 'STOPPED',
    'last_update': datetime.now().isoformat(),
    'connection_status': 'Disconnected'
}

# Historical data for charts (keep last 100 readings)
historical_data = {
    'bpm': deque(maxlen=100),
    'spo2': deque(maxlen=100),
    'respiration_rate': deque(maxlen=100),
    'temperature': deque(maxlen=100),
    'timestamps': deque(maxlen=100)
}

# Medical Vitals History Storage (permanent medical records)
vitals_history = []  # Store all medical history records
HISTORY_FILE = 'vitals_history.json'

# Connection monitoring
last_data_received = 0
CONNECTION_TIMEOUT = 10  # seconds

def load_vitals_history():
    """Load existing vitals history from file"""
    global vitals_history
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r') as f:
                vitals_history = json.load(f)
            print(f"Loaded {len(vitals_history)} existing medical records")
        else:
            vitals_history = []
            print("No existing medical records found - starting fresh")
    except Exception as e:
        print(f"Error loading vitals history: {e}")
        vitals_history = []

def save_vitals_history():
    """Save vitals history to file"""
    try:
        with open(HISTORY_FILE, 'w') as f:
            json.dump(vitals_history, f, indent=2)
        print(f"Saved {len(vitals_history)} medical records to {HISTORY_FILE}")
    except Exception as e:
        print(f"Error saving vitals history: {e}")

def monitor_connection():
    """Monitor connection status"""
    global last_data_received
    while True:
        current_time = time.time()
        if current_time - last_data_received > CONNECTION_TIMEOUT:
            vital_signs_data['connection_status'] = 'Disconnected'
            vital_signs_data['monitoring_status'] = 'DISCONNECTED'
        time.sleep(5)

# Load existing history and start connection monitor
load_vitals_history()
connection_thread = threading.Thread(target=monitor_connection, daemon=True)
connection_thread.start()

@app.route('/')
def dashboard():
    """Main dashboard page"""
    return render_template('dashboard.html')

@app.route('/api/vital_signs', methods=['GET'])
def get_vital_signs():
    """Get current vital signs data"""
    return jsonify(vital_signs_data)

@app.route('/api/vital_signs', methods=['POST'])
def receive_vital_signs():
    """Receive live vital signs data from monitoring device"""
    global last_data_received
    
    try:
        data = request.get_json()
        
        # Update live vital signs data
        vital_signs_data.update({
            'bpm': data.get('bpm', 0),
            'bpm_status': data.get('bpm_status', 'Unknown'),
            'spo2': data.get('spo2', 0),
            'spo2_status': data.get('spo2_status', 'Unknown'),
            'respiration_rate': data.get('respiration_rate', 0),
            'rr_status': data.get('rr_status', 'Unknown'),
            'temperature_c': data.get('temperature_c', 0),
            'temperature_f': data.get('temperature_f', 0),
            'temp_status': data.get('temp_status', 'Unknown'),
            'signal_quality': data.get('signal_quality', 'Unknown'),
            'camera_status': data.get('camera_status', 'Unknown'),
            'monitoring_status': data.get('monitoring_status', 'Unknown'),
            'last_update': datetime.now().isoformat(),
            'connection_status': 'Connected'
        })
        
        # Add to historical data for charts
        current_time = datetime.now().isoformat()
        historical_data['bpm'].append(data.get('bpm', 0))
        historical_data['spo2'].append(data.get('spo2', 0))
        historical_data['respiration_rate'].append(data.get('respiration_rate', 0))
        historical_data['temperature'].append(data.get('temperature_c', 0))
        historical_data['timestamps'].append(current_time)
        
        last_data_received = time.time()
        
        # Emit to all connected clients via WebSocket
        socketio.emit('vital_signs_update', vital_signs_data)
        
        return jsonify({'status': 'success', 'message': 'Data received'})
        
    except Exception as e:
        print(f"Error receiving data: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 400

@app.route('/api/vitals_history', methods=['POST'])
def receive_vitals_history():
    """Receive and store medical vitals history record"""
    try:
        medical_record = request.get_json()
        
        # Add timestamp if not present
        if 'timestamp' not in medical_record:
            medical_record['timestamp'] = datetime.now().isoformat()
        
        # Add record to history
        vitals_history.append(medical_record)
        
        # Save to file immediately
        save_vitals_history()
        
        print(f"📋 Medical Record Saved - {medical_record['trigger_type'].upper()}: "
              f"bpm={medical_record['vital_signs']['heart_rate_bpm']}, "
              f"SpO2={medical_record['vital_signs']['spo2_percent']}%, "
              f"RR={medical_record['vital_signs']['respiration_rate_bpm']}, "
              f"Temp={medical_record['vital_signs']['temperature_celsius']}°C")
        
        # Emit to connected clients
        socketio.emit('new_vitals_record', medical_record)
        
        return jsonify({'status': 'success', 'message': 'Medical record saved', 'record_id': medical_record.get('record_id')})
        
    except Exception as e:
        print(f"Error receiving medical record: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 400

@app.route('/api/vitals_history', methods=['GET'])
def get_vitals_history():
    """Get medical vitals history with optional filtering"""
    try:
        # Get query parameters for filtering
        limit = request.args.get('limit', type=int)
        patient_id = request.args.get('patient_id')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # Filter records
        filtered_records = vitals_history.copy()
        
        if patient_id:
            filtered_records = [r for r in filtered_records if r.get('patient_id') == patient_id]
        
        if start_date:
            filtered_records = [r for r in filtered_records if r.get('timestamp', '') >= start_date]
        
        if end_date:
            filtered_records = [r for r in filtered_records if r.get('timestamp', '') <= end_date]
        
        # Sort by timestamp (newest first)
        filtered_records = sorted(filtered_records, key=lambda x: x.get('timestamp', ''), reverse=True)
        
        # Limit results
        if limit:
            filtered_records = filtered_records[:limit]
        
        return jsonify({
            'records': filtered_records,
            'total_count': len(vitals_history),
            'filtered_count': len(filtered_records)
        })
        
    except Exception as e:
        print(f"Error retrieving vitals history: {e}")
        return jsonify({'records': [], 'error': str(e), 'total_count': 0, 'filtered_count': 0}), 500

@app.route('/api/test', methods=['POST'])
def create_test_record():
    """Create a test medical record (for debugging)"""
    try:
        test_record = {
            'patient_id': 'test_patient',
            'record_id': f"test_record_{int(time.time())}",
            'timestamp': datetime.now().isoformat(),
            'trigger_type': 'test',
            'trigger_reason': 'Manual test record via API',
            'vital_signs': {
                'heart_rate_bpm': 75,
                'heart_rate_status': 'Normal',
                'spo2_percent': 98.0,
                'spo2_status': 'Normal',
                'respiration_rate_bpm': 16.0,
                'respiration_status': 'Normal',
                'temperature_celsius': 36.5,
                'temperature_fahrenheit': 97.7,
                'temperature_status': 'Normal'
            },
            'system_status': {
                'signal_quality': 'Good Signal',
                'camera_status': 'Active',
                'monitoring_status': 'ACTIVE',
                'device_id': 'test_device'
            }
        }
        
        vitals_history.append(test_record)
        save_vitals_history()
        
        # Emit to connected clients
        socketio.emit('new_vitals_record', test_record)
        
        return jsonify({'status': 'success', 'message': 'Test record created', 'record': test_record})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    print('Client connected to dashboard')
    emit('vital_signs_update', vital_signs_data)
    # Send recent medical records
    recent_records = sorted(vitals_history, key=lambda x: x.get('timestamp', ''), reverse=True)[:10]
    emit('vitals_history_update', recent_records)

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    print('Client disconnected from dashboard')

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    os.makedirs('templates', exist_ok=True)
    
    port = int(os.environ.get('PORT', 5000))
    
    print("=" * 60)
    print("Vital Signs Medical History Server")
    print("=" * 60)
    print("Server starting...")
    print(f"Dashboard will be available at: http://localhost:{port}")
    print("API endpoints:")
    print(f"  - Live data: http://localhost:{port}/api/vital_signs")
    print(f"  - Medical history: http://localhost:{port}/api/vitals_history")
    print(f"  - Test record: http://localhost:{port}/api/test (POST)")
    print(f"Medical records will be saved to: {HISTORY_FILE}")
    print(f"Currently stored records: {len(vitals_history)}")
    print("Press Ctrl+C to stop the server")
    print("=" * 60)
    
    # Run the server
    socketio.run(app, host='0.0.0.0', port=port, debug=False)
