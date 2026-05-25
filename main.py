from crewai import Task, Crew

from agents.planner import planner
from agents.coder import coder
from agents.reviewer import reviewer
from agents.researcher import researcher

from tools.memory_tools import save_memory
from tools.shell_tools import run_command
from tools.file_tools import write_file

from tools.memory_tools import search_memory

results = search_memory(
    "authentication api"
)

print(results)

write_file(
    "app.py",
    generated_code
)

print(run_command("git status"))

def run_task(user_prompt):

    planning_task = Task(

        description=f"""
        Create a detailed implementation plan for:

        {user_prompt}
        """,

        expected_output="""
        Step-by-step technical plan
        """,

        agent=planner
    )

    coding_task = Task(

        description=f"""
        Implement the following:

        {user_prompt}
        """,

        expected_output="""
        Production-ready implementation
        """,

        agent=coder
    )

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

    result = crew.kickoff()

    save_memory(str(result))

    return result
