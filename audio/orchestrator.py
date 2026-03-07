"""
orchestrator.py

Coordinates:
- continuous audio capture (writes to per-session PCM file)
- Porcupine wake-word detection (via WakeWordDetector)
- short command recording & transcription (non-disruptive)
- full-session transcription & WAV saving on stop
- "live transcription" (transcribe audio so far without stopping recording)

Design notes:
- The recorder keeps calling `audio_callback(frame, sample_rate, sample_width, channels)`.
- This module handles writing to disk (session PCM file) and buffering command audio when wake word triggers.
- For robustness and scalability we stream raw PCM to disk and only create WAV / transcribe on demand.
"""

import os
import threading
import time
import wave
import logging
from datetime import datetime
from typing import Optional, Callable

from .transcriber import transcribers

# Local imports
# from wakeword import WakeWordDetector  # user will instantiate and pass detector or pass callback

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)


class ContinuousClassRecorder:
    """
    Orchestrator that receives PCM frames from an audio source (AudioRecorder),
    writes them continuously to a session PCM file, detects wake word via an external
    WakeWordDetector (which should call `on_wake_word_detected()`), records short commands,
    and transcribes commands and final session audio using the provided Transcriber.
    """

    def __init__(
        self,
        transcriber,
        session_dir_root: str = "recordings",
        transcripts_dir: str = "transcripts",
        record_seconds_on_command: float = 4.0,
        expected_sample_rate: int = 16000,
        expected_sample_width: int = 2,
        expected_channels: int = 1,
        command_callback: Optional[Callable[[str], None]] = None,
        auto_start_session: bool = True,
    ):
        """
        :param transcriber: instance of Transcriber (has transcribe_bytes and transcribe_file)
        :param session_dir_root: where session folders will be created
        :param transcripts_dir: where transcripts are saved
        :param record_seconds_on_command: how many seconds to collect for each command after wakeword
        :param expected_sample_rate: expected sample rate for audio frames
        :param expected_sample_width: sample width in bytes (2 for 16-bit)
        :param expected_channels: number of channels (1 = mono)
        :param command_callback: optional callable(text) to receive transcribed commands
        :param auto_start_session: if True, a session folder will be made immediately
        """
        self.transcriber = transcriber
        self.record_seconds_on_command = float(record_seconds_on_command)
        self.expected_sample_rate = expected_sample_rate
        self.expected_sample_width = expected_sample_width
        self.expected_channels = expected_channels
        self.command_callback = command_callback

        # directories
        self.session_dir_root = session_dir_root
        self.transcripts_dir = transcripts_dir
        os.makedirs(self.session_dir_root, exist_ok=True)
        os.makedirs(self.transcripts_dir, exist_ok=True)

        # session-managed resources
        self._session_lock = threading.Lock()
        self._session_active = False
        self._session_dir = None
        self._pcm_path = None
        self._pcm_file = None  # open file handle for append mode
        self._session_start_time = None

        # command recording state
        self._command_lock = threading.Lock()
        self._recording_command = False
        self._command_frames = []  # small list of bytes for current command

        # transcription lock (Whisper is heavy, serialize access)
        self._transcribe_lock = threading.Lock()

        # optional wake-detector instance (set by caller) - orchestrator does not create it
        self.wake_detector = None

        if auto_start_session:
            self.start_session()

    # ---------------------
    # Session management
    # ---------------------
    def start_session(self, session_name: Optional[str] = None):
        """
        Start a new session directory & open PCM file for appending.
        You should call this before starting the recorder; if you don't, the first audio callback will auto-start.
        """
        with self._session_lock:
            if self._session_active:
                logger.debug("Session already active: %s", self._session_dir)
                return

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            session_name = session_name or f"session_{ts}"
            self._session_dir = os.path.join(self.session_dir_root, session_name)
            os.makedirs(self._session_dir, exist_ok=True)
            self._pcm_path = os.path.join(self._session_dir, "class_audio.pcm")
            # Open PCM file handle for append in binary mode and keep it open for the session
            # We write raw PCM bytes as they arrive. WAV header will be created on finalize.
            self._pcm_file = open(self._pcm_path, "ab")
            self._session_active = True
            self._session_start_time = time.time()
            logger.info("Session started: %s", self._session_dir)

    def _ensure_session(self):
        if not self._session_active:
            self.start_session()

    def attach_wake_detector(self, wake_detector):
        """
        Attach a WakeWordDetector instance. The detector should call orchestrator.on_wake_word_detected()
        as its callback, or the orchestrator will call wake_detector.process_frame() from audio_callback.
        """
        self.wake_detector = wake_detector

    # ---------------------
    # Audio input callback
    # ---------------------
    def audio_callback(self, frame: bytes, sample_rate: int = 16000, sample_width: int = 2, channels: int = 1):
        """
        This function receives incoming PCM frames from the audio capture layer.
        - Writes the frame to the session PCM file (append).
        - If command recording is active, appends to the command buffer.
        - Forwards the raw bytes to the wake detector (if attached).
        :param frame: raw PCM bytes (16-bit little-endian samples)
        :param sample_rate: incoming sample rate (Hz)
        :param sample_width: sample width in bytes
        :param channels: number of channels
        """
        # ensure session exists
        self._ensure_session()

        # basic parameter check
        if sample_rate != self.expected_sample_rate:
            logger.debug("Frame sample_rate != expected (%s != %s); continuing but transcription quality may suffer",
                         sample_rate, self.expected_sample_rate)

        if sample_width != self.expected_sample_width or channels != self.expected_channels:
            logger.debug("Frame format (width=%s, channels=%s) differs from expected (width=%s, channels=%s)",
                         sample_width, channels, self.expected_sample_width, self.expected_channels)

        # Append to PCM file (atomic with file lock)
        with self._session_lock:
            if self._pcm_file:
                try:
                    self._pcm_file.write(frame)
                    # it is helpful to flush regularly so data is on disk in case of crash
                    self._pcm_file.flush()
                    os.fsync(self._pcm_file.fileno())
                except Exception as e:
                    logger.exception("Failed to write to PCM file: %s", e)

        # If we are currently recording a command, append to small command buffer
        if self._recording_command:
            with self._command_lock:
                self._command_frames.append(frame)

        # Forward bytes to attached wake detector (it will buffer frames as it needs)
        if self.wake_detector:
            try:
                # wake_detector.process_frame expects raw PCM bytes
                self.wake_detector.process_frame(frame)
            except Exception as e:
                logger.exception("Wake detector process_frame raised an exception: %s", e)

    # ---------------------
    # Wake-word handling -> command recording
    # ---------------------
    def on_wake_word_detected(self):
        """
        Called by the wake detector when a wake word is seen.
        Starts a short command capture window in the background (non-blocking).
        If a command capture is already in-flight, this will be ignored.
        """
        logger.info("Wake word detected -> starting command capture for %.2f seconds", self.record_seconds_on_command)
        with self._command_lock:
            if self._recording_command:
                logger.info("Command capture already in progress; ignoring new wake-word until current finishes.")
                return
            # reset command buffer
            self._command_frames = []
            self._recording_command = True

        # spawn background timer thread to stop command capture after timeout and transcribe
        t = threading.Thread(target=self._capture_and_transcribe_command, daemon=True)
        t.start()

    def _capture_and_transcribe_command(self):
        """
        Wait for the configured command duration while frames accumulate via audio_callback.
        When timeout expires, join frames, transcribe, and call command_callback if provided.
        """
        try:
            time.sleep(self.record_seconds_on_command)  # while frames are appended by audio_callback

            with self._command_lock:
                self._recording_command = False
                frames = b"".join(self._command_frames)
                self._command_frames = []

            if not frames:
                logger.info("No audio frames captured for command.")
                return

            logger.info("Transcribing captured command (~%s bytes)...", len(frames))
            with self._transcribe_lock:
                try:
                    # pass sample_rate expected by this orchestrator
                    text = self.transcriber.transcribe_bytes(frames, sample_rate=self.expected_sample_rate)
                except Exception as e:
                    logger.exception("Command transcription failed: %s", e)
                    text = ""

            logger.info("Command transcription result: %s", text)
            if self.command_callback:
                try:
                    self.command_callback(text)
                except Exception:
                    logger.exception("command_callback raised an exception.")

        except Exception as e:
            logger.exception("Error during command capture/transcribe: %s", e)
            # Ensure state reset
            with self._command_lock:
                self._recording_command = False
                self._command_frames = []

    # ---------------------
    # Finalize/save session audio and transcription
    # ---------------------
    def _pcm_to_wav(self, pcm_path: str, wav_path: str, sample_rate: int, sample_width: int, channels: int):
        """
        Convert raw PCM file to WAV file by adding a header (writes to wav_path).
        """
        try:
            with open(pcm_path, "rb") as f:
                pcm_bytes = f.read()
            with wave.open(wav_path, "wb") as wf:
                wf.setnchannels(channels)
                wf.setsampwidth(sample_width)
                wf.setframerate(sample_rate)
                wf.writeframes(pcm_bytes)
            logger.info("Successfully wrote WAV: %s", wav_path)
            return True
        except Exception as e:
            logger.exception("Failed to produce WAV file: %s", e)
            return False

    def stop_and_finalize(self, transcribe_full: bool = True) -> dict:
        """
        Stop session (close PCM file), convert to WAV, create transcript file (if transcribe_full True).
        Returns a dict with keys: session_dir, wav_path, transcript_path (or None), transcript_text (or None).
        """
        with self._session_lock:
            if not self._session_active:
                logger.info("No active session to stop.")
                return {"session_dir": None, "wav_path": None, "transcript_path": None, "transcript_text": None}

            # Close PCM file handle
            try:
                if self._pcm_file:
                    self._pcm_file.flush()
                    os.fsync(self._pcm_file.fileno())
                    self._pcm_file.close()
            except Exception as e:
                logger.exception("Error closing pcm file: %s", e)
            finally:
                self._pcm_file = None
                pcm_path = self._pcm_path

            # Create WAV file path under session dir
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            wav_path = os.path.join(self._session_dir, f"class_audio_{ts}.wav")

            # convert pcm -> wav
            converted = self._pcm_to_wav(pcm_path, wav_path, self.expected_sample_rate, self.expected_sample_width, self.expected_channels)

            transcript_text = None
            transcript_path = None
            if converted and transcribe_full:
                logger.info("Transcribing full session (this may take time for long recordings)...")
                try:
                    with self._transcribe_lock:
                        transcript_text = self.transcriber.transcribe_file(wav_path)
                except Exception as e:
                    logger.exception("Full session transcription failed: %s", e)
                    transcript_text = ""

                # Save transcript to transcripts dir with timestamped filename
                transcript_fn = datetime.utcnow().strftime("transcript_%Y%m%d_%H%M%S.txt")
                transcript_path = os.path.join(self.transcripts_dir, transcript_fn)
                try:
                    with open(transcript_path, "w", encoding="utf-8") as tf:
                        tf.write(transcript_text or "")
                    logger.info("Transcript saved: %s", transcript_path)
                except Exception as e:
                    logger.exception("Failed to save transcript: %s", e)
                    transcript_path = None

            # mark session inactive
            session_dir = self._session_dir
            self._session_active = False
            self._session_dir = None
            self._pcm_path = None
            self._session_start_time = None

            return {"session_dir": session_dir, "wav_path": wav_path if converted else None, "transcript_path": transcript_path, "transcript_text": transcript_text}


    # ---------------------
    # Interval-based transcription
    # ---------------------
    def get_transcription_interval(self, start_sec: float, end_sec: float, language: str = "en") -> str:
        """
        Transcribe only a segment of the current PCM file between start_sec and end_sec.
        :param start_sec: start time (seconds from beginning of session)
        :param end_sec: end time (seconds from beginning of session)
        """
        if not self._pcm_path or not os.path.exists(self._pcm_path):
            logger.info("No PCM data to transcribe.")
            return ""

        bytes_per_sec = self.expected_sample_rate * self.expected_sample_width * self.expected_channels
        start_byte = int(start_sec * bytes_per_sec)
        length_bytes = int((end_sec - start_sec) * bytes_per_sec)

        try:
            with open(self._pcm_path, "rb") as f:
                f.seek(start_byte)
                segment = f.read(length_bytes)
        except Exception as e:
            logger.exception("Error reading PCM interval: %s", e)
            return ""

        if not segment:
            logger.info("No audio data found in requested interval.")
            return ""

        with self._transcribe_lock:
            try:
                text = self.transcriber.transcribe_bytes(
                    segment,
                    sample_rate=self.expected_sample_rate,
                    language=language,
                )
                return text
            except Exception as e:
                logger.exception("Interval transcription failed: %s", e)
                return ""

    # ---------------------
    # Live transcription (no stop)
    # ---------------------
    def get_live_transcription(self, language: Optional[str] = "en", fp16: bool = False) -> str:
        """
        Transcribe the current recording so far WITHOUT stopping recording.
        This reads the current PCM file (so the transcription reflects everything appended so far).
        WARNING: for very long recordings this can take a long time and is resource-intensive.
        :param language: optional language hint
        :param fp16: pass fp16 to Whisper (effective when using GPU)
        :return: transcript text (string)
        """
        with self._session_lock:
            if not self._session_active or not os.path.exists(self._pcm_path):
                logger.info("No session or no audio data present for live transcription.")
                return ""

            # flush file to ensure bytes on disk
            try:
                self._pcm_file.flush()
                os.fsync(self._pcm_file.fileno())
            except Exception:
                pass

            # read bytes
            try:
                with open(self._pcm_path, "rb") as f:
                    pcm_bytes = f.read()
            except Exception as e:
                logger.exception("Failed to read PCM for live transcription: %s", e)
                return ""

        # send to transcriber
        with self._transcribe_lock:
            try:
                text = self.transcriber.transcribe_bytes(pcm_bytes, sample_rate=self.expected_sample_rate, language=language, fp16=fp16)
                return text
            except Exception as e:
                logger.exception("Live transcription failed: %s", e)
                return ""

    # ---------------------
    # Utility functions
    # ---------------------
    def list_transcripts(self):
        """
        Returns a list of transcript file paths currently saved in the transcripts directory.
        """
        files = []
        try:
            for fn in sorted(os.listdir(self.transcripts_dir)):
                path = os.path.join(self.transcripts_dir, fn)
                if os.path.isfile(path):
                    files.append(path)
        except Exception as e:
            logger.exception("Error listing transcripts: %s", e)
        return files
    
    def get_transcript_by_date(self, date_str: str) -> Optional[str]:
        """
        Retrieve the transcript text for a given date.
        :param date_str: date string in format "YYYYMMDD" (e.g., "20250910")
        :return: transcript text if found, else None
        """
        try:
            for fn in sorted(os.listdir(self.transcripts_dir)):
                if fn.startswith("transcript_") and fn.endswith(".txt"):
                    if date_str in fn:  # match the date portion
                        path = os.path.join(self.transcripts_dir, fn)
                        with open(path, "r", encoding="utf-8") as f:
                            return f.read()
            logger.info("No transcript found for date: %s", date_str)
            return None
        except Exception as e:
            logger.exception("Error retrieving transcript for %s: %s", date_str, e)
            return None

    def get_session_dir(self):
        return self._session_dir

    def save_current_pcm_copy_as_wav(self, out_wav_path: str) -> bool:
        """
        Create a WAV copy of the current PCM file (useful for manual saving).
        """
        with self._session_lock:
            if not self._session_active or not os.path.exists(self._pcm_path):
                logger.info("No active PCM to save.")
                return False
            try:
                # flush file
                self._pcm_file.flush()
                os.fsync(self._pcm_file.fileno())
            except Exception:
                pass
            pcm_path = self._pcm_path

        return self._pcm_to_wav(pcm_path, out_wav_path, self.expected_sample_rate, self.expected_sample_width, self.expected_channels)

def on_command_text(text):
    print("Received command text:", text)

orchestrators = ContinuousClassRecorder(
        transcribers, record_seconds_on_command=4.0, command_callback=on_command_text
    )
