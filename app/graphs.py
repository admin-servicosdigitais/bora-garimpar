from langgraph.graph import END, START, StateGraph

from app.agents.ingestion import extract_json_and_store_db_agent, scrape_and_save_json_agent
from app.agents.matching import match_jobs_by_profile_agent
from app.schemas import PipelineState


def build_ingestion_graph():
    graph = StateGraph(PipelineState)
    graph.add_node("scrape_agent", scrape_and_save_json_agent)
    graph.add_node("extract_store_agent", extract_json_and_store_db_agent)
    graph.add_edge(START, "scrape_agent")
    graph.add_edge("scrape_agent", "extract_store_agent")
    graph.add_edge("extract_store_agent", END)
    return graph.compile()


def build_matching_graph():
    graph = StateGraph(PipelineState)
    graph.add_node("match_agent", match_jobs_by_profile_agent)
    graph.add_edge(START, "match_agent")
    graph.add_edge("match_agent", END)
    return graph.compile()


ingestion_graph = build_ingestion_graph()
matching_graph = build_matching_graph()
