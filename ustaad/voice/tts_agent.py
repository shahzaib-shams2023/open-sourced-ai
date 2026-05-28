import os
from typing import Optional

class TTSAgent:
    """
    Lazy-loaded TTS Agent.
    Prevents model downloading and heavy initialization on module import.
    """
    def __init__(self, model_name: str = "tts_models/en/ljspeech/tacotron2-DDC"):
        self.model_name = model_name
        self._tts = None

    @property
    def tts(self):
        if self._tts is None:
            try:
                # Lazy import to avoid loading heavy TTS modules immediately
                from TTS.api import TTS
            except ImportError:
                raise ImportError(
                    "The 'coqui-tts' library is missing in your current environment.\n"
                    "To install it, run:\n"
                    "  pip install coqui-tts\n\n"
                    "Note: Windows users may require Visual Studio C++ build tools and PyTorch installed."
                )
            self._tts = TTS(model_name=self.model_name)
        return self._tts

    def speak(self, text: str, file_path: str = "output.wav"):
        """Synthesize text to an audio file."""
        self.tts.tts_to_file(
            text=text,
            file_path=file_path
        )


