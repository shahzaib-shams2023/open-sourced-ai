from autogen_agentchat.agents import AssistantAgent

planner = AssistantAgent(
    name="planner",
    model_client="deepseek-r1"
)

coder = AssistantAgent(
    name="coder",
    model_client="qwen3.6:latest"
)

reviewer = AssistantAgent(
    name="reviewer",
    model_client="deepseek-r1"
)
