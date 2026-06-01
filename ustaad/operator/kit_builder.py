import os
import shutil
from rich.console import Console

console = Console()

def init_operator_kit(workspace: str = None) -> bool:
    """
    Initializes Ustaad Operator Kit in the current workspace directory.
    Creates .ustaad-kit structure, copies templates, and installs git hooks.
    """
    workspace = workspace or os.getcwd()
    kit_dir = os.path.join(workspace, ".ustaad-kit")
    
    # 1. Establish directories
    dirs = {
        "rules": os.path.join(kit_dir, "rules"),
        "hooks": os.path.join(kit_dir, "hooks"),
        "skills": os.path.join(kit_dir, "skills"),
    }
    
    for name, path in dirs.items():
        os.makedirs(path, exist_ok=True)

    # 2. Source template location
    template_src = os.path.join(os.path.dirname(__file__), "templates")
    if not os.path.isdir(template_src):
        console.print("[bold red]✗ Operator Kit templates source directory missing.[/bold red]")
        return False

    templates_to_copy = [
        ("coding_rules.md", os.path.join(dirs["rules"], "coding_rules.md")),
        ("safety_rules.md", os.path.join(dirs["rules"], "safety_rules.md")),
        ("git_pre_commit", os.path.join(dirs["hooks"], "pre-commit")),
        ("operator_guide.md", os.path.join(kit_dir, "operator_guide.md")),
        ("setup.sh", os.path.join(kit_dir, "setup.sh")),
        ("setup.ps1", os.path.join(kit_dir, "setup.ps1")),
    ]

    # 3. Copy files
    for src_name, dest_path in templates_to_copy:
        src_path = os.path.join(template_src, src_name)
        if os.path.isfile(src_path):
            try:
                shutil.copy2(src_path, dest_path)
            except Exception as e:
                console.print(f"[yellow]  ⚠ Failed to copy {src_name}: {e}[/yellow]")

    console.print("[bold green]✓ Created .ustaad-kit structure, rules, and rulesets successfully.[/bold green]")

    # 4. Try to register Git pre-commit hook automatically
    git_hooks_dir = os.path.join(workspace, ".git", "hooks")
    if os.path.isdir(git_hooks_dir):
        dest_hook_path = os.path.join(git_hooks_dir, "pre-commit")
        try:
            shutil.copy2(os.path.join(dirs["hooks"], "pre-commit"), dest_hook_path)
            # Make it executable
            try:
                os.chmod(dest_hook_path, 0o755)
            except AttributeError:
                pass # os.chmod on Windows doesn't fully support POSIX octal modes, but copy works
            console.print("[bold green]✓ Registered Ustaad Secure Pre-Commit Git Hook successfully.[/bold green]")
        except Exception as e:
            console.print(f"[yellow]  ⚠ Failed to copy git hook directly: {e}[/yellow]")
    else:
        console.print("[dim]   Git repository hooks directory not found. Git hook templates are located under .ustaad-kit/hooks/.[/dim]")

    # Copy standard readme/guide to workspace root for user awareness
    guide_dest = os.path.join(workspace, "USTAAD_OPERATOR.md")
    if not os.path.exists(guide_dest):
        try:
            shutil.copy2(os.path.join(kit_dir, "operator_guide.md"), guide_dest)
            console.print("[bold green]✓ Drop-in USTAAD_OPERATOR.md guide created in workspace root![/bold green]")
        except Exception:
            pass

    return True
