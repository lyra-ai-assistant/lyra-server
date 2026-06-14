from lyra.agents.GenerationAgent import GenerationAgent

generation_agent = GenerationAgent()
_model_ready = False

def get_agent() -> GenerationAgent:
    return generation_agent
