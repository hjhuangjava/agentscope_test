from typing import Any, Dict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph


def node_1(state: Dict[str, Any]) -> Dict[str, Any]:
    return {"foo": state["user_input"] + " name"}


def node_2(state: Dict[str, Any]) -> Dict[str, Any]:
    return {"bar": state["foo"] + " is"}


def node_3(state: Dict[str, Any]) -> Dict[str, Any]:
    return {"graph_output": state["bar"] + " Lance"}


def create_graph() -> CompiledStateGraph:
    builder = StateGraph(Dict[str, Any])
    builder.add_node("node_1", node_1)
    builder.add_node("node_2", node_2)
    builder.add_node("node_3", node_3)
    builder.add_edge(START, "node_1")
    builder.add_edge("node_1", "node_2")
    builder.add_edge("node_2", "node_3")
    builder.add_edge("node_3", END)
    return builder.compile()


if __name__ == "__main__":
    graph = create_graph()
    input_state = {"user_input": "My"}
    result = graph.invoke(input_state)
    print("========", result)
