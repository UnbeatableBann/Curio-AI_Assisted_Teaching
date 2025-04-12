from flask import Flask, request, jsonify, render_template
import threading, os
import wave, sqlite3, pyaudio, pvporcupine
from datetime import datetime
import speech_recognition as sr

from pdf_summary import PDFSummarizer
from quiz_generator import QuizGenerator
from visual_generator import VisualGenerator
from class_summary import summarize_class

app = Flask(__name__)

# ENV config
PICOVOICE_API_KEY = os.getenv('PICOVOICE_API_KEY')
AUDIO_DB = "audio_recordings.db"

# Audio config
AUDIO_FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 512
RECORD_SECONDS_AFTER_WAKE = 5
pa = pyaudio.PyAudio()

# Control flags
recording_active = threading.Event()
wake_word_detected = threading.Event()
wake_word_thread_running = threading.Event()

# Initialize Porcupine
porcupine = pvporcupine.create(access_key=PICOVOICE_API_KEY, keyword_paths=["Wakeup word\Hey-Echo_en_windows_v3_0_0.ppn"])


# === ROUTES ===

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start_recording', methods=['POST'])
def start_recording():
    if not recording_active.is_set():
        recording_active.set()
        threading.Thread(target=continuous_recording, daemon=True).start()
        
        if not wake_word_thread_running.is_set():
            wake_word_thread_running.set()
            threading.Thread(target=detect_wake_word, daemon=True).start()

        return jsonify({"message": "Recording and wake word listening started."})
    return jsonify({"error": "Already recording."})

@app.route('/stop_recording', methods=['POST'])
def stop_recording():
    if recording_active.is_set():
        recording_active.clear()
        porcupine.delete()
        pa.terminate()
        return jsonify({"message": "Recording stopped."})
    return jsonify({"error": "Not currently recording."})


@app.route('/pdf_summary', methods=['POST'])
def pdf_summary():
    question = request.json.get('question', 'What is the main topic of the document?')
    summarizer = PDFSummarizer()
    response = summarizer.user_input(question)
    return jsonify({"response": response})

@app.route('/quiz_generator', methods=['POST'])
def quiz_generator():
    input_text = request.json.get('input', 'Generate a quiz based on the class data.')
    quiz_generator = QuizGenerator()
    quiz = quiz_generator.generate_quiz(input_text)
    return jsonify({"quiz": quiz}) if quiz else jsonify({"error": "Quiz generation failed."})

@app.route('/visual_generator', methods=['POST'])
def visual_generator():
    query = request.json.get('query', 'sunset over the mountains')
    visual_generator = VisualGenerator()
    best_image, _ = visual_generator.run_all_image_generators(query)
    return jsonify({"best_image_url": best_image}) if best_image else jsonify({"error": "No image found."})

@app.route('/class_summary', methods=['GET'])
def class_summary():
    summary = summarize_class()
    return jsonify({"class_summary": summary}) if summary and summary != "None" else jsonify({"error": "No summary."})


# === THREAD FUNCTIONS ===

def continuous_recording():
    print("🎙️ Continuous recording started.")
    stream = pa.open(
        format=AUDIO_FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK
    )

    frames = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"recording_session_{timestamp}.wav"

    while recording_active.is_set():
        data = stream.read(CHUNK)
        frames.append(data)

    stream.stop_stream()
    stream.close()

    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(pa.get_sample_size(AUDIO_FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))

    save_audio_to_db(filename)
    print(f"✅ Recording session saved: {filename}")


def detect_wake_word():
    print("👂 Wake word detection started.")
    stream = pa.open(
        rate=porcupine.sample_rate,
        channels=CHANNELS,
        format=AUDIO_FORMAT,
        input=True,
        frames_per_buffer=porcupine.frame_length
    )

    while True:
        if not recording_active.is_set():
            break  # Exit when recording is stopped

        pcm = stream.read(porcupine.frame_length, exception_on_overflow=False)
        pcm = memoryview(pcm).cast('h')
        if porcupine.process(pcm) >= 0:
            print("🚀 Wake word 'Jarvis' detected!")
            threading.Thread(target=record_after_wake_word, daemon=True).start()

    stream.stop_stream()
    stream.close()
    wake_word_thread_running.clear()


def record_after_wake_word():
    print("🎧 Recording short command after wake word...")
    stream = pa.open(
        format=AUDIO_FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK
    )
    frames = []
    for _ in range(0, int(RATE / CHUNK * RECORD_SECONDS_AFTER_WAKE)):
        data = stream.read(CHUNK)
        frames.append(data)

    stream.stop_stream()
    stream.close()

    recognizer = sr.Recognizer()
    # Convert raw audio frames into AudioData for speech_recognition
    audio_data = sr.AudioData(b''.join(frames), RATE, pa.get_sample_size(AUDIO_FORMAT))

    try:
        print("🧠 Transcribing command using Google Speech Recognition...")
        command = recognizer.recognize_google(audio_data).lower()
        print(f"🗣️ Command: {command}")

        # You can now act on the command
        if "generate quiz" in command:
            print("📝 Trigger quiz generation.")
        elif "summarize class" in command:
            print("📘 Trigger class summary.")
        else:
            print("🤔 Command not recognized.")

    except sr.UnknownValueError:
        print("❌ Google Speech Recognition could not understand the audio.")
    except sr.RequestError as e:
        print(f"❌ Could not request results from Google Speech Recognition service; {e}")


def save_audio_to_db(filename):
    conn = sqlite3.connect(AUDIO_DB)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recordings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("INSERT INTO recordings (filename) VALUES (?)", (filename,))
    conn.commit()
    conn.close()


# === RUN APP ===
if __name__ == '__main__':
    app.run(debug=True)
