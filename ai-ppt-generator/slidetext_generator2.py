import os
import json
from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda, RunnableSequence
import logging

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise EnvironmentError("GEMINI_API_KEY not found.")

embedding = GoogleGenerativeAIEmbeddings(
    model="models/embedding-001", google_api_key=GEMINI_API_KEY
)

def get_slide_generator_runnable():
    # Prompt for mapping each document to a slide draft
    map_prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a slide assistant."),
        ("user", "Topic: {topic}\nUse this document snippet:\n{context}\nGenerate a concise slide draft.")
    ])

    # Prompt for reducing drafts into final JSON slides
    reduce_prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert educational presentation designer."),
        ("user", (
            "Topic: {topic}\n"
            "You are given a collection of draft slides for this topic.\n\n"
            "Now combine these drafts into a final presentation in **JSON format** as an array of slides.\n\n"
            "For each slide, include:\n"
            "- **title**: Short and clear title\n"
            "- **bullet_points**: 3–5 simple bullet points\n"
            "- **speaker_notes**: Expand the content into a short spoken explanation\n"
            "- **font_hint**: (optional) Suggest a font style like 'chalkboard', 'modern sans-serif', or 'handwritten' that fits the tone\n"
            "- **color_hint**: (optional) Suggest background/text color palette (e.g., 'green on white', 'dark mode with yellow highlights')\n"
            "- **visual_hint**: Describe a suitable visual aid (diagram, image, chart, infographic, etc.) to accompany the slide.\n"
            "    • If relevant visual is found in the text, indicate its location (e.g., 'see Figure 3 in document').\n"
            "    • Else, describe what the ideal visual should show (e.g., 'infographic comparing Photosynthesis vs Respiration').\n\n"
            "Make slides **engaging, educational, and contextually accurate**. Keep them concise and ready to render in a real slide deck.\n\n"
            "Context:\n{context}"
        ))
    ])


    llm = ChatGoogleGenerativeAI(
        google_api_key=GEMINI_API_KEY,
        model="gemini-3-flash-preview",
        temperature=0.3
    )

    map_chain = map_prompt | llm | StrOutputParser()
    reduce_chain = reduce_prompt | llm | StrOutputParser()

    # Step 1: Map over each document
    map_runnable = RunnableLambda(
        lambda inputs: [
            map_chain.invoke({"topic": inputs["topic"], "context": doc.page_content})
            for doc in inputs["input_documents"]
        ]
    )

    # Step 2: Reduce the mapped outputs into final slides
    reduce_runnable = RunnableLambda(
        lambda mapped_outputs_and_inputs: reduce_chain.invoke({
            "topic": mapped_outputs_and_inputs["topic"],
            "context": "\n".join(mapped_outputs_and_inputs["mapped_outputs"])
        })
    )

    # Combine both steps into a single RunnableSequence
    full_chain = RunnableSequence(
            lambda inputs: {
                "mapped_outputs": map_runnable.invoke(inputs),
                "topic": inputs["topic"]
            },
            reduce_runnable
        
    )

    return full_chain

def user_input(topic):
    try:
        # Load vector DB
        try:
            new_db = FAISS.load_local("vector_db", embedding, allow_dangerous_deserialization=True)
        except Exception as e:
            logging.error(f"Failed to load vector DB: {e}")
            return {"error": "Internal error: Could not load knowledge base."}

        # Retrieve documents
        try:
            docs = new_db.similarity_search(topic)
            if not docs:
                logging.warning(f"No documents found for topic: {topic}")
                return {"error": "No relevant documents found for your topic."}
        except Exception as e:
            logging.error(f"Document retrieval failed: {e}")
            return {"error": "Internal error: Could not retrieve documents."}

        # Generate slides
        slide_generator = get_slide_generator_runnable()
        try:
            result = slide_generator.invoke({"input_documents": docs, "topic": topic})
        except Exception as e:
            logging.error(f"LLM invocation failed: {e}")
            return {"error": "Internal error: Could not generate slides."}

        # Clean and parse output
        try:
            result = result.replace("```json", "").replace("```", "").strip()
            slides = json.loads(result)
            return slides
        except json.JSONDecodeError as e:
            logging.error(f"JSON parsing failed: {e}\nResult was:\n{result}")
            return {"error": "Failed to parse slide content. Please try again."}
        except Exception as e:
            logging.error(f"Unexpected error during output processing: {e}")
            return {"error": "An unexpected error occurred."}

    except Exception as e:
        logging.critical(f"Unhandled error in user_input: {e}")
        return {"error": "A critical error occurred. Please contact support."}

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    slides = user_input("ppt on Teachmintx with 10 slides")
    print(slides)
