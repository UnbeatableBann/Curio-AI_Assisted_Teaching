import os
import json
import re
from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

load_dotenv()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

if not GEMINI_API_KEY:
    raise EnvironmentError("GEMINI_API_KEY not found in environment variables.")

embedding = GoogleGenerativeAIEmbeddings(
    model="models/text-embedding-004", 
    google_api_key=GEMINI_API_KEY
)

def get_conversational_chain():
    """
    Returns a LangChain chain configured with a prompt for generating educational slide content.
    """
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert AI Presentation Designer. You don't just write text; you design the entire look and feel."),
        ("user", """
Topic: "{topic}"
Task: Create a complete presentation design and content.

1. **Design The Presentation**:
   - Choose a Color Palette (Hex codes) that fits the topic (e.g., Dark & Neon for AI, Clean & Blue for Medical).
   - Choose a Font Style (Serif, Sans-Serif).
   - Define the 'Mood' (Professional, Playful, Futuristic).

3. **Content Structure**:
   - **Title Slide**: Catchy title & subtitle.
   - **Agenda**: clear roadmap.
   - **Content Slides (4-6)**: 
     - detailed points (mix of context & general knowledge).
     - **Visual Descriptions**: describe specific, relevant images (e.g., "Chart showing growth of X", "Diagram of Y").
   - **Conclusion**: Summary & Next Steps.

Context (from user files):
{context}

**Output JSON Format ONLY**:
{{
  "theme": {{
    "background_color": "#HEXCODE (e.g., #1E1E2E)",
    "text_color": "#HEXCODE (e.g., #FFFFFF)",
    "primary_color": "#HEXCODE (for titles)",
    "accent_color": "#HEXCODE (for highlights)",
    "font_family": "Calibri" 
  }},
  "slides": [
    {{
      "layout": "title" | "content_text_left" | "content_text_right" | "full_text",
      "title": "Slide Title",
      "content": ["Point 1", "Point 2"],
      "visual_description": "Detailed description for an image generation prompt",
      "speaker_notes": "What the speaker should say..."
    }}
  ]
}}
""")
    ])

    # Using configurable model for flexibility
    model_name = os.getenv('GEMINI_MODEL_NAME', 'gemini-3-flash-preview')
    print(f"Using Gemini Model: {model_name}")
    
    model = ChatGoogleGenerativeAI(
        google_api_key=GEMINI_API_KEY,
        model=model_name,
        temperature=0.5 # Higher temp for more creativity in design
    )
    
    chain = prompt | model | StrOutputParser()
    return chain

def repair_json(json_string):
    """
    Attempts to repair common JSON errors in AI-generated JSON strings.
    Fixes issues like missing commas between object properties.
    """
    # First, try to extract JSON if it's wrapped in markdown code blocks
    json_string = json_string.strip()
    json_string = re.sub(r'^```json\s*', '', json_string)
    json_string = re.sub(r'^```\s*', '', json_string)
    json_string = re.sub(r'```\s*$', '', json_string)
    json_string = json_string.strip()
    
    # Try parsing first - if it works, return as-is
    try:
        return json.loads(json_string)
    except json.JSONDecodeError:
        pass
    
    # Fix missing comma after string property values (most common issue)
    # Pattern: "key": "value"\n      "next_key": -> "key": "value",\n      "next_key":
    # This handles cases where a string value ends and is followed by a new property
    json_string = re.sub(
        r'"\s*\n\s+"([a-zA-Z_][a-zA-Z0-9_]*)"\s*:',
        r'",\n      "\1":',
        json_string
    )
    
    # More specific: fix missing comma after visual_description (common in slide objects)
    json_string = re.sub(
        r'"visual_description":\s*"([^"]*)"\s*\n\s+"speaker_notes"',
        r'"visual_description": "\1",\n      "speaker_notes"',
        json_string,
        flags=re.MULTILINE
    )
    
    # Fix missing comma after any string property that's followed by another property
    # Pattern: "value"\n      "key": (where value doesn't end with comma)
    json_string = re.sub(
        r'("(?:[^"\\]|\\.)*")\s*\n\s+("(?:[a-zA-Z_][a-zA-Z0-9_]*)"\s*:)',
        r'\1,\n      \2',
        json_string
    )
    
    # Fix missing comma after array closing bracket before next property
    json_string = re.sub(
        r'\]\s*\n\s+"([a-zA-Z_][a-zA-Z0-9_]*)"\s*:',
        r'],\n      "\1":',
        json_string
    )
    
    # Fix missing comma after object closing brace before next property
    json_string = re.sub(
        r'}\s*\n\s+"([a-zA-Z_][a-zA-Z0-9_]*)"\s*:',
        r'},\n      "\1":',
        json_string
    )
    
    # Try parsing again
    try:
        return json.loads(json_string)
    except json.JSONDecodeError as e:
        # More aggressive repair: find lines that should have commas
        lines = json_string.split('\n')
        repaired_lines = []
        
        for i, line in enumerate(lines):
            repaired_lines.append(line)
            
            # Check if this line ends with a string value (quote) and next line is a property
            if i < len(lines) - 1:
                current_line = line.rstrip()
                next_line = lines[i + 1].strip()
                
                # If current line ends with " and doesn't end with , or { or [
                # And next line starts with a property name in quotes
                if (current_line.endswith('"') and 
                    not current_line.endswith(',') and 
                    not current_line.endswith('{') and 
                    not current_line.endswith('[') and
                    re.match(r'^\s*"[a-zA-Z_][a-zA-Z0-9_]*"\s*:', next_line)):
                    # Add comma to current line
                    repaired_lines[-1] = current_line + ','
        
        json_string = '\n'.join(repaired_lines)
        
        # Try parsing one more time
        try:
            return json.loads(json_string)
        except json.JSONDecodeError as final_e:
            # Last resort: raise the original error with context
            print(f"JSON repair failed. Error at position {getattr(final_e, 'pos', 'unknown')}")
            raise ValueError(f"Failed to parse JSON even after repair attempts: {final_e}")

def user_input(topic):
    try:
        new_db = FAISS.load_local("./vector_db", embedding, allow_dangerous_deserialization=True)
        docs = new_db.similarity_search(topic, k=10) 
        print(f"DEBUG: Found {len(docs)} relevant document chunks.")
        context = "\n\n".join([doc.page_content for doc in docs])
        print(f"DEBUG: Context length: {len(context)} chars")
        if len(context) > 500:
             print(f"DEBUG: Context snippet: {context[:500]}...")
        if len(context) > 20000: context = context[:20000]
    except Exception:
        # Fallback if DB load fails (e.g. empty DB)
        context = "No specific documents provided."
    
    chain = get_conversational_chain()
    response = chain.invoke({"context": context, "topic": topic})
    
    print(f"Raw LLM Response: {response}")
    
    output_text = response.strip()
    if not output_text:
        raise ValueError("Model returned empty response. Could be due to safety filters or model instability.")
    
    try:
        # Use repair_json which handles common JSON errors
        return repair_json(output_text)
    except json.JSONDecodeError as e:
        print(f"JSON Error: {output_text}")
        raise ValueError(f"Failed to parse JSON from model output: {e}")

if __name__ == "__main__":
    topic = "Future of Space Travel"
    try:
        data = user_input(topic)
        print(json.dumps(data, indent=2))
    except Exception as e:
        print(f"Error: {e}")