"""
Autonomous event scheduler for Pokemon intelligence and world simulation.
Executes event-driven agent reactions on key world transitions:
  - Exploring new regions and landmarks
  - Resting, recovering, and teammate bonding
  - Battle conclusions, goal progressions, and reflections
Avoids continuous polling by triggering only upon concrete game events.
"""
from typing import Any, Optional, Sequence

from src.ai.agent import PokemonAgent
from src.ai.companion_service import CompanionService
from src.ai.decision_provider import DecisionProvider
from src.ai.persistence import AiState
from src.models.player import Player
from src.models.pokemon import Pokemon


class AutonomousWorldScheduler:
    """
    Event-driven scheduler activating Pokemon intelligence on significant world events.
    Keeps computation efficient while making companion and wild Pokemon feel alive.
    """

    @staticmethod
    def on_region_entered(
        player: Player,
        region_id: str,
        ai_state: Optional[AiState] = None,
        provider: Optional[DecisionProvider] = None,
    ) -> list[str]:
        """
        Triggered when the player enters a new or revisited world region.
        Companion observes the terrain, checks goals, and forms impressions.
        """
        if not isinstance(player, Player) or not player.active_pokemon or ai_state is None:
            return []

        active_mon = player.active_pokemon
        agent = CompanionService.get_or_create_companion_agent(active_mon, ai_state, player)

        clean_region = region_id.replace("_", " ").title()
        events: list[str] = []

        # Check immediate and long-term goals relating to exploration
        for goal in agent.goals.immediate_goals:
            if goal.get("status") == "active" and region_id in goal.get("description", "").lower():
                goal["status"] = "completed"
                events.append(f"{active_mon.display_name} accomplished its goal: '{goal['description']}'!")
                agent.record_experience(
                    event_type="goal_achieved",
                    summary=f"Reached {clean_region}, fulfilling personal exploration goal",
                    emotional_impact=0.4,
                    involved_entities=[player.unique_id],
                )

        # Temperament-flavored regional reaction
        temp = agent.identity.temperament
        if temp == "curious":
            reflection = f"{active_mon.display_name} sniffs the air in {clean_region}, looking around with bright curiosity."
        elif temp == "cautious":
            reflection = f"{active_mon.display_name} stays close to your heels in {clean_region}, remaining alert."
        elif temp == "bold":
            reflection = f"{active_mon.display_name} steps forward confidently in {clean_region}, ready for any challenge."
        else:
            reflection = f"{active_mon.display_name} looks around {clean_region}, taking in the surroundings."

        events.append(reflection)
        return events

    @staticmethod
    def on_landmark_discovered(
        player: Player,
        landmark_id: str,
        ai_state: Optional[AiState] = None,
    ) -> list[str]:
        """
        Triggered when a landmark is discovered by the player.
        """
        if not isinstance(player, Player) or not player.active_pokemon or ai_state is None:
            return []

        active_mon = player.active_pokemon
        agent = CompanionService.get_or_create_companion_agent(active_mon, ai_state, player)

        clean_lm = landmark_id.replace("_", " ").title()
        ep = agent.record_experience(
            event_type="landmark_discovered",
            summary=f"Discovered the landmark '{clean_lm}' alongside {player.name}",
            emotional_impact=0.25,
            involved_entities=[player.unique_id],
        )

        rel = agent.get_relationship(player.unique_id, default_name=player.name, default_type="trainer")
        rel.adjust_familiarity(3.0)
        rel.add_memory(ep.episode_id)

        return [f"{active_mon.display_name} looks in awe at the {clean_lm}!"]

    @staticmethod
    def on_rest(
        player: Player,
        hours: float,
        ai_state: Optional[AiState] = None,
        provider: Optional[DecisionProvider] = None,
    ) -> list[str]:
        """
        Triggered when the player rests to advance time.
        Promotes social interaction among team members and emotional rejuvenation.
        """
        if not isinstance(player, Player) or ai_state is None:
            return []

        events: list[str] = []
        team = player.team

        # If team has multiple Pokemon, pair two teammates to interact
        if len(team) >= 2:
            mon1, mon2 = team[0], team[1]
            agent1 = CompanionService.get_or_create_companion_agent(mon1, ai_state, player)
            agent2 = CompanionService.get_or_create_companion_agent(mon2, ai_state, player)

            res = CompanionService.teammate_interaction(agent1, mon1, agent2, mon2, context=f"resting for {hours:.1f} hours")
            events.append(f"While resting: {res.summary}")

        # Active companion reflection
        if player.active_pokemon:
            active_agent = CompanionService.get_or_create_companion_agent(player.active_pokemon, ai_state, player)
            rel = active_agent.get_relationship(player.unique_id, default_name=player.name, default_type="trainer")
            rel.adjust_familiarity(1.5)
            events.append(f"{player.active_pokemon.display_name} feels well-rested and refreshed.")

        return events

    @staticmethod
    def on_battle_concluded(
        player: Player,
        battle: Any,
        ai_state: Optional[AiState] = None,
        outcome: str = "victory",
    ) -> list[str]:
        """
        Triggered when a battle concludes.
        Updates companion goals, confidence, and battle memories.
        """
        if not isinstance(player, Player) or not player.active_pokemon or ai_state is None:
            return []

        active_mon = player.active_pokemon
        agent = CompanionService.get_or_create_companion_agent(active_mon, ai_state, player)
        rel = agent.get_relationship(player.unique_id, default_name=player.name, default_type="trainer")
        events: list[str] = []

        if outcome == "victory":
            ep = agent.record_experience(
                event_type="battle_victory",
                summary=f"Achieved victory in battle under {player.name}'s guidance",
                emotional_impact=0.35,
                involved_entities=[player.unique_id],
            )
            rel.adjust_trust(2.0)
            rel.adjust_respect(3.0)
            rel.add_memory(ep.episode_id)
            events.append(f"{active_mon.display_name} rejoices in victory, proud of your teamwork!")

            # Check goal: battle victory
            for goal in agent.goals.immediate_goals:
                if goal.get("status") == "active" and "win" in goal.get("description", "").lower():
                    goal["status"] = "completed"
                    events.append(f"{active_mon.display_name} completed goal: '{goal['description']}'!")

        elif outcome == "defeat":
            ep = agent.record_experience(
                event_type="battle_defeat",
                summary=f"Endured defeat in battle with {player.name}",
                emotional_impact=-0.25,
                involved_entities=[player.unique_id],
            )
            rel.add_memory(ep.episode_id)
            events.append(f"{active_mon.display_name} vows silently to train harder and overcome defeat.")

        return events
