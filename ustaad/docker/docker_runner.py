"""
USTAAD Isolated Docker & Container Sandbox Engine

This module provides a fully isolated execution sandbox using local Docker
containers. It runs volatile terminal commands, tests, or scripts inside a secure,
resource-limited container environment to safeguard the host operating system.
If Docker is not running, it falls back gracefully to host execution with standard
safety-gate protection.
"""

import os
import subprocess
import time
from rich.console import Console

console = Console()


class DockerSandbox:
    """
    Manages the Docker container sandbox environment for Ustaad.
    Mounts the active workspace and executes commands safely.
    """

    def __init__(self, workspace: str = None, image: str = "python:3.11-slim"):
        self.workspace = os.path.abspath(workspace or os.getcwd())
        self.image = image
        self._client = None
        self._docker_available = None

    @property
    def is_available(self) -> bool:
        """
        Check if the Docker daemon is online and accessible.
        Caches the result to avoid recurring handshake latency.
        """
        if self._docker_available is not None:
            return self._docker_available

        try:
            # Lazy import docker to avoid high CLI startup latency
            import docker
            self._client = docker.from_env()
            self._client.ping()
            self._docker_available = True
        except Exception:
            self._docker_available = False
            self._client = None
            
        return self._docker_available

    def run(self, command: str, timeout: int = 120) -> dict:
        """
        Runs a command inside the isolated container sandbox.
        If Docker is unavailable, falls back gracefully to a gated host subprocess.
        """
        if not self.is_available:
            return self._run_host_fallback(command, timeout)

        try:
            # Prepare mount details
            # Normalize pathing for Windows / POSIX hosts
            bind_path = "/workspace"
            volumes = {
                self.workspace: {
                    "bind": bind_path,
                    "mode": "rw"
                }
            }

            # Inject execution script to change directory to /workspace and run the command
            exec_command = f"sh -c 'cd {bind_path} && {command}'"

            # Create container and execute
            container = self._client.containers.create(
                image=self.image,
                command=exec_command,
                volumes=volumes,
                network_mode="none", # Strict isolation: block all external network access
                mem_limit="1g",      # Safe memory boundary to prevent swap exhaustion
                nano_cpus=1000000000, # Max 1 CPU core allocation
                working_dir=bind_path
            )

            container.start()
            
            # Wait for execution with timeout
            start_time = time.time()
            status = container.wait(timeout=timeout)
            duration = time.time() - start_time

            # Retrieve logs
            stdout = container.logs(stdout=True, stderr=False).decode("utf-8", errors="ignore")
            stderr = container.logs(stdout=False, stderr=True).decode("utf-8", errors="ignore")
            
            container.remove(force=True)

            return {
                "stdout": stdout,
                "stderr": stderr,
                "returncode": status.get("StatusCode", 0),
                "sandbox": True,
                "duration": duration
            }

        except Exception as e:
            console.print(f"[yellow]   ⚠ Docker execution failure: {e}. Falling back to host subprocess.[/yellow]")
            return self._run_host_fallback(command, timeout)

    def _run_host_fallback(self, command: str, timeout: int) -> dict:
        """Fallback executor on the host machine."""
        try:
            result = subprocess.run(
                command,
                shell=True,
                text=True,
                capture_output=True,
                timeout=timeout,
                cwd=self.workspace
            )
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "sandbox": False
            }
        except subprocess.TimeoutExpired:
            return {
                "stdout": "",
                "stderr": f"Error: Command timed out after {timeout}s",
                "returncode": -1,
                "sandbox": False
            }
        except Exception as e:
            return {
                "stdout": "",
                "stderr": f"Error: Local subprocess failure: {str(e)}",
                "returncode": -1,
                "sandbox": False
            }
