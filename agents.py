from typing import TypedDict, List, Dict, Any
from langchain.tools import Tool
from langgraph.graph import START, END, StateGraph
from tools.pdf_summary import user_input
from tools.quiz_generator import generate_quiz
from tools.visual_generator import run_all_image_generators
from tools.class_summary import summarize_class
from tools.threeD_model import generate_3d_model

pdf_summarization = Tool(
    name="Summarization of PDF",
    func=user_input,
    description="Give summary for uploaded PDFs."
)

image_generation = Tool(
    name="Image Generation",
    func=run_all_image_generators,
    description="Generates images from different sources."
)

generate_quiz_tool = Tool(
    name="Generate Quiz",
    func=generate_quiz,
    description="Generates a quiz from the latest recorded text."
)

class_summarization = Tool(
    name="Class Summarization",
    func=summarize_class,
    description="Summarizes class lecture based on transcripts."
)

model_generation = Tool(
    name="3D Model Generation",
    func=generate_3d_model,
    description="Generates a 3D model from the given context."
)
def summarize_node(state):
    result = class_summarization.func("")
    state["results"].append({"step": "summary", "output": result})
    return state

def quiz_node(state):
    result = generate_quiz_tool.func("")
    state["results"].append({"step": "quiz", "output": result})
    return state

def image_node(state):
    result = image_generation.func("")
    state["results"].append({"step": "image", "output": result})
    return state

def model_node(state):
    result = model_generation.func("")
    state["results"].append({"step": "3d_model", "output": result})
    return state

# Define your graph state structure
class AgentState(TypedDict):
    command: str
    results: List[Dict[str, Any]]

def build_graph():
    builder = StateGraph(AgentState)

    # Start Node: decide based on user command
    builder.add_node("summarize", summarize_node)
    builder.add_node("quiz", quiz_node)
    builder.add_node("image", image_node)
    builder.add_node("3d_model", model_node)

    # This order is just an example – modify as needed
    builder.add_edge(START, "summarize")
    builder.add_edge(START, "quiz")
    #builder.add_edge("quiz", "image")
    #builder.add_edge("image", "3d_model")

    builder.add_edge("summarize", END)
    graph= builder.compile()
    print(graph.get_graph().draw_ascii())

    return graph


def handle_query(command):
    # Initialize state
    state = {"command": command, "results": []}
    # Run the graph
    graph = build_graph()
    final_state = graph.invoke(state)

    print("🧠 Final Results:", final_state["results"])
    return final_state["results"]


if __name__ == "__main__":
    # Example command to test the graph
    command = "generate image"
    results = handle_query(command)
    print("Results:", results)  