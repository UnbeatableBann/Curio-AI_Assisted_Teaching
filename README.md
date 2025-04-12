# AI-Powered Smartboard Teaching Assistant  (THIS PROJECT STILL IN PROGRESS. NOT FINISHED YET)

## Overview
This project aims to build an AI-powered smartboard application designed to assist teachers in the classroom. It integrates **Agentic AI** to generate images, videos, GIFs, quizzes, and summarize lessons based on teacher queries. The application enhances classroom interaction by allowing teachers to query the AI for visual aids, explanations, and class summaries, all while keeping track of class progress and student engagement.

## Features
- **Voice Recognition**: Detects voice commands to generate real-time responses, images, or quizzes.
- **Interactive Visuals**: Generates and displays images, GIFs, or videos based on teacher queries (e.g., "Show me a diagram of the human heart").
- **Real-Time Class Summarization**: AI can summarize class sessions and answer questions like "What did we study yesterday?" using previously stored audio recordings.
- **Quiz Generation**: Automatically creates quizzes based on the topic being taught or specific queries from the teacher.
- **Syllabus & Lesson Planning Assistance**: Suggests lesson plans based on curriculum progress and class needs.
- **AI-Powered Explanations**: Provides simple, AI-generated explanations for complex topics.
- **Multi-Agent System**: Different agents manage specific tasks like generating visuals, creating quizzes, summarizing sessions, and suggesting content.

## Technologies Used
- **Python**: Core language for developing the application.
- **PyQt5**: GUI framework for building the desktop application interface.
- **Whisper API**: For speech-to-text conversion.
- **OpenAI GPT**: For generating AI-based explanations, quizzes, and content suggestions.
- **FAISS**: For storing and retrieving semantic memory of class sessions.
- **SQLite**: For storing past lessons, class summaries, and student interactions.
- **gTTS / pyttsx3**: For text-to-speech capabilities for voice-based feedback.
- **Pillow / OpenCV**: For handling and displaying images and visual content.

## Installation

### Prerequisites
Ensure you have Python 3.7+ installed.

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/smartboard-teaching-assistant.git
   cd smartboard-teaching-assistant
'''
2. **Install dependencies: Install the required Python packages using pip:**

```bash
pip install -r requirements.txt
```
3. Install additional libraries (if needed):
- PyQt5 for GUI development
- Whisper API for speech recognition
- OpenAI GPT for AI-powered text generation

4. Set up an GEMINI API key: Sign up at Gemini and get your API key. Add the key to your environment variables:
```
bash
export OPENAI_API_KEY="your-api-key"
```
## Running the Application
After setting up the dependencies, you can start the application by running:
```
bash
python app.py
```

## Folder Structure
```
bash
smartboard_ai/
├── gui/                     # PyQt5 interface files
│   ├── main_window.py       # Main window for smartboard interface
│   └── output_display.py    # Handles display of generated content
├── audio/                   # Audio handling files
│   ├── recorder.py          # Handles voice input and speech-to-text
│   └── wake_word.py         # Detects wake word for triggering actions
├── ai_engine/               # Core AI functionality
│   ├── planner.py           # Handles task delegation to agents
│   ├── image_gen.py         # Visual content generation
│   ├── quiz_gen.py          # Quiz generation logic
│   ├── summarizer.py        # Class session summarization
│   └── chem_lab_agent.py    # Placeholder for future Chemistry Lab integration
├── memory/                  # Stores class history and memory
│   └── context_manager.py   # Manages class memory and interactions
├── database/                # Stores SQLite database for session storage
├── assets/                  # Contains images, icons, or media files
├── requirements.txt         # List of required Python packages
└── app.py                   # Main application entry point

```

## How to Use
1. Start the Application: Once the app is running, you'll be presented with a smartboard interface. The teacher can speak into the microphone or type commands into the text input box.

2. Voice Commands:
- "Show me a diagram of the heart."
- "Can you summarize today's lesson?"
- "Generate a quiz on photosynthesis."

3. Real-Time Interaction: The AI will respond by:
- Displaying generated images or videos.
- Summarizing class content.
- Creating and displaying interactive quizzes.

4. End of Class Summary: The teacher can ask, "What did we study yesterday?" or "Summarize the class," and the AI will pull the information from past sessions and provide a summary.

## 📸 Screenshots

### 🖥️ Main Smartboard Interface
![Smartboard Interface](screenshots/smartboard_interface.png)

### 🎤 Voice Command in Action
![Voice Command](screenshots/voice_command.png)

### 🧠 AI-Generated Quiz
![Quiz Generation](screenshots/quiz_generation.png)

### 📊 Class Summary View
![Class Summary](screenshots/class_summary.png)


## Future Enhancements
- Chemistry Virtual Lab: Add interactive chemical reactions and lab simulations.
- AI-Assisted Grade Tracking: Track student progress through quizzes and performance metrics.
- Enhanced Visual Content: Use more advanced models for 3D rendering or animations.
- Real-time Feedback: Provide real-time feedback on student understanding based on quiz performance.

## Contributing
If you'd like to contribute to this project, feel free to fork the repository and submit a pull request with your enhancements or bug fixes. Please ensure your code is well-documented and follows the style guide.

## License
This project is licensed under the MIT License - see the LICENSE file for details.
