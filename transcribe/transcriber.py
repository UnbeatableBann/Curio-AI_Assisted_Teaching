"""
transcriber.py
Whisper-based transcriber helper.

- Loads a Whisper model once.
- Provides `transcribe_bytes` and `transcribe_file`.
- Writes a temporary WAV file for raw PCM bytes and cleans up after transcription.
- Thread-safe usage is recommended by using an external lock (the orchestrator does that).
"""

import os
import tempfile
import logging
from typing import Optional

try:
    import torch
    import whisper
except Exception as e:
    whisper = None
    torch = None
    logging.warning("Could not import whisper/torch: %s", e)


class Transcriber:
    """
    Wrapper around whisper to transcribe audio.

    Note:
    - The easiest and most compatible input for this wrapper is raw 16-bit PCM (mono) at 16000 Hz.
    - If your audio has a different sample rate, pass sample_rate to transcribe_bytes and it will add the corresponding WAV header.
    """

    def __init__(self, model_name: str = "large", device: Optional[str] = None, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        if whisper is None:
            raise RuntimeError("whisper package is required but failed to import.")
        # choose device automatically if not provided
        if device:
            self.device = device
        else:
            self.device = "cuda" if torch is not None and torch.cuda.is_available() else "cpu"

        self.logger.info("Loading Whisper model '%s' on device '%s' ...", model_name, self.device)
        # Load model once (can take time & memory)
        self.model = whisper.load_model(model_name, device=self.device)
        self.logger.info("Whisper model loaded.")

    def transcribe_bytes(self, audio_bytes: bytes, sample_rate: int = 16000, language: Optional[str] = "en", fp16: bool = False) -> str:
        """
        Transcribe raw PCM bytes by writing a temporary WAV and calling Whisper.
        :param audio_bytes: raw PCM bytes (16-bit little-endian)
        :param sample_rate: sample rate in WAV header (int)
        :param language: optional language hint (e.g., "en")
        :param fp16: whether to use fp16 decoding (useful with GPU).
        :return: recognized text (string)
        """
        import wave

        tmp = None
        try:
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp.close()
            wav_path = tmp.name
            with wave.open(wav_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(sample_rate)
                wf.writeframes(audio_bytes)

            result = self.model.transcribe(wav_path, fp16=fp16, language=language)
            text = result.get("text", "").strip()
            return text
        except Exception as e:
            self.logger.exception("transcribe_bytes failed: %s", e)
            return ""
        finally:
            if tmp is not None:
                try:
                    os.remove(tmp.name)
                except Exception:
                    pass

    def transcribe_file(self, file_path: str, language: Optional[str] = "en", fp16: bool = False) -> str:
        """
        Transcribe an existing audio file using whisper (ffmpeg-backed support).
        :param file_path: path to audio file (wav, mp3, etc.)
        """
        try:
            result = self.model.transcribe(file_path, fp16=fp16, language=language)
            return result.get("text", "").strip()
        except Exception as e:
            self.logger.exception("transcribe_file failed: %s", e)
            return ""

transcribers = Transcriber(model_name="large")