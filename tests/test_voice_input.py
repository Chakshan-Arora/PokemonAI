# --- VOICE INPUT TESTS (BT3.1) - CURRENTLY COMMENTED OUT ---
# """
# Unit tests for Syntax Error 26 BT3.1: AssemblyAI Voice Input and CLI Integration.
#
# Verifies:
# - VoiceInputService and adapter error handling
# - Successful transcription
# - Missing API key detection
# - Empty transcript handling
# - Transcription / API failure handling
# - Microphone / recording failure handling
# - CLI battle talk integration:
#   - Transcript review and confirmation
#   - Transcript cancellation (no command execution)
#   - Execution at most once (no duplicate execution)
#   - Routing through existing BattleManager.talk() pipeline
#   - Typed battle talk remains fully functional
# - All tests are fully mocked (zero microphones, zero paid API keys, zero network).
# """
# import os
# import unittest
# from unittest.mock import MagicMock, patch
#
# from src.models.pokemon import Pokemon
# from src.models.player import Player
# from src.models.personality import Personality
# from src.models.battle_state import BattleState
# from src.models.battle import Battle, BattleActionType
# from src.data.species import PIKACHU, CHARMANDER
# from src.data.attacks import THUNDER_SHOCK, QUICK_ATTACK, EMBER, SCRATCH
#
# from src.ai.voice_input import (
#     VoiceInputService,
#     VoiceInputResult,
#     VoiceInputErrorType,
#     VoiceInputDependencyError,
#     VoiceInputMicrophoneError,
#     VoiceInputTranscriptionError,
#     VoiceInputEmptyAudioError,
#     DefaultAudioRecorder,
#     DefaultAssemblyAITranscriber,
# )
# from game import AdventureGame
#
#
# class DummyMockRecorder:
#     """Mock audio recorder returning controlled WAV bytes or raising exceptions."""
#     def __init__(self, audio_data: bytes = b"RIFFmockwavdata", should_raise: Exception = None):
#         self.audio_data = audio_data
#         self.should_raise = should_raise
#         self.record_called_count = 0
#
#     def record(self, duration_seconds: float = 5.0, sample_rate: int = 16000) -> bytes:
#         self.record_called_count += 1
#         if self.should_raise:
#             raise self.should_raise
#         return self.audio_data
#
#
# class DummyMockTranscriber:
#     """Mock AssemblyAI transcriber returning controlled text or raising exceptions."""
#     def __init__(self, transcript_text: str = "Pikachu, dodge that attack!", should_raise: Exception = None):
#         self.transcript_text = transcript_text
#         self.should_raise = should_raise
#         self.transcribe_called_count = 0
#         self.last_api_key = None
#
#     def transcribe(self, audio_data: bytes, api_key: str) -> str:
#         self.transcribe_called_count += 1
#         self.last_api_key = api_key
#         if self.should_raise:
#             raise self.should_raise
#         return self.transcript_text
#
#
# class TestVoiceInputAdapter(unittest.TestCase):
#     """Tests for VoiceInputService and standalone adapter components."""
#
#     def test_01_successful_transcription(self) -> None:
#         """Successful recording and transcription returns VoiceInputResult.ok."""
#         recorder = DummyMockRecorder(audio_data=b"valid_wav_bytes")
#         transcriber = DummyMockTranscriber(transcript_text="Dodge that attack!")
#         service = VoiceInputService(api_key="test_key_123", recorder=recorder, transcriber=transcriber)
#
#         res = service.record_and_transcribe(duration_seconds=3.0)
#
#         self.assertTrue(res.success)
#         self.assertEqual(res.text, "Dodge that attack!")
#         self.assertIsNone(res.error_type)
#         self.assertEqual(recorder.record_called_count, 1)
#         self.assertEqual(transcriber.transcribe_called_count, 1)
#         self.assertEqual(transcriber.last_api_key, "test_key_123")
#
#     def test_02_missing_api_key(self) -> None:
#         """Service cleanly reports missing API key without raising unhandled exceptions."""
#         with patch.dict(os.environ, {}, clear=True):
#             if "ASSEMBLYAI_API_KEY" in os.environ:
#                 del os.environ["ASSEMBLYAI_API_KEY"]
#
#             recorder = DummyMockRecorder()
#             transcriber = DummyMockTranscriber()
#             service = VoiceInputService(api_key=None, recorder=recorder, transcriber=transcriber)
#
#             avail, err_type, err_msg = service.check_availability()
#             self.assertFalse(avail)
#             self.assertEqual(err_type, VoiceInputErrorType.MISSING_API_KEY)
#             self.assertIn("ASSEMBLYAI_API_KEY", err_msg)
#
#             res = service.record_and_transcribe()
#             self.assertFalse(res.success)
#             self.assertEqual(res.error_type, VoiceInputErrorType.MISSING_API_KEY)
#             # Recorder and transcriber must not have been invoked
#             self.assertEqual(recorder.record_called_count, 0)
#             self.assertEqual(transcriber.transcribe_called_count, 0)
#
#     def test_03_empty_transcript_detected(self) -> None:
#         """When speech recognition detects no words, NO_SPEECH_DETECTED is reported."""
#         recorder = DummyMockRecorder(audio_data=b"silence_bytes")
#         transcriber = DummyMockTranscriber(transcript_text="   ")
#         service = VoiceInputService(api_key="mock_key", recorder=recorder, transcriber=transcriber)
#
#         res = service.record_and_transcribe()
#
#         self.assertFalse(res.success)
#         self.assertEqual(res.error_type, VoiceInputErrorType.NO_SPEECH_DETECTED)
#         self.assertIn("No speech was detected", res.error_message)
#
#     def test_04_transcription_api_failure(self) -> None:
#         """When AssemblyAI API fails or times out, TRANSCRIPTION_FAILED is reported cleanly."""
#         recorder = DummyMockRecorder(audio_data=b"good_audio")
#         transcriber = DummyMockTranscriber(
#             should_raise=VoiceInputTranscriptionError("Connection timed out to AssemblyAI")
#         )
#         service = VoiceInputService(api_key="mock_key", recorder=recorder, transcriber=transcriber)
#
#         res = service.record_and_transcribe()
#
#         self.assertFalse(res.success)
#         self.assertEqual(res.error_type, VoiceInputErrorType.TRANSCRIPTION_FAILED)
#         self.assertIn("Connection timed out", res.error_message)
#
#     def test_05_recording_microphone_failure(self) -> None:
#         """When microphone capture fails, MICROPHONE_ERROR is reported cleanly."""
#         recorder = DummyMockRecorder(
#             should_raise=VoiceInputMicrophoneError("Permission denied: cannot access microphone")
#         )
#         transcriber = DummyMockTranscriber()
#         service = VoiceInputService(api_key="mock_key", recorder=recorder, transcriber=transcriber)
#
#         res = service.record_and_transcribe()
#
#         self.assertFalse(res.success)
#         self.assertEqual(res.error_type, VoiceInputErrorType.MICROPHONE_ERROR)
#         self.assertIn("Permission denied", res.error_message)
#         # Transcriber should not be called if recording failed
#         self.assertEqual(transcriber.transcribe_called_count, 0)
#
#     def test_06_empty_recording_bytes(self) -> None:
#         """When microphone produces empty bytes, EMPTY_RECORDING is reported."""
#         recorder = DummyMockRecorder(audio_data=b"")
#         transcriber = DummyMockTranscriber()
#         service = VoiceInputService(api_key="mock_key", recorder=recorder, transcriber=transcriber)
#
#         res = service.record_and_transcribe()
#
#         self.assertFalse(res.success)
#         self.assertEqual(res.error_type, VoiceInputErrorType.EMPTY_RECORDING)
#         self.assertEqual(transcriber.transcribe_called_count, 0)
#
#     def test_07_default_recorder_missing_dependency(self) -> None:
#         """DefaultAudioRecorder raises VoiceInputDependencyError if sounddevice is missing."""
#         rec = DefaultAudioRecorder()
#         with patch.dict("sys.modules", {"sounddevice": None}):
#             with self.assertRaises(VoiceInputDependencyError):
#                 rec.record(duration_seconds=1.0)
#
#     def test_08_default_transcriber_missing_dependency(self) -> None:
#         """DefaultAssemblyAITranscriber raises VoiceInputDependencyError if assemblyai is missing."""
#         trans = DefaultAssemblyAITranscriber()
#         with patch.dict("sys.modules", {"assemblyai": None}):
#             with self.assertRaises(VoiceInputDependencyError):
#                 trans.transcribe(audio_data=b"test", api_key="test_key")
#
#
# class TestVoiceInputCLIIntegration(unittest.TestCase):
#     """Tests verifying CLI battle talk interaction in game.py."""
#
#     def setUp(self) -> None:
#         self.personality = Personality(
#             aggression=50, curiosity=50, fear=50, sociability=50, loyalty=50, confidence=50
#         )
#         self.pika = Pokemon(
#             species=PIKACHU,
#             personality=self.personality,
#             level=5,
#             attacks=[THUNDER_SHOCK, QUICK_ATTACK],
#         )
#         self.charm = Pokemon(
#             species=CHARMANDER,
#             personality=self.personality,
#             level=5,
#             attacks=[EMBER, SCRATCH],
#         )
#         self.player = Player(name="Red")
#         self.player.add_pokemon(self.pika)
#         self.player.add_to_team(self.pika)
#         self.player.set_active_pokemon(self.pika)
#
#     def _create_game_app(self, inputs: list[str], voice_service: VoiceInputService) -> tuple[AdventureGame, list[str]]:
#         outputs: list[str] = []
#         input_queue = list(inputs)
#
#         def mock_input(prompt: str = "") -> str:
#             if prompt:
#                 outputs.append(prompt)
#             if input_queue:
#                 val = input_queue.pop(0)
#                 outputs.append(f">> {val}")
#                 return val
#             return "4"  # Default to flee
#
#         def mock_output(*args: object) -> None:
#             outputs.append(" ".join(str(a) for a in args))
#
#         app = AdventureGame(
#             input_fn=mock_input,
#             output_fn=mock_output,
#             seed=42,
#             voice_service=voice_service,
#         )
#         app.player = self.player
#         return app, outputs
#
#     def test_09_voice_battle_talk_confirmed_and_routed_to_dodge(self) -> None:
#         """
#         Player selects [6] Battle Talk -> [1] Voice Input -> presses Enter ->
#         AssemblyAI returns 'Dodge that attack!' -> player confirms 'y' ->
#         BattleManager routes to DODGE action and executes turn.
#         """
#         transcriber = DummyMockTranscriber(transcript_text="Pikachu, dodge that attack!")
#         recorder = DummyMockRecorder(audio_data=b"mock_voice_wav")
#         voice_service = VoiceInputService(api_key="mock_key", recorder=recorder, transcriber=transcriber)
#
#         # Inputs:
#         # 1. "6" -> Battle Talk menu
#         # 2. "1" -> Voice Input option
#         # 3. ""  -> Press Enter to record
#         # 4. "y" -> Confirm transcript
#         # 5. "4" -> Flee to end battle
#         inputs = ["6", "1", "", "y", "4"]
#         app, outputs = self._create_game_app(inputs, voice_service)
#
#         battle = app.battle_manager.start_battle(self.player, self.charm, seed=42)
#         initial_turn = battle.current_turn
#
#         app._battle_loop(battle)
#
#         # 1. Recording and transcription were invoked exactly once
#         self.assertEqual(recorder.record_called_count, 1)
#         self.assertEqual(transcriber.transcribe_called_count, 1)
#
#         # 2. Transcript was displayed to user before confirmation
#         transcript_shown = any("Pikachu, dodge that attack!" in out for out in outputs)
#         self.assertTrue(transcript_shown)
#
#         # 3. Dodge was executed (which advances turn)
#         self.assertGreater(battle.current_turn, initial_turn)
#
#         # 4. Turn history recorded the DODGE action outcome
#         self.assertTrue(len(battle.turn_history) >= 1)
#
#     def test_10_voice_battle_talk_cancelled_before_recording(self) -> None:
#         """Player aborts voice input at recording prompt: no recording and no battle action."""
#         transcriber = DummyMockTranscriber()
#         recorder = DummyMockRecorder()
#         voice_service = VoiceInputService(api_key="mock_key", recorder=recorder, transcriber=transcriber)
#
#         # Inputs: "6" (Battle Talk), "1" (Voice), "cancel" (Abort), "4" (Flee)
#         inputs = ["6", "1", "cancel", "4"]
#         app, outputs = self._create_game_app(inputs, voice_service)
#
#         battle = app.battle_manager.start_battle(self.player, self.charm, seed=42)
#         initial_turn = battle.current_turn
#
#         app._battle_loop(battle)
#
#         self.assertEqual(recorder.record_called_count, 0)
#         self.assertEqual(transcriber.transcribe_called_count, 0)
#         # Turn did not advance from cancelled talk (flee terminates battle)
#         self.assertTrue(any("Voice input cancelled" in out for out in outputs))
#
#     def test_11_voice_battle_talk_cancelled_at_confirmation(self) -> None:
#         """
#         Player records audio and receives transcript, but rejects confirmation with 'n':
#         no battle action is dispatched, turn is NOT consumed.
#         """
#         transcriber = DummyMockTranscriber(transcript_text="Hang in there!")
#         recorder = DummyMockRecorder()
#         voice_service = VoiceInputService(api_key="mock_key", recorder=recorder, transcriber=transcriber)
#
#         # Inputs: "6" (Talk), "1" (Voice), "" (Record), "n" (Reject confirmation), "4" (Flee)
#         inputs = ["6", "1", "", "n", "4"]
#         app, outputs = self._create_game_app(inputs, voice_service)
#
#         battle = app.battle_manager.start_battle(self.player, self.charm, seed=42)
#
#         # Hook to verify battle.take_action is NOT called with TALK or DODGE
#         action_calls = []
#         original_take_action = battle.take_action
#
#         def spy_take_action(action):
#             action_calls.append(action.action_type)
#             return original_take_action(action)
#
#         battle.take_action = spy_take_action
#
#         app._battle_loop(battle)
#
#         self.assertEqual(recorder.record_called_count, 1)
#         self.assertEqual(transcriber.transcribe_called_count, 1)
#         self.assertTrue(any("Voice command cancelled" in out for out in outputs))
#
#         # Only FLEE was executed; TALK and DODGE were never executed!
#         self.assertNotIn(BattleActionType.TALK, action_calls)
#         self.assertNotIn(BattleActionType.DODGE, action_calls)
#
#     def test_12_no_duplicate_execution(self) -> None:
#         """A confirmed voice transcript executes at most once and does not repeat."""
#         transcriber = DummyMockTranscriber(transcript_text="You can do it!")
#         recorder = DummyMockRecorder()
#         voice_service = VoiceInputService(api_key="mock_key", recorder=recorder, transcriber=transcriber)
#
#         # Inputs: Talk -> Voice -> Record -> Confirm -> then Flee
#         inputs = ["6", "1", "", "y", "4"]
#         app, outputs = self._create_game_app(inputs, voice_service)
#
#         battle = app.battle_manager.start_battle(self.player, self.charm, seed=42)
#
#         talk_execution_count = 0
#         original_talk = app.battle_manager.talk
#
#         def spy_talk(player, command):
#             nonlocal talk_execution_count
#             talk_execution_count += 1
#             return original_talk(player, command)
#
#         app.battle_manager.talk = spy_talk
#
#         app._battle_loop(battle)
#
#         # Talk pipeline executed exactly once for the confirmed transcript
#         self.assertEqual(talk_execution_count, 1)
#
#     def test_13_voice_unavailable_graceful_message(self) -> None:
#         """When voice service is unavailable (missing API key), player is advised to type."""
#         recorder = DummyMockRecorder()
#         transcriber = DummyMockTranscriber()
#         # Voice service without API key
#         voice_service = VoiceInputService(api_key=None, recorder=recorder, transcriber=transcriber)
#
#         with patch.dict(os.environ, {}, clear=True):
#             if "ASSEMBLYAI_API_KEY" in os.environ:
#                 del os.environ["ASSEMBLYAI_API_KEY"]
#
#             # Inputs: Talk -> Voice -> Flee
#             inputs = ["6", "1", "4"]
#             app, outputs = self._create_game_app(inputs, voice_service)
#
#             battle = app.battle_manager.start_battle(self.player, self.charm, seed=42)
#             app._battle_loop(battle)
#
#             self.assertTrue(any("Voice input unavailable" in out for out in outputs))
#             self.assertTrue(any("type your battle talk command instead" in out for out in outputs))
#             self.assertEqual(recorder.record_called_count, 0)
#
#     def test_14_typed_battle_talk_pipeline_unchanged(self) -> None:
#         """
#         Option [2] in Battle Talk allows standard keyboard typing.
#         Dispatches through the exact same BattleManager.talk() pipeline.
#         """
#         voice_service = VoiceInputService(api_key="mock_key")
#
#         # Inputs: "6" (Talk), "2" (Type), "Great job, Pikachu!", "4" (Flee)
#         inputs = ["6", "2", "Great job, Pikachu!", "4"]
#         app, outputs = self._create_game_app(inputs, voice_service)
#
#         battle = app.battle_manager.start_battle(self.player, self.charm, seed=42)
#         app._battle_loop(battle)
#
#         # Companion response should appear in battle events
#         companion_talk_logged = any("Pikachu" in out and "Player:" in out for out in outputs) or \
#                                 any("Player: \"Great job, Pikachu!\"" in event for event in battle.events)
#         self.assertTrue(companion_talk_logged)
#
#     def test_15_typed_battle_talk_cancellation(self) -> None:
#         """Cancelling typed battle talk takes no battle action."""
#         voice_service = VoiceInputService(api_key="mock_key")
#
#         # Inputs: "6" (Talk), "2" (Type), "cancel", "4" (Flee)
#         inputs = ["6", "2", "cancel", "4"]
#         app, outputs = self._create_game_app(inputs, voice_service)
#
#         battle = app.battle_manager.start_battle(self.player, self.charm, seed=42)
#         initial_turn = battle.current_turn
#
#         app._battle_loop(battle)
#
#         self.assertTrue(any("Battle talk cancelled" in out for out in outputs))
#
#
# if __name__ == "__main__":
#     unittest.main()
