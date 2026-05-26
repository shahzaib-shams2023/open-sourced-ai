import os
from dotenv import load_dotenv
load_dotenv()
os.environ.setdefault("OPENAI_API_KEY", "na")

from crewai import Task, Crew

from ustaad.agents.planner import planner
from ustaad.agents.coder import coder
from ustaad.agents.reviewer import reviewer
from ustaad.agents.researcher import researcher

from ustaad.tools.memory_tools import (
    save_memory,
    search_memory
)

from ustaad.tools.shell_tools import (
    run_command
)

from ustaad.tools.file_tools import (
    write_file
)


def run_task(user_prompt, workspace=None):

    print("\nUSTAAD AI OS\n")

    if workspace:
        print(f"Workspace: {workspace}\n")

    # Search previous memory
    memory_results = search_memory(user_prompt)

    print("\nMemory Context:")
    print(memory_results)

    # Git status
    git_status = run_command("git status")

    print("\nGit Status:")
    print(git_status["stdout"])

    # Generate workspace file listing to provide initial context to the planner agent
    workspace_context = ""
    if workspace and os.path.exists(workspace):
        try:
            files_list = []
            for root, dirs, files in os.walk(workspace):
                # Prune unwanted directories in place
                dirs[:] = [d for d in dirs if d not in ['.git', 'venv', 'node_modules', '__pycache__', 'memory', 'artifacts']]
                for file in files:
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, workspace)
                    files_list.append(rel_path)
            
            if files_list:
                workspace_context = "Existing files in workspace:\n- " + "\n- ".join(files_list[:100])
                if len(files_list) > 100:
                    workspace_context += "\n- ... (and more files exist)"
            else:
                workspace_context = "Workspace is currently empty."
        except Exception as e:
            workspace_context = f"Error listing workspace files: {str(e)}"

    # Planning Task
    planning_task = Task(
        description=f"""
        Analyze the workspace and create a detailed implementation plan for:

        {user_prompt}

        Current workspace path:
        {workspace}

        {workspace_context}
        """,

        expected_output="""
        A clear, step-by-step technical plan detailing what files to create or modify to accomplish the goal.
        """,

        agent=planner
    )

    # Coding Task
    coding_task = Task(
        description=f"""
        Implement the changes required to fulfill the following goal:

        {user_prompt}

        Follow the design guidelines and technical plan provided by the Project Planner. Read the necessary files, then write complete, clean, and production-ready code.
        """,

        expected_output="""
        Production-ready implementation with all requested changes applied.
        """,

        agent=coder,
        context=[planning_task]
    )

    # Review Task
    review_task = Task(
        description="""
        Review the changes made by the Software Engineer to ensure they are fully operational and production-grade.

        Check for:
        - bugs
        - security vulnerabilities
        - scalability and performance
        """,

        expected_output="""
        Detailed technical review and confirmation of correctness.
        """,

        agent=reviewer,
        context=[coding_task]
    )

    # Create Crew
    crew = Crew(
        agents=[
            planner,
            coder,
            reviewer,
            researcher
        ],

        tasks=[
            planning_task,
            coding_task,
            review_task
        ],

        verbose=True
    )

    # Run Crew
    result = crew.kickoff()

    # Save memory
    save_memory(str(result))

    # Auto-save output
    output_path = os.path.join(
        workspace or ".",
        "ustaad_output.md"
    )

    write_file(
        output_path,
        str(result)
    )

    print(f"\nSaved output to: {output_path}")

    return result
