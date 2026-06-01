'use client';

import React, { useEffect, useState, useCallback } from 'react';
import ReactFlow, { Background, Controls, applyNodeChanges, applyEdgeChanges, addEdge, Node, Edge } from 'reactflow';
import 'reactflow/dist/style.css';
import { Activity, Code, Globe, Database, Terminal } from 'lucide-react';

const initialNodes: Node[] = [
  {
    id: 'user_input',
    type: 'default',
    position: { x: 250, y: 50 },
    data: { label: 'Waiting for task...' },
    style: { background: '#1e293b', color: '#fff', border: '1px solid #334155', borderRadius: '8px', padding: '10px' }
  }
];

const initialEdges: Edge[] = [];

export default function WorkflowDashboard() {
  const [nodes, setNodes] = useState<Node[]>(initialNodes);
  const [edges, setEdges] = useState<Edge[]>(initialEdges);
  const [isConnected, setIsConnected] = useState(false);
  const [logs, setLogs] = useState<string[]>([]);

  useEffect(() => {
    // Generate a session ID or get it from URL
    const workflowId = 'session_1';
    const ws = new WebSocket(`ws://localhost:8000/ws/workflow/${workflowId}`);

    ws.onopen = () => setIsConnected(true);
    ws.onclose = () => setIsConnected(false);

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleEvent(data);
      } catch (e) {
        console.error("Error parsing WS message", e);
      }
    };

    return () => ws.close();
  }, []);

  const handleEvent = useCallback((event: any) => {
    setLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] ${event.agent} | ${event.status}: ${event.event_type}`]);
    
    if (event.event_type === 'TASK_RECEIVED') {
      setNodes([{
        id: 'user_input',
        position: { x: 250, y: 50 },
        data: { label: `Task: ${event.payload.task}` },
        style: { background: '#10b981', color: '#fff', border: '1px solid #059669', borderRadius: '8px', padding: '10px' }
      }]);
      return;
    }

    setNodes((nds) => {
      const nodeExists = nds.find(n => n.id === event.node_id);
      
      let bgColor = '#1e293b';
      let borderColor = '#334155';
      if (event.status === 'RUNNING') { bgColor = '#3b82f6'; borderColor = '#2563eb'; }
      else if (event.status === 'COMPLETED') { bgColor = '#10b981'; borderColor = '#059669'; }
      else if (event.status === 'FAILED') { bgColor = '#ef4444'; borderColor = '#dc2626'; }

      if (nodeExists) {
        return nds.map(n => n.id === event.node_id ? {
          ...n,
          style: { ...n.style, background: bgColor, borderColor }
        } : n);
      } else {
        // Create new node below the previous one
        const yPos = nds.length * 100 + 50;
        return [...nds, {
          id: event.node_id,
          position: { x: 250, y: yPos },
          data: { label: `${event.agent}: ${event.node_id}` },
          style: { background: bgColor, color: '#fff', border: `1px solid ${borderColor}`, borderRadius: '8px', padding: '10px' }
        }];
      }
    });

    setEdges((eds) => {
      if (event.payload.parent_id) {
        const edgeId = `e-${event.payload.parent_id}-${event.node_id}`;
        if (!eds.find(e => e.id === edgeId)) {
          return [...eds, {
            id: edgeId,
            source: event.payload.parent_id,
            target: event.node_id,
            animated: event.status === 'RUNNING',
            style: { stroke: '#94a3b8' }
          }];
        }
      }
      return eds.map(e => e.target === event.node_id ? { ...e, animated: event.status === 'RUNNING' } : e);
    });
  }, []);

  const onNodesChange = useCallback((changes: any) => setNodes((nds) => applyNodeChanges(changes, nds)), []);
  const onEdgesChange = useCallback((changes: any) => setEdges((eds) => applyEdgeChanges(changes, eds)), []);

  return (
    <div className="flex h-screen bg-slate-950 text-slate-200">
      <div className="flex-1 flex flex-col p-4">
        <header className="flex justify-between items-center mb-4">
          <h1 className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-emerald-400">
            Ustaad AI Workflow Visualizer
          </h1>
          <div className="flex items-center gap-2">
            <span className="text-sm text-slate-400">Backend Status:</span>
            <div className={`w-3 h-3 rounded-full ${isConnected ? 'bg-emerald-500' : 'bg-red-500'}`} />
            <span className="text-sm font-mono">{isConnected ? 'Connected' : 'Disconnected'}</span>
          </div>
        </header>

        <div className="flex-1 rounded-xl overflow-hidden border border-slate-800 shadow-2xl relative">
          <ReactFlow 
            nodes={nodes} 
            edges={edges} 
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            fitView 
          >
            <Background color="#334155" gap={16} />
            <Controls className="bg-slate-800 border-slate-700 fill-slate-300" />
          </ReactFlow>
        </div>

        <div className="h-48 mt-4 bg-slate-900 border border-slate-800 rounded-xl p-4 overflow-y-auto font-mono text-sm">
          <h3 className="text-slate-400 mb-2 uppercase text-xs font-bold tracking-wider">Execution Timeline</h3>
          {logs.map((log, i) => (
            <div key={i} className="text-slate-300 mb-1">{log}</div>
          ))}
        </div>
      </div>
    </div>
  );
}
