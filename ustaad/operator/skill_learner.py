import os
import re
from rich.console import Console

console = Console()

def learn_reusable_skill(skill_name: str, description: str, workspace: str = None) -> bool:
    """
    Spins up the LLM to write a complete, valid CrewAI Python tool (skill),
    compiles it, and registers it dynamically into .ustaad/plugins/.
    """
    workspace = workspace or os.getcwd()
    plugins_dir = os.path.join(workspace, ".ustaad", "plugins")
    os.makedirs(plugins_dir, exist_ok=True)
    
    # 1. Clean the skill name for valid Python naming conventions
    clean_name = re.sub(r'[^a-zA-Z0-9_]', '_', skill_name).lower()
    if not clean_name[0].isalpha():
        clean_name = "skill_" + clean_name

    skill_filepath = os.path.join(plugins_dir, f"{clean_name}.py")
    
    console.print(f"[bold cyan]🤖 Synthesizing new skill module: {clean_name}.py...[/bold cyan]")
    console.print(f"   [dim]Goal: {description}[/dim]\n")
    
    # 2. Design the prompt to the LLM to output ONLY raw Python containing a CrewAI tool
    prompt = f"""
    You are USTAAD's Skill Synthesis Engine.
    Your task is to generate a fully complete, self-contained Python file that defines a valid CrewAI tool named '{clean_name}'.
    
    The tool description is:
    "{description}"
    
    RULES:
    1. Import the necessary modules. Always import `tool` decorator: `from crewai.tools import tool`
    2. Write the decorated function `@tool("{clean_name}")`.
    3. Include complete Python type hints for all parameters and return values.
    4. Write a detailed docstring within the function describing exactly what it does, because the agent's planner uses this docstring to understand how to call it.
    5. Implement proper error handling inside the function (use try-except blocks so it never crashes Ustaad).
    6. Return a string result summarizing the action.
    7. Output ONLY raw executable Python code. Do NOT enclose the code inside markdown code blocks (e.g. no ```python) and do NOT write any conversational text before or after the code.
    
    Example Structure:
    from crewai.tools import tool

    @tool("{clean_name}")
    def {clean_name}(param1: str) -> str:
        \"\"\"
        Detailed description of what the tool does.
        \"\"\"
        try:
            # logic here
            return f"Success: processed {{param1}}"
        except Exception as e:
            return f"Error: {{str(e)}}"
    """

    # 3. Call the model
    try:
        from ustaad.llm import load_model_for_role_and_complexity
        model = load_model_for_role_and_complexity(role="coder", complexity="standard")
        # Run prompt
        res = model.invoke(prompt)
        content = str(res.content if hasattr(res, "content") else res).strip()
        
        # Clean any accidental markdown block wrappers
        if content.startswith("```python"):
            content = content[9:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        # 4. Programmatic Syntax Check (Compile)
        try:
            compile(content, f"<dynamic_skill_{clean_name}>", "exec")
        except SyntaxError as se:
            console.print(f"[bold red]✗ Syntax check failed for synthesized tool code:[/bold red] {se}")
            # Log the code for debugging
            console.print(f"\n[dim]{content}[/dim]\n")
            return False

        # 5. Write to plugin directory
        with open(skill_filepath, "w", encoding="utf-8") as f:
            f.write(content)

        console.print(f"[bold green]✓ Synthesized skill saved: .ustaad/plugins/{clean_name}.py[/bold green]")
        
        # 6. Dynamically trigger reload on active context
        from ustaad.cli import cmd_reload_plugins
        cmd_reload_plugins()
        
        return True
    except Exception as e:
        console.print(f"[bold red]✗ Skill synthesis failed:[/bold red] {e}")
        return False
