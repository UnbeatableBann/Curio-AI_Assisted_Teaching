from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO, emit
import threading, os, time
import wave, sqlite3, pyaudio, pvporcupine
from datetime import datetime
import speech_recognition as sr
from langchain.agents import initialize_agent, AgentType
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.tools import Tool
from dotenv import load_dotenv
import atexit

from db_manager import save_audio_to_db
from agents import handle_query

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*") 
load_dotenv()

# ENV config
PICOVOICE_API_KEY = os.getenv('PICOVOICE_API_KEY')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
Audio_folder= "audio_recording_folder"
os.makedirs(Audio_folder, exist_ok=True)

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

# Picovoice config
WAKE_WORD_FOLDER = os.path.join(os.getcwd(), "Wakeup word")
WAKEUP_WORD_PATH = os.path.join(WAKE_WORD_FOLDER, "Hey-Echo_en_windows_v3_0_0.ppn")

# Initialize Porcupine
gemini_llm= ChatGoogleGenerativeAI(model="gemini-2.0-flash", google_api_key=GEMINI_API_KEY, temperature=0.7)

# === 👷‍♂️👷‍♂️👷‍♂️Helper Functions👷‍♂️👷‍♂️👷‍♂️ ===

@atexit.register
def cleanup():
    print("🔚 Shutting down: terminating PyAudio instance.")
    pa.terminate()

# === 🗺️🗺️🗺️ROUTES🗺️🗺️🗺️ ===

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start_recording', methods=['POST'])
def start_recording():
    global porcupine
    porcupine = pvporcupine.create(access_key=PICOVOICE_API_KEY, keyword_paths=[WAKEUP_WORD_PATH])
    if not os.path.exists(WAKEUP_WORD_PATH):
        raise FileNotFoundError(f"Wake word file not found: {WAKEUP_WORD_PATH}")
    
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
        while wake_word_thread_running.is_set():
            time.sleep(0.1)
        if 'porcupine' in globals():
            porcupine.delete()
        return jsonify({"message": "Recording stopped."})
    return jsonify({"error": "Not currently recording."})

# === 🧵🧵🧵THREAD FUNCTIONS🧵🧵🧵 ===

def continuous_recording():
    print("🎙️ Continuous recording started.")
    try:
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
        file_path = os.path.join(Audio_folder, filename)

        start_time = time.time()
        last_action_time = start_time
        ACTION_INTERVAL = 120  # 2 minutes in seconds

        while recording_active.is_set():
            data = stream.read(CHUNK)
            frames.append(data)

            current_time = time.time()
            # Every 2 minutes, trigger autonomous agent action
            if (current_time - last_action_time) >= ACTION_INTERVAL:
                print("⏰ 2 minutes reached, triggering autonomous agent action.")
                # Use a copy of frames for the last 2 minutes
                frames_for_action = frames.copy()
                threading.Thread(target=autonomous_agent_action, args=(frames_for_action,), daemon=True).start()
                last_action_time = current_time
                frames = []  # Reset frames for next interval

        stream.stop_stream()
        stream.close()

        with wave.open(file_path, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(pa.get_sample_size(AUDIO_FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(b''.join(frames))

        save_audio_to_db(filename)
        print(f"✅ Recording session saved: {filename}")
    
    except Exception as e:
        print(f"❌ Error continously audio recording stream: {e}")

def autonomous_agent_action(frames):
    """ 
    Process the last 2 minutes of audio and trigger autonomous agent action.
    """
    audio_data = sr.AudioData(b''.join(frames), RATE, pa.get_sample_size(AUDIO_FORMAT))
    recognizer = sr.Recognizer()
    try:
        print("🧠 Transcribing 2-min audio for autonomous agent action...")
        transcript = recognizer.recognize_google(audio_data).lower()
        print(f"🗣️ Transcript: {transcript}")

        # Call agent with full transcript
        prompt = (
            f"Here is a transcript of a lecture or meeting:\n\n{transcript}\n\n"
            "Decide what actions to take based on the content. "
            "You can generate a summary, create a quiz, generate related images, or create a 3D model if appropriate. "
            "You are free to use multiple tools if necessary. "
            "If the transcript is not useful, say so."
        )

        handle_query(prompt)
        print("🧠 Autonomous Agent Decision & Output sent to side panel.")
    except Exception as e:
        print(f"❌ Error in autonomous agent action: {e}")

def detect_wake_word():
    print("👂 Wake word detection started.")
    try:
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
                print("🚀 Wake word 'Echo' detected!")
                threading.Thread(target=record_after_wake_word, daemon=True).start()

        stream.stop_stream()
        stream.close()
        wake_word_thread_running.clear()
    
    except Exception as e:
        print(f"❌ Error while detecting wakeup word: {e}")


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
        handle_query(command)

    except sr.UnknownValueError:
        print("❌ Google Speech Recognition could not understand the audio.")
    except sr.RequestError as e:
        print(f"❌ Could not request results from Google Speech Recognition service; {e}")


# === RUN APP ===
if __name__ == '__main__':
    socketio.run(app, debug=True)
