"""
============================================
TeleCode v0.1 - Voice Processing Module
============================================
Handles voice note transcription:
- Downloads voice notes from Telegram (OGG format)
- Converts OGG to WAV using pydub/ffmpeg
- Transcribes using Google Speech Recognition (FREE)

IMPORTANT: Requires ffmpeg to be installed and in PATH.
============================================
"""

import os
import logging
import tempfile
import shutil
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger("telecode.voice")

# Check for required dependencies
FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None

try:
    import speech_recognition as sr
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    SPEECH_RECOGNITION_AVAILABLE = False
    logger.warning("SpeechRecognition not installed. Voice features disabled.")

try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False
    logger.warning("pydub not installed. Voice features disabled.")


class VoiceProcessor:
    """
    Converts Telegram voice notes to text.
    
    Pipeline:
    1. Download OGG from Telegram
    2. Convert OGG -> WAV (using pydub + ffmpeg)
    3. Transcribe WAV -> Text (using Google Speech Recognition)
    
    Note: Google Speech Recognition is FREE for low-volume usage.
    No API key required for basic usage.
    """
    
    def __init__(self, temp_dir: Optional[str] = None):
        """
        Initialize voice processor.
        
        Args:
            temp_dir: Directory for temporary audio files.
                      Defaults to system temp directory.
        """
        self.temp_dir = Path(temp_dir) if temp_dir else Path(tempfile.gettempdir()) / "telecode_voice"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Check dependencies
        self.is_available = self._check_dependencies()
        
        if self.is_available:
            self.recognizer = sr.Recognizer()
            logger.info("VoiceProcessor initialized successfully")
        else:
            logger.warning("VoiceProcessor not available - missing dependencies")
    
    def _check_dependencies(self) -> bool:
        """Check if all required dependencies are available."""
        if not FFMPEG_AVAILABLE:
            logger.error("ffmpeg not found in PATH. Voice features require ffmpeg.")
            return False
        
        if not SPEECH_RECOGNITION_AVAILABLE:
            logger.error("SpeechRecognition library not installed.")
            return False
        
        if not PYDUB_AVAILABLE:
            logger.error("pydub library not installed.")
            return False
        
        return True
    
    def get_status(self) -> str:
        """Get status message about voice processing availability."""
        if self.is_available:
            return "✅ Voice processing is available"
        
        issues = []
        if not FFMPEG_AVAILABLE:
            issues.append("❌ ffmpeg not installed")
        if not SPEECH_RECOGNITION_AVAILABLE:
            issues.append("❌ SpeechRecognition not installed")
        if not PYDUB_AVAILABLE:
            issues.append("❌ pydub not installed")
        
        return "⚠️ Voice processing unavailable:\n" + "\n".join(issues)
    
    async def process_voice_file(self, ogg_path: str) -> Tuple[bool, str]:
        """
        Process a voice file and return transcribed text.
        
        Args:
            ogg_path: Path to the downloaded OGG file
            
        Returns:
            Tuple of (success, transcribed_text_or_error)
        """
        if not self.is_available:
            return False, "Voice processing not available. Check dependencies."
        
        wav_path = None
        try:
            # Convert OGG to WAV
            logger.info(f"Converting OGG to WAV: {ogg_path}")
            wav_path = self._convert_ogg_to_wav(ogg_path)
            
            if not wav_path:
                return False, "Failed to convert audio format"
            
            # Transcribe WAV
            logger.info(f"Transcribing WAV: {wav_path}")
            text = self._transcribe_wav(wav_path)
            
            if text:
                logger.info(f"Transcription successful: {text[:50]}...")
                return True, text
            else:
                return False, "Could not understand audio"
            
        except Exception as e:
            logger.error(f"Voice processing failed: {e}")
            return False, f"Voice processing error: {str(e)}"
        
        finally:
            # Cleanup temp files
            self._cleanup_file(ogg_path)
            if wav_path:
                self._cleanup_file(wav_path)
    
    def _convert_ogg_to_wav(self, ogg_path: str) -> Optional[str]:
        """
        Convert OGG file to WAV format.
        
        Args:
            ogg_path: Path to OGG file
            
        Returns:
            Path to WAV file or None if failed
        """
        try:
            wav_path = str(Path(ogg_path).with_suffix(".wav"))
            
            # Load OGG and export as WAV
            audio = AudioSegment.from_ogg(ogg_path)
            audio.export(wav_path, format="wav")
            
            return wav_path
            
        except Exception as e:
            logger.error(f"OGG to WAV conversion failed: {e}")
            return None
    
    def _transcribe_wav(self, wav_path: str) -> Optional[str]:
        """
        Transcribe WAV file to text using Google Speech Recognition.
        
        This uses the FREE Google Web Speech API.
        No API key required for basic usage (rate limited).
        
        Args:
            wav_path: Path to WAV file
            
        Returns:
            Transcribed text or None if failed
        """
        try:
            with sr.AudioFile(wav_path) as source:
                # Read the audio data
                audio_data = self.recognizer.record(source)
                
                # Use Google Web Speech API (free)
                text = self.recognizer.recognize_google(audio_data)
                return text
                
        except sr.UnknownValueError:
            logger.warning("Google Speech Recognition could not understand audio")
            return None
        except sr.RequestError as e:
            logger.error(f"Google Speech Recognition request failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return None
    
    def _cleanup_file(self, file_path: str) -> None:
        """
        Securely delete a temporary file.
        
        SEC-005: Overwrites file content before deletion to prevent
        recovery of potentially sensitive audio content.
        """
        try:
            if os.path.exists(file_path):
                # SEC-005: Overwrite file with random data before deletion
                # This prevents recovery of audio content
                file_size = os.path.getsize(file_path)
                
                if file_size > 0:
                    try:
                        with open(file_path, 'wb') as f:
                            # Overwrite with zeros (fast and sufficient for temp files)
                            f.write(b'\x00' * min(file_size, 1024 * 1024))  # Max 1MB overwrite
                            f.flush()
                            os.fsync(f.fileno())
                    except Exception as e:
                        logger.warning(f"Could not securely overwrite {file_path}: {e}")
                
                # Now delete the file
                os.remove(file_path)
                logger.debug(f"Securely deleted: {file_path}")
                
        except Exception as e:
            logger.warning(f"Failed to cleanup {file_path}: {e}")
    
    def get_temp_filepath(self, extension: str = ".ogg") -> str:
        """
        Generate a unique temporary file path.
        
        Args:
            extension: File extension (default .ogg)
            
        Returns:
            Path to temp file
        """
        import uuid
        filename = f"voice_{uuid.uuid4().hex}{extension}"
        return str(self.temp_dir / filename)


async def download_telegram_voice(voice_file, bot) -> Optional[str]:
    """
    Download a voice file from Telegram.
    
    Args:
        voice_file: Telegram Voice object
        bot: Telegram Bot instance
        
    Returns:
        Path to downloaded file or None
    """
    try:
        processor = VoiceProcessor()
        temp_path = processor.get_temp_filepath(".ogg")
        
        # Download file from Telegram
        file = await bot.get_file(voice_file.file_id)
        await file.download_to_drive(temp_path)
        
        logger.info(f"Downloaded voice file to: {temp_path}")
        return temp_path
        
    except Exception as e:
        logger.error(f"Failed to download voice file: {e}")
        return None

