import json
import threading
import uuid
import datetime
import urllib.request
import urllib.error

DASHBOARD_URL = "http://localhost:8000/api/events"

class EventSystem:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.workflow_id = str(uuid.uuid4())
            cls._instance.enabled = False
        return cls._instance

    def enable(self):
        self.enabled = True
        
    def disable(self):
        self.enabled = False

    def emit(self, event_type: str, node_id: str, agent: str, status: str, payload: dict):
        if not self.enabled:
            return
            
        data = {
            "workflow_id": self.workflow_id,
            "event_type": event_type,
            "node_id": node_id,
            "agent": agent,
            "status": status,
            "payload": payload
        }
        
        # Send non-blocking
        threading.Thread(target=self._send_event, args=(data,), daemon=True).start()
        
    def _send_event(self, data: dict):
        try:
            req = urllib.request.Request(
                DASHBOARD_URL,
                data=json.dumps(data).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )
            urllib.request.urlopen(req, timeout=1)
        except Exception:
            pass # Ignore errors if dashboard is not running

# Global instance
event_bus = EventSystem()
