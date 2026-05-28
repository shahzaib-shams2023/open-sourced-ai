"""
USTAAD Core Plugin & Dynamic Skill Loader System

This module allows Ustaad to dynamically load, compile, register, and validate
new capabilities and tools at runtime. This provides a self-extending operating
environment where the system can synthesize a new tool in Python, compile it,
verify it, and register it directly into the active agents without restarts.
"""

import os
import sys
import importlib.util
import inspect
from pathlib import Path
from typing import Dict, List, Any
from crewai.tools import tool, BaseTool
from rich.console import Console

console = Console()


class PluginSystem:
    """
    Manages dynamic loading of plugins, tools, and extensions in Ustaad.
    Plugins are stored in `.ustaad/plugins/` as modular Python files.
    """

    def __init__(self, workspace: str = None):
        self.workspace = os.path.abspath(workspace or os.getcwd())
        self.plugin_dir = os.path.join(self.workspace, ".ustaad", "plugins")
        os.makedirs(self.plugin_dir, exist_ok=True)
        self._loaded_plugins: Dict[str, Dict[str, Any]] = {}
        self._loaded_tools: Dict[str, BaseTool] = {}

    @property
    def loaded_plugins(self) -> Dict[str, Dict[str, Any]]:
        return self._loaded_plugins

    @property
    def loaded_tools(self) -> Dict[str, BaseTool]:
        return self._loaded_tools

    def load_all_plugins(self) -> int:
        """
        Scan `.ustaad/plugins/` and load all valid Python modules.
        Returns the count of successfully loaded plugins.
        """
        if not os.path.exists(self.plugin_dir):
            return 0

        loaded_count = 0
        for file in Path(self.plugin_dir).glob("*.py"):
            if file.name.startswith("__"):
                continue
            plugin_name = file.stem
            try:
                if self.load_plugin(plugin_name):
                    loaded_count += 1
            except Exception as e:
                console.print(f"[bold red]✗ Failed to load plugin '{plugin_name}':[/bold red] {e}")

        return loaded_count

    def load_plugin(self, plugin_name: str) -> bool:
        """
        Dynamically load a single python file as a module and extract all tools.
        """
        plugin_path = os.path.join(self.plugin_dir, f"{plugin_name}.py")
        if not os.path.isfile(plugin_path):
            plugin_path = os.path.join(self.workspace, plugin_name)
            if not os.path.isfile(plugin_path):
                raise FileNotFoundError(f"Plugin file not found: {plugin_name}")

        module_name = f"ustaad.dynamic_plugins.{plugin_name}"
        
        # Load and execute the module in a private namespace
        spec = importlib.util.spec_from_file_location(module_name, plugin_path)
        if spec is None or spec.loader is None:
            return False
            
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        
        try:
            spec.loader.exec_module(module)
        except Exception as e:
            # Clean up on failure
            if module_name in sys.modules:
                del sys.modules[module_name]
            raise e

        # Extract tools from the module
        extracted_tools = []
        
        # Look for objects that are subclasses of BaseTool or decorated with @tool
        for name, obj in inspect.getmembers(module):
            # Check if it's a CrewAI BaseTool subclass (or instance of BaseTool)
            is_crewai_tool = False
            if isinstance(obj, BaseTool):
                is_crewai_tool = True
            elif inspect.isclass(obj) and issubclass(obj, BaseTool) and obj != BaseTool:
                try:
                    obj = obj()  # Try to instantiate the tool class
                    is_crewai_tool = True
                except Exception:
                    pass

            if is_crewai_tool:
                tool_name = getattr(obj, "name", name)
                self._loaded_tools[tool_name] = obj
                extracted_tools.append(obj)
                
        if extracted_tools:
            self._loaded_plugins[plugin_name] = {
                "module": module,
                "path": plugin_path,
                "tools": extracted_tools,
                "loaded_at": inspect.getfile(module) if hasattr(module, "__file__") else plugin_path
            }
            return True
            
        # If no tools were found, clean up the imported module
        if module_name in sys.modules:
            del sys.modules[module_name]
        return False

    def register_tool(self, tool_instance: BaseTool) -> bool:
        """Register a single pre-existing tool instance dynamically."""
        if isinstance(tool_instance, BaseTool):
            self._loaded_tools[tool_instance.name] = tool_instance
            return True
        return False

    def get_all_tools(self) -> List[BaseTool]:
        """Return a list of all loaded tools across all plugins."""
        return list(self._loaded_tools.values())

    def unload_plugin(self, plugin_name: str) -> bool:
        """Unload a loaded plugin and remove its tools from the registry."""
        if plugin_name not in self._loaded_plugins:
            return False

        plugin_data = self._loaded_plugins[plugin_name]
        for t in plugin_data["tools"]:
            if t.name in self._loaded_tools:
                del self._loaded_tools[t.name]

        module_name = f"ustaad.dynamic_plugins.{plugin_name}"
        if module_name in sys.modules:
            del sys.modules[module_name]

        del self._loaded_plugins[plugin_name]
        return True
