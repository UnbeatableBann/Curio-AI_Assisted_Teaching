import google.generativeai as genaia
from quiz_generator import QuizGenerator
from dotenv import load_dotenv
import os

load_dotenv()

GEMINI_API_KEY= os.getenv("GEMINI_API_KEY")

genaia.configure(api_key=GEMINI_API_KEY)

def summarize_class():
    """Summarizes the entire class based on recorded transcriptions."""
    quiz_generator = QuizGenerator()
    text = quiz_generator.get_text_transcriptions()
    prompt = f"""
    Summarize the following class discussion into key points:
    
    {text}
    
    - Keep the summary concise and give in only few points not more than four.
    - Highlight key topics covered.
    - If no text transcription present then return 'None' without any explaination.
    """

    model = genaia.GenerativeModel('gemini-2.0-flash')
    response = model.generate_content(prompt)
    if response.text:
        return response.text
    else:
        return "No summary available."
    