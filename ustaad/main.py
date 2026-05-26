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

    # Planning Task
    planning_task = Task(

        description=f"""
        Create a detailed implementation plan for:

        {user_prompt}

        Current workspace:
        {workspace}
        """,

        expected_output="""
        Step-by-step technical plan
        """,

        agent=planner
    )

    # Coding Task
    coding_task = Task(

        description=f"""
        Implement the following:

        {user_prompt}

        Generate production-ready code.
        """,

        expected_output="""
        Production-ready implementation
        """,

        agent=coder
    )

    # Review Task
    review_task = Task(

        description="""
        Review generated implementation for:

        - bugs
        - scalability
        - security
        - performance
        """,

        expected_output="""
        Detailed technical review
        """,

        agent=reviewer
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
