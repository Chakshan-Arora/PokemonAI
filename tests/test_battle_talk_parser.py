# """
# Unit tests for the deterministic Battle Talk intent parser (BT2.2):
# - Supported intents: PRAISE, ENCOURAGE, WARNING, GENERAL
# - Text normalization: whitespace, capitalization, and punctuation handling
# - Empty, whitespace-only, and invalid input type handling
# - Ambiguous phrases and rule precedence
# - Explicit tactical manoeuvre requests (dodge, evade, jump, block) detected as tactical
# """
# import unittest

# from src.models.battle import (
#     BattleTalkCommand,
#     BattleTalkIntent,
#     TalkCategory,
# )
# from src.ai.battle_talk_parser import (
#     BattleTalkParser,
#     parse,
#     parse_battle_talk,
# )


# class TestBattleTalkParser(unittest.TestCase):
#     """Test suite verifying deterministic intent parsing and rule precedence."""

    # 1. PRAISE intent
#     def test_01_praise_intent_phrases(self) -> None:
#         """Praise and compliments are classified as BattleTalkIntent.PRAISE."""
#         phrases = [
#             "Good job, Pikachu!",
#             "Great job!",
#             "Well done on that attack!",
#             "Nice work!",
#             "Awesome hit!",
#             "Nice strike!",
#             "Nice move!",
#             "Proud of you!",
#             "I'm so proud of you!",
#             "You were amazing!",
#             "You did great!",
#             "Fantastic!",
#             "Brilliant attack!",
#             "Superb job!",
#             "Excellent!",
#             "Good boy!",
#             "Good girl!",
#             "Thank you!",
#             "Thanks for fighting hard!",
#             "Congrats!",
#             "Congratulations!",
#             "Bravo!",
#             "Kudos!",
#             "Best partner ever!",
#         ]
#         for phrase in phrases:
#             with self.subTest(phrase=phrase):
#                 cmd = parse(phrase)
#                 self.assertEqual(cmd.intent, BattleTalkIntent.PRAISE)
#                 self.assertEqual(cmd.category, TalkCategory.CONVERSATIONAL)
#                 self.assertFalse(cmd.is_tactical)

    # 2. ENCOURAGE intent
#     def test_02_encourage_intent_phrases(self) -> None:
#         """Reassurance, confidence-building, and motivation are classified as ENCOURAGE."""
#         phrases = [
#             "You can do this!",
#             "You can do it!",
#             "You've got this!",
#             "You got this, buddy!",
#             "Hang in there!",
#             "Don't give up!",
#             "Do not give up!",
#             "Never give up!",
#             "Keep going!",
#             "Keep it up!",
#             "Keep fighting!",
#             "Stay strong!",
#             "Believe in yourself!",
#             "Come on!",
#             "Let's go!",
#             "Let's do this!",
#             "We can win!",
#             "We've got this!",
#             "Give it your all!",
#             "Show them what you've got!",
#             "Stay focused!",
#             "Focus up!",
#             "Push through!",
#             "Don't lose hope!",
#         ]
#         for phrase in phrases:
#             with self.subTest(phrase=phrase):
#                 cmd = parse(phrase)
#                 self.assertEqual(cmd.intent, BattleTalkIntent.ENCOURAGE)
#                 self.assertEqual(cmd.category, TalkCategory.CONVERSATIONAL)
#                 self.assertFalse(cmd.is_tactical)

    # 3. WARNING intent
#     def test_03_warning_intent_phrases(self) -> None:
#         """Cautionary and defensive phrases are classified as WARNING."""
#         phrases = [
#             "Watch out!",
#             "Look out, Pikachu!",
#             "Heads up!",
#             "Be careful!",
#             "Stay alert!",
#             "Stay sharp!",
#             "Incoming!",
#             "Danger ahead!",
#             "Behind you!",
#             "On guard!",
#             "Watch your back!",
#             "Keep your guard up!",
#             "Careful, Pikachu!",
#         ]
#         for phrase in phrases:
#             with self.subTest(phrase=phrase):
#                 cmd = parse(phrase)
#                 self.assertEqual(cmd.intent, BattleTalkIntent.WARNING)
#                 self.assertEqual(cmd.category, TalkCategory.CONVERSATIONAL)
#                 self.assertFalse(cmd.is_tactical)

    # 4. GENERAL intent and conversational fallback
#     def test_04_general_intent_and_greetings(self) -> None:
#         """Greetings, small talk, and unmatched conversation resolve to GENERAL."""
#         phrases = [
#             "Hello there!",
#             "Hi, Pikachu!",
#             "Hey buddy!",
#             "Greetings!",
#             "How are you feeling?",
#             "What's up?",
#             "The sky is cloudy today.",
#             "I wonder what wild Pokemon live here.",
#             "This battle is interesting.",
#             "Hmm, let me think.",
#             "Tell me about yourself.",
#         ]
#         for phrase in phrases:
#             with self.subTest(phrase=phrase):
#                 cmd = parse(phrase)
#                 self.assertEqual(cmd.intent, BattleTalkIntent.GENERAL)
#                 self.assertEqual(cmd.category, TalkCategory.CONVERSATIONAL)
#                 self.assertFalse(cmd.is_tactical)

    # 5. Normalization: capitalization, whitespace, and punctuation
#     def test_05_normalization_whitespace_capitalization_punctuation(self) -> None:
#         """Parser normalizes whitespace, capitalization, and punctuation gracefully."""
        # ALL CAPS
#         self.assertEqual(parse("GREAT JOB!!").intent, BattleTalkIntent.PRAISE)
#         self.assertEqual(parse("WATCH OUT!!!").intent, BattleTalkIntent.WARNING)
#         self.assertEqual(parse("YOU CAN DO THIS!").intent, BattleTalkIntent.ENCOURAGE)

        # Surrounding whitespace and tabs
#         self.assertEqual(parse("   \t  good job   \n").intent, BattleTalkIntent.PRAISE)
#         self.assertEqual(parse("   look out  ").intent, BattleTalkIntent.WARNING)

        # Mixed punctuation
#         self.assertEqual(parse("You've got this... right?").intent, BattleTalkIntent.ENCOURAGE)
#         self.assertEqual(parse("Be careful!").intent, BattleTalkIntent.WARNING)

    # 6. Ambiguous phrases and rule precedence
#     def test_06_ambiguous_phrases_and_rule_precedence(self) -> None:
#         """Rule precedence properly categorizes ambiguous phrases."""
        # "Good morning" contains "good", but is a greeting -> GENERAL
#         cmd_morning = parse("Good morning, Pikachu!")
#         self.assertEqual(cmd_morning.intent, BattleTalkIntent.GENERAL)

#         cmd_evening = parse("Good evening buddy!")
#         self.assertEqual(cmd_evening.intent, BattleTalkIntent.GENERAL)

        # "Good" in non-praise descriptive contexts -> GENERAL
#         cmd_weather = parse("The weather is good today.")
#         self.assertEqual(cmd_weather.intent, BattleTalkIntent.GENERAL)

#         cmd_question = parse("I have a good question for you.")
#         self.assertEqual(cmd_question.intent, BattleTalkIntent.GENERAL)

        # Mixed praise and warning: warning takes precedence for tactical caution
#         cmd_mixed = parse("Good job, but watch out!")
#         self.assertEqual(cmd_mixed.intent, BattleTalkIntent.WARNING)

#         cmd_mixed2 = parse("Nice strike, but be careful!")
#         self.assertEqual(cmd_mixed2.intent, BattleTalkIntent.WARNING)

    # 7. Explicit tactical manoeuvres are flagged as tactical
#     def test_07_tactical_requests_flagged_as_tactical(self) -> None:
#         """Physical battle commands like dodge, evade, jump, block are marked TACTICAL."""
#         tactical_inputs = [
#             "Dodge!",
#             "Dodge to the left!",
#             "Quick, dodge right!",
#             "Evade the incoming attack!",
#             "Sidestep quickly!",
#             "Duck down!",
#             "Jump over it!",
#             "Jump away!",
#             "Block it with your arms!",
#             "Parry the strike!",
#         ]
#         for phrase in tactical_inputs:
#             with self.subTest(phrase=phrase):
#                 cmd = parse(phrase)
#                 self.assertEqual(cmd.category, TalkCategory.TACTICAL)
#                 self.assertTrue(cmd.is_tactical)
#                 self.assertIn("tactical", cmd.intent.lower())
#                 self.assertIsNotNone(cmd.metadata)
#                 self.assertIn("detected_tactical_action", cmd.metadata)

    # 8. Empty input and invalid input types handled safely
#     def test_08_empty_and_invalid_input_types(self) -> None:
#         """Empty strings, whitespace, and non-string types return safe fallback commands."""
        # Empty and whitespace
#         cmd_empty = parse("")
#         self.assertEqual(cmd_empty.text, "")
#         self.assertEqual(cmd_empty.intent, BattleTalkIntent.GENERAL)
#         self.assertFalse(cmd_empty.is_tactical)

#         cmd_ws = parse("   \t  \n ")
#         self.assertEqual(cmd_ws.text, "")
#         self.assertEqual(cmd_ws.intent, BattleTalkIntent.GENERAL)

        # Non-string types
#         cmd_none = parse(None)  # type: ignore
#         self.assertEqual(cmd_none.text, "")
#         self.assertEqual(cmd_none.intent, BattleTalkIntent.GENERAL)

#         cmd_int = parse(999)  # type: ignore
#         self.assertEqual(cmd_int.text, "999")
#         self.assertEqual(cmd_int.intent, BattleTalkIntent.GENERAL)

    # 9. Function aliases and class interface consistency
#     def test_09_aliases_and_class_interface(self) -> None:
#         """BattleTalkParser.parse, parse, and parse_battle_talk produce identical results."""
#         text = "Awesome performance!"
#         r1 = BattleTalkParser.parse(text)
#         r2 = parse(text)
#         r3 = parse_battle_talk(text)

#         self.assertEqual(r1.intent, r2.intent)
#         self.assertEqual(r2.intent, r3.intent)
#         self.assertEqual(r1.text, text)


    # 10. Negated tactical commands are treated as conversational
#     def test_10_negated_tactical_commands_not_flagged_as_tactical(self) -> None:
#         """Phrases like 'Don't dodge!' or 'Never evade!' do not trigger tactical status."""
#         negated_phrases = [
#             "Don't dodge!",
#             "Don't dodge, stay put!",
#             "Do not dodge!",
#             "Never evade!",
#             "Don't try to dodge!",
#             "Stop dodging!",
#             "Don't jump away!",
#             "Do not block it!",
#             "Never parry!",
#         ]
#         for phrase in negated_phrases:
#             with self.subTest(phrase=phrase):
#                 cmd = parse(phrase)
#                 self.assertEqual(cmd.category, TalkCategory.CONVERSATIONAL)
#                 self.assertFalse(cmd.is_tactical)
#                 self.assertEqual(cmd.intent, BattleTalkIntent.GENERAL)
#                 self.assertTrue(cmd.metadata.get("negated_tactical"))

        # Crucially, non-tactical negative phrases like "Don't give up!" still resolve to ENCOURAGE
#         enc_phrase = parse("Don't give up, Pikachu!")
#         self.assertEqual(enc_phrase.intent, BattleTalkIntent.ENCOURAGE)
#         self.assertFalse(enc_phrase.is_tactical)

#         never_phrase = parse("Never give up!")
#         self.assertEqual(never_phrase.intent, BattleTalkIntent.ENCOURAGE)


# if __name__ == "__main__":
#     unittest.main()
