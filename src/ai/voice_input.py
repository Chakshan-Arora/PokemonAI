# --- VOICE INPUT VIA ASSEMBLYAI (BT3.1) - CURRENTLY COMMENTED OUT ---
# """
# Voice Input Adapter for Syntax Error 26 (BT3.1).
# Integrates speech-to-text transcription via AssemblyAI for battle talk commands.
#
# Architecture:
# - Audio capture via microphone (push-to-talk / fixed-duration recording).
# - Conversion to WAV format using Python's standard library.
# - Transcription via the official AssemblyAI Python SDK (aai.Transcriber).
# - Completely decoupled from game logic: outputs raw transcript text or structured errors.
# - Graceful degradation when audio dependencies or API keys are missing.
# - Temporary files are immediately cleaned up and never retained on disk.
# - Zero credential logging or exposure.
# """
# from __future__ import annotations
#
# import io
# import os
# import tempfile
# import wave
# from dataclasses import dataclass
# from enum import Enum
# from typing import Any, Optional, Protocol, runtime_checkable
#
#
# class VoiceInputErrorType(str, Enum):
#     """Categories of voice input and transcription errors."""
#     MISSING_DEPENDENCY = "MISSING_DEPENDENCY"
#     MISSING_API_KEY = "MISSING_API_KEY"
#     MICROPHONE_ERROR = "MICROPHONE_ERROR"
#     EMPTY_RECORDING = "EMPTY_RECORDING"
#     TRANSCRIPTION_FAILED = "TRANSCRIPTION_FAILED"
#     NO_SPEECH_DETECTED = "NO_SPEECH_DETECTED"
#     CANCELLED = "CANCELLED"
#
#
# @dataclass(frozen=True)
# class VoiceInputResult:
#     """
#     Structured outcome of a voice recording and transcription operation.
#     """
#     success: bool
#     text: Optional[str] = None
#     error_type: Optional[VoiceInputErrorType] = None
#     error_message: Optional[str] = None
#     raw_response: Optional[Any] = None
#
#     @classmethod
#     def ok(cls, text: str, raw_response: Optional[Any] = None) -> VoiceInputResult:
#         return cls(success=True, text=text, raw_response=raw_response)
#
#     @classmethod
#     def fail(cls, error_type: VoiceInputErrorType, message: str) -> VoiceInputResult:
#         return cls(success=False, error_type=error_type, error_message=message)
#
#
# class VoiceInputException(Exception):
#     """Base exception for voice input errors."""
#     def __init__(self, error_type: VoiceInputErrorType, message: str) -> None:
#         super().__init__(message)
#         self.error_type = error_type
#         self.message = message
#
#
# class VoiceInputDependencyError(VoiceInputException):
#     def __init__(self, message: str) -> None:
#         super().__init__(VoiceInputErrorType.MISSING_DEPENDENCY, message)
#
#
# class VoiceInputMicrophoneError(VoiceInputException):
#     def __init__(self, message: str) -> None:
#         super().__init__(VoiceInputErrorType.MICROPHONE_ERROR, message)
#
#
# class VoiceInputEmptyAudioError(VoiceInputException):
#     def __init__(self, message: str) -> None:
#         super().__init__(VoiceInputErrorType.EMPTY_RECORDING, message)
#
#
# class VoiceInputTranscriptionError(VoiceInputException):
#     def __init__(self, message: str) -> None:
#         super().__init__(VoiceInputErrorType.TRANSCRIPTION_FAILED, message)
#
#
# class VoiceInputEmptyTranscriptError(VoiceInputException):
#     def __init__(self, message: str) -> None:
#         super().__init__(VoiceInputErrorType.NO_SPEECH_DETECTED, message)
#
#
# @runtime_checkable
# class AudioRecorderProtocol(Protocol):
#     """Protocol for recording microphone audio into WAV bytes."""
#     def record(self, duration_seconds: float = 5.0, sample_rate: int = 16000) -> bytes:
#         ...
#
#
# @runtime_checkable
# class TranscriberProtocol(Protocol):
#     """Protocol for transcribing WAV audio bytes into text."""
#     def transcribe(self, audio_data: bytes, api_key: str) -> str:
#         ...
#
#
# class DefaultAudioRecorder:
#     """
#     Default microphone recorder using sounddevice and Python's wave module.
#     Dynamically imports sounddevice to allow startup without audio dependencies.
#     """
#     def record(self, duration_seconds: float = 5.0, sample_rate: int = 16000) -> bytes:
#         try:
#             import sounddevice as sd
#             import numpy as np
#         except ImportError as err:
#             raise VoiceInputDependencyError(
#                 "The 'sounddevice' library is required for audio recording. "
#                 "Install it with: pip install sounddevice"
#             ) from err
#
#         if duration_seconds <= 0:
#             raise VoiceInputMicrophoneError("Recording duration must be greater than zero.")
#
#         try:
#             # Check for available input devices
#             devices = sd.query_devices()
#             default_input = sd.default.device[0] if sd.default.device else None
#             if not devices or default_input is None or default_input < 0:
#                 raise VoiceInputMicrophoneError("No microphone input device found.")
#
#             # Record 16-bit mono audio
#             total_frames = int(duration_seconds * sample_rate)
#             recording = sd.rec(
#                 total_frames,
#                 samplerate=sample_rate,
#                 channels=1,
#                 dtype="int16",
#             )
#             sd.wait()
#         except VoiceInputMicrophoneError:
#             raise
#         except Exception as exc:
#             raise VoiceInputMicrophoneError(f"Microphone recording failed: {exc}") from exc
#         finally:
#             try:
#                 sd.stop()
#             except Exception:
#                 pass
#
#         if recording is None or len(recording) == 0:
#             raise VoiceInputEmptyAudioError("Recording produced no audio data.")
#
#         # Check for near-total silence (all zero amplitudes)
#         if int(np.max(np.abs(recording))) == 0:
#             raise VoiceInputEmptyAudioError("Recording was completely silent / empty.")
#
#         # Convert int16 NumPy array into WAV bytes
#         buf = io.BytesIO()
#         try:
#             with wave.open(buf, "wb") as wf:
#                 wf.setnchannels(1)
#                 wf.setsampwidth(2)  # 16-bit = 2 bytes
#                 wf.setframerate(sample_rate)
#                 wf.writeframes(recording.tobytes())
#             return buf.getvalue()
#         except Exception as exc:
#             raise VoiceInputMicrophoneError(f"Failed to encode WAV audio: {exc}") from exc
#
#
# class DefaultAssemblyAITranscriber:
#     """
#     Default transcriber using the official AssemblyAI Python SDK.
#     Dynamically imports assemblyai to allow startup without the dependency.
#     """
#     def transcribe(self, audio_data: bytes, api_key: str) -> str:
#         try:
#             import assemblyai as aai
#         except ImportError as err:
#             raise VoiceInputDependencyError(
#                 "The 'assemblyai' library is required for speech-to-text. "
#                 "Install it with: pip install assemblyai"
#             ) from err
#
#         if not api_key or not api_key.strip():
#             raise VoiceInputException(
#                 VoiceInputErrorType.MISSING_API_KEY,
#                 "AssemblyAI API key is missing or empty."
#             )
#
#         if not audio_data or len(audio_data) == 0:
#             raise VoiceInputEmptyAudioError("Audio data to transcribe is empty.")
#
#         temp_path: Optional[str] = None
#         try:
#             with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
#                 tmp.write(audio_data)
#                 temp_path = tmp.name
#
#             aai.settings.api_key = api_key.strip()
#             transcriber = aai.Transcriber()
#             transcript = transcriber.transcribe(temp_path)
#
#             status = getattr(transcript, "status", None)
#             error = getattr(transcript, "error", None)
#
#             if error or str(status).lower() in ("error", "failed"):
#                 err_msg = error or "Unknown AssemblyAI transcription error"
#                 raise VoiceInputTranscriptionError(f"AssemblyAI error: {err_msg}")
#
#             text = getattr(transcript, "text", None)
#             if text is None or not str(text).strip():
#                 raise VoiceInputEmptyTranscriptError("No speech detected in audio recording.")
#
#             return str(text).strip()
#         except (VoiceInputDependencyError, VoiceInputTranscriptionError, VoiceInputEmptyTranscriptError, VoiceInputException):
#             raise
#         except Exception as exc:
#             raise VoiceInputTranscriptionError(f"Transcription request failed: {exc}") from exc
#         finally:
#             if temp_path and os.path.exists(temp_path):
#                 try:
#                     os.remove(temp_path)
#                 except OSError:
#                     pass
#
#
# class VoiceInputService:
#     """
#     High-level service coordinating microphone recording and AssemblyAI transcription.
#     Safe against missing libraries, absent hardware, network failures, and missing keys.
#     """
#     ENV_API_KEY_VAR = "ASSEMBLYAI_API_KEY"
#
#     def __init__(
#         self,
#         api_key: Optional[str] = None,
#         recorder: Optional[AudioRecorderProtocol] = None,
#         transcriber: Optional[TranscriberProtocol] = None,
#     ) -> None:
#         self._explicit_api_key = api_key
#         self._recorder = recorder if recorder is not None else DefaultAudioRecorder()
#         self._transcriber = transcriber if transcriber is not None else DefaultAssemblyAITranscriber()
#
#     @property
#     def api_key(self) -> Optional[str]:
#         """Resolves the AssemblyAI API key from explicit config or environment."""
#         if self._explicit_api_key and self._explicit_api_key.strip():
#             return self._explicit_api_key.strip()
#         env_val = os.environ.get(self.ENV_API_KEY_VAR, "").strip()
#         return env_val if env_val else None
#
#     def check_availability(self) -> tuple[bool, Optional[VoiceInputErrorType], Optional[str]]:
#         """
#         Verifies if voice input can be used in the current environment.
#         Checks API key and library dependencies without recording audio.
#         """
#         # 1. API Key check
#         if not self.api_key:
#             return (
#                 False,
#                 VoiceInputErrorType.MISSING_API_KEY,
#                 f"Environment variable '{self.ENV_API_KEY_VAR}' is not set. "
#                 f"Set it using: $env:{self.ENV_API_KEY_VAR}='your_key' in PowerShell.",
#             )
#
#         # 2. Dependency checks (only if using default recorder/transcriber)
#         if isinstance(self._recorder, DefaultAudioRecorder):
#             try:
#                 import sounddevice  # noqa: F401
#             except ImportError:
#                 return (
#                     False,
#                     VoiceInputErrorType.MISSING_DEPENDENCY,
#                     "Optional dependency 'sounddevice' is not installed. Install with: pip install sounddevice",
#                 )
#
#         if isinstance(self._transcriber, DefaultAssemblyAITranscriber):
#             try:
#                 import assemblyai  # noqa: F401
#             except ImportError:
#                 return (
#                     False,
#                     VoiceInputErrorType.MISSING_DEPENDENCY,
#                     "Optional dependency 'assemblyai' is not installed. Install with: pip install assemblyai",
#                 )
#
#         return (True, None, None)
#
#     def record_and_transcribe(self, duration_seconds: float = 5.0) -> VoiceInputResult:
#         """
#         Executes the full recording and speech-to-text pipeline.
#         Catches all internal exceptions and returns a structured VoiceInputResult.
#         """
#         # Pre-flight check
#         is_ok, err_type, err_msg = self.check_availability()
#         if not is_ok and err_type is not None and err_msg is not None:
#             return VoiceInputResult.fail(err_type, err_msg)
#
#         api_key = self.api_key
#         if not api_key:
#             return VoiceInputResult.fail(
#                 VoiceInputErrorType.MISSING_API_KEY,
#                 f"Environment variable '{self.ENV_API_KEY_VAR}' is not set.",
#             )
#
#         # Step 1: Record audio
#         try:
#             audio_bytes = self._recorder.record(duration_seconds=duration_seconds)
#         except VoiceInputException as exc:
#             return VoiceInputResult.fail(exc.error_type, exc.message)
#         except Exception as exc:
#             return VoiceInputResult.fail(
#                 VoiceInputErrorType.MICROPHONE_ERROR,
#                 f"Unexpected recording error: {exc}",
#             )
#
#         if not audio_bytes:
#             return VoiceInputResult.fail(
#                 VoiceInputErrorType.EMPTY_RECORDING,
#                 "Microphone produced an empty audio recording.",
#             )
#
#         # Step 2: Transcribe via AssemblyAI
#         try:
#             transcript_text = self._transcriber.transcribe(audio_bytes, api_key=api_key)
#         except VoiceInputException as exc:
#             return VoiceInputResult.fail(exc.error_type, exc.message)
#         except Exception as exc:
#             return VoiceInputResult.fail(
#                 VoiceInputErrorType.TRANSCRIPTION_FAILED,
#                 f"Transcription request failed: {exc}",
#             )
#
#         cleaned = transcript_text.strip()
#         if not cleaned:
#             return VoiceInputResult.fail(
#                 VoiceInputErrorType.NO_SPEECH_DETECTED,
#                 "No speech was detected in the audio.",
#             )
#
#         return VoiceInputResult.ok(cleaned)
