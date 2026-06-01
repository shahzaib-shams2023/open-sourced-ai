"""
USTAAD Telemetry Dashboard
Provides a simple HTTP server to visualize agent telemetry.
"""
import os
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
import json

class DashboardHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            html = """
            <!DOCTYPE html>
            <html>
            <head><title>USTAAD Telemetry</title></head>
            <body style="font-family: sans-serif; background: #111; color: #eee; padding: 20px;">
                <h1>USTAAD Agent Telemetry</h1>
                <div id="stats">Loading...</div>
                <script>
                    fetch('/api/stats')
                        .then(r => r.json())
                        .then(d => {
                            document.getElementById('stats').innerHTML = 
                                '<pre>' + JSON.stringify(d, null, 2) + '</pre>';
                        });
                </script>
            </body>
            </html>
            """
            self.wfile.write(html.encode('utf-8'))
        elif self.path == '/api/stats':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            # Read from audit logs or just mock
            workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            audit_path = os.path.join(workspace, ".ustaad", "audit.jsonl")
            events = 0
            if os.path.exists(audit_path):
                with open(audit_path, "r") as f:
                    events = len(f.readlines())
                    
            data = {
                "status": "online",
                "total_events": events,
                "version": "3.0"
            }
            self.wfile.write(json.dumps(data).encode('utf-8'))
        else:
            self.send_error(404)

class TelemetryDashboard:
    def __init__(self, port: int = 8080):
        self.port = port
        self.server = None
        self.thread = None
        
    def start(self):
        if self.server:
            return
            
        self.server = HTTPServer(('localhost', self.port), DashboardHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        
    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server = None
