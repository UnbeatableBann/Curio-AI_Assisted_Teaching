import google.generativeai as genaia
import sqlite3
import os
from dotenv import load_dotenv

class QuizGenerator:
    def __init__(self, db_file='class_data.db'):
        """Initialize the QuizGenerator with the database file and configure the Gemini API."""
        load_dotenv()
        self.db_file = db_file
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        genaia.configure(api_key=self.gemini_api_key)

    def get_text_transcriptions(self):
        """Retrieve all transcriptions from the database and concatenate them."""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute("SELECT text FROM text_recording ORDER BY timestamp DESC")
            results = cursor.fetchall()
            conn.close()

            if results:
                # Concatenate all transcription texts
                all_text = "\n".join([result[0] for result in results])
                return all_text
            else:
                return "No transcriptions available."
        except Exception as e:
            print(f"Error retrieving transcriptions: {e}")
            return "Error retrieving transcriptions."

    def generate_quiz(self, topic):
        """Generate a quiz based on the given topic and text transcriptions."""
        try:
            # Determine the intent of the topic using Gemini
            intent_prompt = (
                f"Determine the topic on which i have to generate the quiz. "
                f"Check for the topic for following: '{topic}'. "
                f"Return only the topic if found; otherwise, if it says to use class data or just generate quiz then return 'None'."
            )
            model = genaia.GenerativeModel('gemini-2.0-flash')
            intent_response = model.generate_content(intent_prompt)
            intent = intent_response.text.strip()

            # Use text transcriptions if intent is not found
            text = self.get_text_transcriptions() if intent == "None" else topic

            # Use Gemini to generate quiz questions
            prompt = (
                f"Generate few multiple-choice quiz questions based on the following text, focusing on the topic of:\n\n"
                f"{text}\n\n"
                f"Each question should have 4 answer options (A, B, C, D) with one correct answer. "
                f"Indicate the correct answer after each question in parenthesis. "
                f"Format each question like this:\n\n"
                f"Question: [Question text]\n"
                f"A) [Option A]\n"
                f"B) [Option B]\n"
                f"C) [Option C]\n"
                f"D) [Option D]\n"
                f"(Correct Answer: [Letter of correct answer])\n\n"
                f"- If no text transcription is present, then return 'None' without any explanation."
            )

            response = model.generate_content(prompt)
            if response.text:
                return response.text
            else:
                return None
        except Exception as e:
            print(f"Error generating quiz: {e}")
            return "Failed to generate quiz."