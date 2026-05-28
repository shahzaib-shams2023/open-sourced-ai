model = None

def transcribe(audio_path: str) -> str:
    """Lazy-load faster-whisper model and transcribe an audio file."""
    global model
    if model is None:
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise ImportError(
                "The 'faster-whisper' library is missing in your current environment.\n"
                "To install it, run:\n"
                "  pip install faster-whisper\n"
            )
        model = WhisperModel("base")
        
    segments, _ = model.transcribe(audio_path)
    text = ""
    for segment in segments:
        text += segment.text
    return text


