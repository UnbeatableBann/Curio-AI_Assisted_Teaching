"""
recorder.py
A resilient non-blocking audio recorder using PyAudio.

- Captures raw 16-bit PCM frames via a background callback.
- Calls `frame_callback(in_data, sample_rate, sample_width, channels)` for each buffer.
- Provides utility to save raw PCM bytes into a WAV file using the configured format.
"""

import logging
import threading
from typing import Callable, Optional

from .orchestrator import orchestrators

try:
    import pyaudio
except Exception as e:
    pyaudio = None
    logging.warning("pyaudio import failed: %s", e)


class AudioRecorder:
    """
    AudioRecorder captures audio from the default (or specified) input device and calls
    the provided frame_callback for every buffer of audio captured.
    """

    def __init__(
        self,
        rate: int = 16000,
        chunk: int = 1024,
        channels: int = 1,
        format=None,
        frame_callback: Optional[Callable[[bytes, int, int, int], None]] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """
        :param rate: sample rate (Hz). Default 16000.
        :param chunk: frames per buffer (number of samples per channel).
        :param channels: number of channels (1 = mono).
        :param format: PyAudio format (defaults to pyaudio.paInt16).
        :param frame_callback: function(in_data, sample_rate, sample_width_bytes, channels)
        """
        self.logger = logger or logging.getLogger(__name__)
        if pyaudio is None:
            raise RuntimeError("PyAudio is required by AudioRecorder but failed to import.")

        self.rate = rate
        self.chunk = chunk
        self.channels = channels
        self.pyaudio_format = format if format is not None else pyaudio.paInt16
        self.audio_interface = pyaudio.PyAudio()
        self.stream = None
        self.running = False
        self.lock = threading.Lock()
        self.frame_callback = frame_callback

    def start(self, device_index: Optional[int] = None):
        """
        Start the input stream. Non-blocking; frames delivered to `frame_callback`.
        """
        with self.lock:
            if self.running:
                self.logger.debug("AudioRecorder already running.")
                return
            try:
                self.stream = self.audio_interface.open(
                    format=self.pyaudio_format,
                    channels=self.channels,
                    rate=self.rate,
                    input=True,
                    input_device_index=device_index,
                    frames_per_buffer=self.chunk,
                    stream_callback=self._internal_callback,
                )
                self.stream.start_stream()
                self.running = True
                print("AudioRecorder started.")
                self.logger.info("AudioRecorder started (rate=%s, chunk=%s, channels=%s)", self.rate, self.chunk, self.channels)
            except Exception as e:
                self.logger.exception("Failed to start audio stream: %s", e)
                raise

    def _internal_callback(self, in_data, frame_count, time_info, status):
        """
        This is called by PyAudio for each chunk. We forward the raw bytes to the user's callback.
        """
        if self.running and self.frame_callback:
            try:
                sample_width = self.audio_interface.get_sample_size(self.pyaudio_format)
            except Exception:
                sample_width = 2
            try:
                # forward the raw bytes and basic format meta
                self.frame_callback(in_data, self.rate, sample_width, self.channels)
            except Exception as e:
                # Do not allow exceptions in user callback to break the stream.
                self.logger.exception("Frame callback raised exception: %s", e)
        return (None, pyaudio.paContinue)

    def stop(self):
        """
        Stop and close the audio stream (non-destructive to the audio interface).
        """
        with self.lock:
            if not self.running:
                return
            try:
                if self.stream is not None:
                    if self.stream.is_active():
                        self.stream.stop_stream()
                    self.stream.close()
                self.stream = None
                self.running = False
                self.logger.info("AudioRecorder stopped.")
            except Exception as e:
                self.logger.exception("Error stopping recorder: %s", e)

    def close(self):
        """
        Stop and terminate the PyAudio interface (release resources).
        """
        self.stop()
        try:
            if self.audio_interface is not None:
                self.audio_interface.terminate()
                self.audio_interface = None
                self.logger.info("Audio interface terminated.")
        except Exception as e:
            self.logger.exception("Error terminating audio interface: %s", e)

    def save_wav(self, pcm_bytes: bytes, path: str, sample_rate: Optional[int] = None, sample_width: Optional[int] = None, channels: Optional[int] = None):
        """
        Save raw PCM bytes into a WAV file using the recorder's current format by default.
        :param pcm_bytes: raw 16-bit PCM bytes (little-endian)
        :param path: destination .wav path
        :param sample_rate: sample rate to write in header (defaults to self.rate)
        :param sample_width: sample width in bytes (defaults to audio_interface.get_sample_size)
        :param channels: number of channels (defaults to self.channels)
        """
        import wave
        sample_rate = sample_rate or self.rate
        channels = channels or self.channels
        try:
            sample_width = sample_width or self.audio_interface.get_sample_size(self.pyaudio_format)
        except Exception:
            sample_width = 2

        with wave.open(path, "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(sample_width)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_bytes)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.close()

recorder = AudioRecorder(
    rate=16000, chunk=1024, frame_callback=orchestrators.audio_callback
)