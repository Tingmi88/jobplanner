"""
Graph nodes for the job planning workflow.
"""
import os
from typing import List, Optional, Annotated, TypedDict
from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.graph.message import add_messages
from rich.console import Console
from langchain_tavily import TavilySearch
from langchain_nebius import ChatNebius
from langchain.tools import tool
from app.tools import (load_job_by_title, search_jobs_by_title, list_all_jobs,
                       get_job_by_filename, search_jobs_by_criteria)
from dotenv import load_dotenv
load_dotenv(override=True)

console = Console()

web_search = TavilySearch(api_key=os.environ["TAVILY_API_KEY"], max_results=2)

web_search.name = "web_search"
web_search.description = "Search the web for information"

@tool
def web_search_tool(query: str) -> str:
    """Search the web for information"""
    response = web_search.invoke(query)
    return str(response)


llm = ChatNebius(model="Qwen/Qwen3-14B", api_key=os.environ["NEBIUS_API_KEY"])
# Add job tools to your tool list
llm_with_tools = llm.bind_tools([
    web_search_tool, 
    load_job_by_title, 
    search_jobs_by_title,
    list_all_jobs,
    get_job_by_filename,
    search_jobs_by_criteria
])

class Plan(BaseModel):
    """
    A structured plan for a multi-step task
    """
    steps: List[str] = Field(description="A list of tool calls that, when executed, will answer the query.")

class PlannerState(TypedDict):
    """
    The state of the planner agent
    """
    user_input: str
    plan: Optional[List[str]] = None
    intermediate_messages: Optional[List[str]] = None
    messages: Annotated[List[BaseMessage], add_messages]
    final_output: Optional[str] = None

def planner_node(state: PlannerState) -> PlannerState:
    """
    Plan the steps for the task
    """
    console.print("--- PLANNER: Decomposing task... ---")
    PLANNER_SYSTEM = (
        "You are a planning agent with access to job data. Break down the task into steps. "
        "Available tools: "
        "- 'web_search_tool(\"query\")' for external information "
        "- 'load_job_by_title(\"job_title\")' to load a job by its title "
        "- 'search_jobs_by_title(\"partial_title\")' to search for jobs by partial title "
        "- 'list_all_jobs()' to see all available jobs "
        "- 'get_job_by_filename(\"filename\")' to load job by exact filename "
        "- 'search_jobs_by_criteria(\"criteria\")' to find relevant jobs "
        "When you have enough information to plan, output ONLY JSON: {\"steps\": [\"...\"]} with 4–7 concrete steps."
    )
    msgs = state.get("messages") or []
    if not msgs:
        # seed the conversation for the planner
        msgs = [
            HumanMessage(
                content=f"{PLANNER_SYSTEM}\n\nTask: {state['user_input']}"
            )
        ]

    # Let the planner take a turn. If it needs the tool it will emit tool_calls.
    planner_llm = llm.with_structured_output(Plan)

    ai = planner_llm.invoke(msgs)

    # Return only the new AI turn; add_messages merges it into the running history.
    console.print(f"--- PLANNER: Generated Plan: {ai} ---")

    return {"plan": ai.steps}

def job_aware_executor_node(state: PlannerState) -> PlannerState:
    """Executor that handles both general and job-specific steps."""
    console.print("--- EXECUTOR: Running next step... ---")

    plan = state["plan"] or []
    if not plan:
        return {"plan": []}

    next_step = plan[0]
    
    # Route to appropriate handler
    if next_step.startswith("web_search_tool"):
        # Web search logic
        import re
        m = re.search(r'web_search_tool\("(.+?)"\)', next_step)
        if not m:
            m = re.search(r"web_search_tool\('(.+?)'\)", next_step)
        if m:
            query = m.group(1)
            response = web_search_tool.invoke(query)
        else:
            response = "Error: Could not parse web search query"
            
    elif next_step.startswith("load_job_by_title"):
        # Load job by title
        import re
        m = re.search(r'load_job_by_title\("(.+?)"\)', next_step)
        if m:
            response = load_job_by_title.invoke(m.group(1))
        else:
            response = "Error: Could not parse job title"
            
    elif next_step.startswith("search_jobs_by_title"):
        # Search jobs by title
        import re
        m = re.search(r'search_jobs_by_title\("(.+?)"\)', next_step)
        if m:
            response = search_jobs_by_title.invoke(m.group(1))
        else:
            response = "Error: Could not parse search term"
            
    elif next_step.startswith("list_all_jobs"):
        # List all jobs
        response = list_all_jobs.invoke({})
        
    elif next_step.startswith("get_job_by_filename"):
        # Get job by filename
        import re
        m = re.search(r'get_job_by_filename\("(.+?)"\)', next_step)
        if m:
            response = get_job_by_filename.invoke(m.group(1))
        else:
            response = "Error: Could not parse filename"
            
    elif next_step.startswith("search_jobs_by_criteria"):
        # Search jobs by criteria
        import re
        m = re.search(r'search_jobs_by_criteria\("(.+?)"\)', next_step)
        if m:
            response = search_jobs_by_criteria.invoke(m.group(1))
        else:
            response = "Error: Could not parse search criteria"
            
    else:
        # General reasoning with job context
        job_prompt = f"""
        You are a recruitment and job analysis expert. Process this step:
        
        Step: {next_step}
        
        Provide expert analysis and recommendations. If this involves job analysis, 
        consider using the available job tools to get specific information.
        """
        response = llm.invoke(job_prompt).content

    console.print(f"--- EXECUTOR: {response[:100]}... ---")

    return {
        "plan": state["plan"][1:],
        "intermediate_messages": (state.get("intermediate_messages") or []) + [response]
    }

def synthesizer_node(state: PlannerState) -> PlannerState:
    """Synthesizes the intermediate messages into a final output."""
    console.print("--- SYNTHESIZER: Synthesizing... ---")

    context = "\n".join(state["intermediate_messages"] or [])    

    prompt = f"""You are an expert synthesizer. Based on the user's input and the collected data, provide a comprehensive final answer.
    
    Request: {state['user_input']}
    Collected Data:
    {context}
    """
    final_output = llm.invoke(prompt).content
    return {"final_output": final_output}


def router_after_planner(state: PlannerState) -> str:
    msgs = state.get("messages") or []
    last = msgs[-1] if msgs else None
    # If the last AI turn requested any tools, go to ToolNode; else, parse the plan.
    return "tools" if getattr(last, "tool_calls", None) else "executer"

def router_function(state: PlannerState) -> str:
    if state.get("plan"):
        return "executer"
    else:
        return "synthesizer"