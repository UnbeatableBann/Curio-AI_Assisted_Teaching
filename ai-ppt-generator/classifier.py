from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
import os

load_dotenv()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

def classify_content(text_content):
    """
    Classifies the document content using Gemini.
    Returns a short category string (e.g., 'Physics', 'History', 'Legal', 'General').
    """
    if not GEMINI_API_KEY:
        return "Uncategorized"
        
    try:
        model_name = os.getenv('GEMINI_MODEL_NAME', 'gemini-3-flash-preview')
        llm = ChatGoogleGenerativeAI(model=model_name, google_api_key=GEMINI_API_KEY)
        
        # Taking a snippet to avoid token limits if file is huge
        snippet = text_content[:4000]
        
        messages = [
            ("system", "You are a document classifier. Return a specific one-word category for the provided text. Examples: 'Physics', 'Marketing', 'Legal', 'ComputerScience', 'Medicine'. Output ONLY the category name, nothing else."),
            ("human", f"Classify this text:\n\n{snippet}")
        ]
        
        response = llm.invoke(messages)
        
        # Handle response.content which might be a list or dict
        content = response.content
        if isinstance(content, list):
            # Join list parts or take first text element
            text_parts = []
            for part in content:
                if isinstance(part, dict) and 'text' in part:
                    text_parts.append(part['text'])
                elif isinstance(part, str):
                    text_parts.append(part)
                else:
                    text_parts.append(str(part))
            content = "".join(text_parts)
        
        category = str(content).strip()
        
        # Limit category length
        if len(category) > 30:
            print(f"Warning: Category too long: {category[:50]}...")
            # Try to extract just the category name
            words = category.split()
            category = words[0] if words else "General"
        
        # Cleanup: sometimes models add extra punctuation
        if category.endswith('.'):
            category = category[:-1]
        
        # Remove spaces for consistency
        category = category.replace(' ', '')
            
        return category if category else "General"
    except Exception as e:
        print(f"Classification error: {e}")
        return "General"
