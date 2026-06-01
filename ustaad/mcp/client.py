"""
USTAAD MCP Client Manager
Loads MCP servers from .ustaad/mcp.json and dynamically registers them as CrewAI tools.
"""

import os
import json
import asyncio
import threading
from typing import Dict, Any, List
from crewai.tools import BaseTool
from pydantic import Field
from rich.console import Console

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from contextlib import AsyncExitStack

console = Console()

class MCPToolWrapper(BaseTool):
    """Wraps an MCP Tool into a CrewAI BaseTool."""
    name: str = ""
    description: str = ""
    server_name: str = ""
    manager: Any = Field(exclude=True)
    
    def _run(self, **kwargs) -> Any:
        return self.manager.call_tool_sync(self.server_name, self.name, kwargs)

class MCPClientManager:
    def __init__(self, workspace: str):
        self.workspace = workspace
        self.config_path = os.path.join(workspace, ".ustaad", "mcp.json")
        self.servers: Dict[str, Dict[str, Any]] = {}
        self.sessions: Dict[str, ClientSession] = {}
        self.tools: List[BaseTool] = []
        self._stacks: Dict[str, AsyncExitStack] = {}
        
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._start_loop, daemon=True)
        self._thread.start()
        
    def _start_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _run_async(self, coro):
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result()

    def load_config(self):
        if not os.path.exists(self.config_path):
            # Create a default empty config if it doesn't exist
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, "w") as f:
                json.dump({
                    "mcpServers": {
                        "example_sqlite": {
                            "command": "uvx",
                            "args": ["mcp-server-sqlite", "--db-path", "test.db"]
                        }
                    }
                }, f, indent=2)
            return

        with open(self.config_path, "r") as f:
            try:
                data = json.load(f)
                self.servers = data.get("mcpServers", {})
            except Exception as e:
                console.print(f"[red]Error parsing {self.config_path}: {e}[/red]")

    def connect_all(self):
        self.load_config()
        if not self.servers:
            return
            
        for server_name, config in self.servers.items():
            if server_name == "example_sqlite":
                continue # Skip default example
            try:
                self._run_async(self._connect_server(server_name, config))
            except Exception as e:
                console.print(f"[red]Failed to connect to MCP server '{server_name}': {e}[/red]")

    async def _connect_server(self, name: str, config: dict):
        command = config.get("command")
        args = config.get("args", [])
        env = config.get("env", None)
        
        if env:
            # Merge with system env
            merged_env = os.environ.copy()
            merged_env.update(env)
            env = merged_env
        else:
            env = os.environ.copy()
            
        stack = AsyncExitStack()
        
        params = StdioServerParameters(command=command, args=args, env=env)
        stdio_transport = await stack.enter_async_context(stdio_client(params))
        read, write = stdio_transport
        
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        
        self.sessions[name] = session
        self._stacks[name] = stack
        
        # Fetch tools
        result = await session.list_tools()
        
        for tool in result.tools:
            tool_name_safe = f"{name}__{tool.name}".replace("-", "_")
            wrapper = MCPToolWrapper(
                name=tool_name_safe,
                description=f"[{name}] {tool.description or tool.name}\nArgs Schema: {json.dumps(tool.inputSchema)}",
                server_name=name,
                manager=self
            )
            self.tools.append(wrapper)
            
        console.print(f"[bold green]🔌 MCP Connected:[/bold green] '{name}' loaded {len(result.tools)} tools")

    def call_tool_sync(self, server_name: str, tool_name: str, arguments: dict) -> str:
        # Strip prefix if it exists
        prefix = f"{server_name}__"
        if tool_name.startswith(prefix):
            actual_tool_name = tool_name[len(prefix):]
        else:
            # Need to revert safe replacement
            actual_tool_name = tool_name.replace("_", "-") # basic approximation
            
        return self._run_async(self._call_tool_async(server_name, actual_tool_name, arguments))

    async def _call_tool_async(self, server_name: str, tool_name: str, arguments: dict) -> str:
        from ustaad.core.safety import get_safety_gate
        gate = get_safety_gate()
        if not gate.confirm_mcp_tool(server_name, tool_name, arguments):
            return f"[BLOCKED] User rejected MCP tool execution: {server_name}::{tool_name}"
            
        session = self.sessions.get(server_name)
        if not session:
            return f"Error: MCP Server {server_name} not found."
            
        try:
            result = await session.call_tool(tool_name, arguments)
            if result.isError:
                return f"MCP Error from {server_name}: {result.content}"
            
            texts = []
            for c in result.content:
                if c.type == "text":
                    texts.append(c.text)
            return "\n".join(texts)
        except Exception as e:
            return f"Error executing MCP tool {tool_name}: {e}"

    def stop_all(self):
        """Cleanup and close all connections."""
        async def _close():
            for name, stack in self._stacks.items():
                await stack.aclose()
        self._run_async(_close())
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=2.0)
