"""
Graph nodes for the job planning workflow.
"""
import os
from typing import List, Optional, Annotated, TypedDict
from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.graph.message import add_messages
from langchain_tavily import TavilySearch
from langchain_nebius import ChatNebius
from langchain.tools import tool
from app.tools import (load_job_by_title, search_jobs_by_title, list_all_jobs,
                       get_job_by_filename, search_jobs_by_criteria)
from dotenv import load_dotenv
load_dotenv(override=True)

import logging
import re

# Set up logging with separate loggers for each node
logger = logging.getLogger("jobplanner.nodes")
planner_logger = logging.getLogger("jobplanner.nodes.planner")
executor_logger = logging.getLogger("jobplanner.nodes.executor")
synthesizer_logger = logging.getLogger("jobplanner.nodes.synthesizer")
router_logger = logging.getLogger("jobplanner.nodes.router")


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
    user_input = state.get("user_input", "")
    planner_logger.info(
        "Planner node started",
        extra={
            "node": "planner",
            "action": "start",
            "user_input_length": len(user_input),
        }
    )
    
    try:
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
                    content=f"{PLANNER_SYSTEM}\n\nTask: {user_input}"
                )
            ]
            planner_logger.debug(
                "Seeded conversation for planner",
                extra={"message_count": len(msgs)}
            )

        # Let the planner take a turn. If it needs the tool it will emit tool_calls.
        planner_llm = llm.with_structured_output(Plan)
        
        planner_logger.debug(
            "Invoking planner LLM",
            extra={"message_count": len(msgs)}
        )
        ai = planner_llm.invoke(msgs)
        
        plan_steps = ai.steps
        planner_logger.info(
            "Planner generated plan successfully",
            extra={
                "node": "planner",
                "action": "complete",
                "plan_step_count": len(plan_steps),
                "plan_steps": plan_steps,
            }
        )

        return {"plan": plan_steps}
    except Exception as e:
        planner_logger.error(
            "Planner node failed",
            extra={
                "node": "planner",
                "action": "error",
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
            exc_info=True
        )
        raise

def job_aware_executor_node(state: PlannerState) -> PlannerState:
    """Executor that handles both general and job-specific steps."""
    plan = state.get("plan") or []
    remaining_steps = len(plan)
    
    executor_logger.info(
        "Executor node started",
        extra={
            "node": "executor",
            "action": "start",
            "remaining_steps": remaining_steps,
        }
    )
    
    if not plan:
        executor_logger.warning(
            "Executor received empty plan",
            extra={"node": "executor", "action": "empty_plan"}
        )
        return {"plan": []}

    next_step = plan[0]
    executor_logger.debug(
        "Executing next step",
        extra={
            "node": "executor",
            "step": next_step,
            "step_index": len(state.get("plan", [])) - remaining_steps,
        }
    )
    
    try:
        # Route to appropriate handler
        if next_step.startswith("web_search_tool"):
            # Web search logic
            m = re.search(r'web_search_tool\("(.+?)"\)', next_step)
            if not m:
                m = re.search(r"web_search_tool\('(.+?)'\)", next_step)
            if m:
                query = m.group(1)
                executor_logger.debug(
                    "Executing web search",
                    extra={"tool": "web_search_tool", "query": query}
                )
                response = web_search_tool.invoke(query)
            else:
                response = "Error: Could not parse web search query"
                executor_logger.warning(
                    "Failed to parse web search query",
                    extra={"step": next_step}
                )
                
        elif next_step.startswith("load_job_by_title"):
            # Load job by title
            m = re.search(r'load_job_by_title\("(.+?)"\)', next_step)
            if m:
                job_title = m.group(1)
                executor_logger.debug(
                    "Loading job by title",
                    extra={"tool": "load_job_by_title", "job_title": job_title}
                )
                response = load_job_by_title.invoke(job_title)
            else:
                response = "Error: Could not parse job title"
                executor_logger.warning(
                    "Failed to parse job title",
                    extra={"step": next_step}
                )
                
        elif next_step.startswith("search_jobs_by_title"):
            # Search jobs by title
            m = re.search(r'search_jobs_by_title\("(.+?)"\)', next_step)
            if m:
                search_term = m.group(1)
                executor_logger.debug(
                    "Searching jobs by title",
                    extra={"tool": "search_jobs_by_title", "search_term": search_term}
                )
                response = search_jobs_by_title.invoke(search_term)
            else:
                response = "Error: Could not parse search term"
                executor_logger.warning(
                    "Failed to parse search term",
                    extra={"step": next_step}
                )
                
        elif next_step.startswith("list_all_jobs"):
            # List all jobs
            executor_logger.debug("Listing all jobs", extra={"tool": "list_all_jobs"})
            response = list_all_jobs.invoke({})
            
        elif next_step.startswith("get_job_by_filename"):
            # Get job by filename
            m = re.search(r'get_job_by_filename\("(.+?)"\)', next_step)
            if m:
                filename = m.group(1)
                executor_logger.debug(
                    "Getting job by filename",
                    extra={"tool": "get_job_by_filename", "filename": filename}
                )
                response = get_job_by_filename.invoke(filename)
            else:
                response = "Error: Could not parse filename"
                executor_logger.warning(
                    "Failed to parse filename",
                    extra={"step": next_step}
                )
                
        elif next_step.startswith("search_jobs_by_criteria"):
            # Search jobs by criteria
            m = re.search(r'search_jobs_by_criteria\("(.+?)"\)', next_step)
            if m:
                criteria = m.group(1)
                executor_logger.debug(
                    "Searching jobs by criteria",
                    extra={"tool": "search_jobs_by_criteria", "criteria": criteria}
                )
                response = search_jobs_by_criteria.invoke(criteria)
            else:
                response = "Error: Could not parse search criteria"
                executor_logger.warning(
                    "Failed to parse search criteria",
                    extra={"step": next_step}
                )
                
        else:
            # General reasoning with job context
            executor_logger.debug(
                "Using LLM for general reasoning",
                extra={"step": next_step}
            )
            job_prompt = f"""
            You are a recruitment and job analysis expert. Process this step:
            
            Step: {next_step}
            
            Provide expert analysis and recommendations. If this involves job analysis, 
            consider using the available job tools to get specific information.
            """
            response = llm.invoke(job_prompt).content

        response_preview = str(response)[:100] if response else ""
        executor_logger.info(
            "Step execution completed",
            extra={
                "node": "executor",
                "action": "complete",
                "step": next_step,
                "response_length": len(str(response)) if response else 0,
                "response_preview": response_preview,
                "remaining_steps": remaining_steps - 1,
            }
        )

        return {
            "plan": state["plan"][1:],
            "intermediate_messages": (state.get("intermediate_messages") or []) + [response]
        }
    except Exception as e:
        executor_logger.error(
            "Step execution failed",
            extra={
                "node": "executor",
                "action": "error",
                "step": next_step,
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
            exc_info=True
        )
        raise

def synthesizer_node(state: PlannerState) -> PlannerState:
    """Synthesizes the intermediate messages into a final output."""
    intermediate_messages = state.get("intermediate_messages") or []
    context_length = len("\n".join(intermediate_messages))
    
    synthesizer_logger.info(
        "Synthesizer node started",
        extra={
            "node": "synthesizer",
            "action": "start",
            "intermediate_message_count": len(intermediate_messages),
            "context_length": context_length,
        }
    )
    
    try:
        context = "\n".join(intermediate_messages)
        user_input = state.get("user_input", "")
        
        synthesizer_logger.debug(
            "Building synthesis prompt",
            extra={
                "user_input_length": len(user_input),
                "context_length": len(context),
            }
        )

        prompt = f"""You are an expert synthesizer. Based on the user's input and the collected data, provide a comprehensive final answer.
    
    Request: {user_input}
    Collected Data:
    {context}
    """
        
        synthesizer_logger.debug("Invoking LLM for synthesis")
        final_output = llm.invoke(prompt).content
        
        synthesizer_logger.info(
            "Synthesizer completed successfully",
            extra={
                "node": "synthesizer",
                "action": "complete",
                "final_output_length": len(final_output) if final_output else 0,
            }
        )
        
        return {"final_output": final_output}
    except Exception as e:
        synthesizer_logger.error(
            "Synthesizer node failed",
            extra={
                "node": "synthesizer",
                "action": "error",
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
            exc_info=True
        )
        raise


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