"""
LangGraph runtime for job planning and execution.
"""

from langgraph.graph import StateGraph, END
from app.nodes import PlannerState, planner_node, job_aware_executor_node, synthesizer_node, router_function

graph_builder = StateGraph(PlannerState)
graph_builder.add_node("planner", planner_node)
graph_builder.add_node("executer", job_aware_executor_node)
graph_builder.add_node("synthesizer", synthesizer_node)
graph_builder.set_entry_point("planner")
graph_builder.add_edge("planner", "executer")
graph_builder.add_conditional_edges("executer", router_function, {"executer":"executer", "synthesizer":"synthesizer"})
graph_builder.add_edge("synthesizer", END)

planner_agent = graph_builder.compile()


