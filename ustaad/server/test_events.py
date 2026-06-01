import time
import requests

def send_event(event_type, node_id, agent, status, payload):
    data = {
        "workflow_id": "session_1",
        "event_type": event_type,
        "node_id": node_id,
        "agent": agent,
        "status": status,
        "payload": payload
    }
    requests.post("http://localhost:8000/api/events", json=data)
    print(f"Sent: {event_type} - {node_id} ({status})")

print("Starting demo sequence...")
time.sleep(2)

send_event("TASK_RECEIVED", "user_input", "System", "COMPLETED", {"task": "Research latest Quantum Computing papers and write a summary"})
time.sleep(1)

send_event("PLAN_CREATED", "planning_node", "Coordinator", "RUNNING", {"parent_id": "user_input"})
time.sleep(2)
send_event("PLAN_CREATED", "planning_node", "Coordinator", "COMPLETED", {"parent_id": "user_input"})
time.sleep(0.5)

send_event("WEB_SEARCH_STARTED", "search_node", "ResearchAgent", "RUNNING", {"parent_id": "planning_node"})
time.sleep(3)
send_event("WEB_SEARCH_COMPLETED", "search_node", "ResearchAgent", "COMPLETED", {"parent_id": "planning_node"})
time.sleep(1)

send_event("CODE_EXECUTED", "code_node", "CodingAgent", "RUNNING", {"parent_id": "search_node"})
time.sleep(4)
send_event("CODE_EXECUTED", "code_node", "CodingAgent", "COMPLETED", {"parent_id": "search_node"})
time.sleep(0.5)

send_event("RESPONSE_GENERATED", "output_node", "Coordinator", "COMPLETED", {"parent_id": "code_node"})
print("Demo complete!")
