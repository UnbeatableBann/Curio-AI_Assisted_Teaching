"""
wakeword.py
Robust Porcupine wake-word detector wrapper.

- Buffers incoming raw PCM bytes and feeds properly-sized frames to Porcupine.
- Accepts keyword_paths or single keyword path, and an access_key if required.
- Calls the provided callback when the wake-word is detected.
"""

import logging
from typing import Callable, Iterable, Optional, Union
from config.settings import settings

try:
    import pvporcupine
except Exception as e:
    pvporcupine = None
    logging.warning("pvporcupine import failed: %s", e)


class WakeWordDetector:
    """
    Wake word detector using Picovoice Porcupine.

    Usage:
        detector = WakeWordDetector(keyword_paths=["/path/to/keyword.ppn"], access_key="YOUR_KEY")
        detector.start(callback=my_callback)
        # feed raw PCM frames via detector.process_frame(pcm_bytes)
        detector.stop()
    """

    def __init__(
        self,
        keyword_paths: Union[str, Iterable[str]],
        access_key: Optional[str] = None,
        sensitivities: Optional[Iterable[float]] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """
        :param keyword_paths: A single path or an iterable of porcupine keyword file paths (.ppn).
        :param access_key: Picovoice access key (if required by your pvporcupine package).
        :param sensitivities: list of sensitivities matching number of keywords (0..1).
        """
        self._logger = logger or logging.getLogger(__name__)
        self._access_key = access_key
        if isinstance(keyword_paths, str):
            self._keyword_paths = [keyword_paths]
        else:
            self._keyword_paths = list(keyword_paths)
        self._sensitivities = list(sensitivities) if sensitivities is not None else None

        self._porcupine = None
        self._running = False
        self._callback: Optional[Callable[[], None]] = None

        # internal byte buffer for assembling frames of the correct length
        self._byte_buffer = bytearray()
        self.frame_length = None  # samples per frame (int)
        self.sample_rate = None  # expected sample rate (int)

    def start(self, callback: Callable[[], None]):
        """
        Initialize porcupine and register callback.
        :param callback: function to call when wake word is detected (no args).
        """
        if pvporcupine is None:
            raise RuntimeError("pvporcupine is not installed or failed to import.")

        if self._running:
            self._logger.debug("WakeWordDetector already started.")
            return

        try:
            # create porcupine instance
            create_kwargs = {
                "keyword_paths": self._keyword_paths,
            }
            if self._access_key:
                create_kwargs["access_key"] = self._access_key
            if self._sensitivities:
                create_kwargs["sensitivities"] = self._sensitivities

            self._porcupine = pvporcupine.create(**create_kwargs)
            # porcupine exposes attributes frame_length and sample_rate
            self.frame_length = getattr(self._porcupine, "frame_length", None)
            self.sample_rate = getattr(self._porcupine, "sample_rate", None)

            if self.frame_length is None or self.sample_rate is None:
                # fallback: typical Porcupine values if not provided (rare)
                self.frame_length = 512
                self.sample_rate = 16000

            self._callback = callback
            self._running = True
            self._byte_buffer = bytearray()
            self._logger.info("WakeWordDetector started (frame_length=%s, sample_rate=%s)", self.frame_length, self.sample_rate)
        except Exception as e:
            self._logger.exception("Failed to start Porcupine: %s", e)
            raise

    def stop(self):
        """
        Stop the detector and release resources.
        """
        if not self._running:
            return
        try:
            self._running = False
            if self._porcupine:
                try:
                    self._porcupine.delete()
                except Exception:
                    # some pvporcupine versions use 'delete'
                    pass
                self._porcupine = None
            self._byte_buffer = bytearray()
            self._logger.info("WakeWordDetector stopped.")
        except Exception as e:
            self._logger.exception("Error stopping WakeWordDetector: %s", e)

    def process_frame(self, pcm_bytes: bytes) -> bool:
        """
        Feed raw PCM bytes into the detector. This method buffers bytes internally
        until it has exactly (frame_length * 2) bytes (16-bit samples) and then calls porcupine.process().

        :param pcm_bytes: raw little-endian 16-bit PCM bytes (mono).
        :return: True if wake word detected for any slice processed, otherwise False.
        """
        if not self._running or self._porcupine is None:
            return False

        if not isinstance(pcm_bytes, (bytes, bytearray)):
            raise TypeError("pcm_bytes must be bytes or bytearray (16-bit PCM)")

        # append incoming bytes
        self._byte_buffer.extend(pcm_bytes)
        bytes_per_frame = self.frame_length * 2  # 2 bytes per sample (16-bit)
        detected = False

        # Process as many non-overlapping frames as available.
        while len(self._byte_buffer) >= bytes_per_frame:
            frame_bytes = bytes(self._byte_buffer[:bytes_per_frame])
            # convert to signed 16-bit array view (required by porcupine)
            pcm = memoryview(frame_bytes).cast("h")
            try:
                index = self._porcupine.process(pcm)
                if index >= 0:
                    # detected keyword index
                    self._logger.debug("Wake word detected (keyword_index=%s)", index)
                    if self._callback:
                        try:
                            self._callback()
                        except Exception as cb_exc:
                            self._logger.exception("Wake word callback raised exception: %s", cb_exc)
                    detected = True
            except Exception as e:
                # Log and continue; porcupine processing can raise for malformed frames
                self._logger.exception("Porcupine process() exception: %s", e)

            # remove consumed bytes (non-overlapping)
            del self._byte_buffer[:bytes_per_frame]

        return detected

wake = WakeWordDetector(
        keyword_paths=settings.WAKEUP_WORD_PATH,
        access_key=settings.PICOVOICE_API_KEY,
    )