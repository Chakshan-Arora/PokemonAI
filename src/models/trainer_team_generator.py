"""
Trainer team generator for dynamic, progression-aware trainer battles.
Generates balanced, level-appropriate, archetype-coherent Pokemon teams
tailored to player progression and regional habitat compositions.
"""
from __future__ import annotations
import math
import random
from typing import Optional, Sequence, Union

from src.models.pokemon import Pokemon, MAX_KNOWN_MOVES
from src.models.player import Player
from src.models.species import PokemonSpecies
from src.models.pokemon_type import PokemonType
from src.models.attack import Attack
from src.models.personality import Personality
from src.models.personality_generator import generate_wild_personality
from src.models.trainer import Trainer, DifficultyProfile, TrainerArchetype
from src.data.move_learning import get_moves_in_level_range


# Archetype to primary/secondary Pokemon type affinities
ARCHETYPE_TYPE_AFFINITIES: dict[TrainerArchetype, tuple[PokemonType, ...]] = {
    TrainerArchetype.YOUNGSTER: (PokemonType.NORMAL, PokemonType.BUG, PokemonType.GRASS),
    TrainerArchetype.BUG_CATCHER: (PokemonType.BUG,),
    TrainerArchetype.LASS: (PokemonType.NORMAL, PokemonType.GRASS, PokemonType.ELECTRIC),
    TrainerArchetype.HIKER: (PokemonType.ROCK, PokemonType.GROUND, PokemonType.FIGHTING),
    TrainerArchetype.BIRD_KEEPER: (PokemonType.FLYING,),
    TrainerArchetype.PSYCHIC: (PokemonType.PSYCHIC, PokemonType.GHOST),
    TrainerArchetype.SAILOR: (PokemonType.WATER, PokemonType.FIGHTING),
    TrainerArchetype.ACE_TRAINER: (),  # Competitive generalist, embraces all types
    TrainerArchetype.GYM_LEADER: (),   # Thematic or region-specialized
}

# Default reward item drops by difficulty tier
DEFAULT_DIFFICULTY_REWARDS: dict[DifficultyProfile, dict[str, int]] = {
    DifficultyProfile.EASY: {"potion": 1, "poke_ball": 2},
    DifficultyProfile.NORMAL: {"super_potion": 1, "poke_ball": 3},
    DifficultyProfile.HARD: {"hyper_potion": 1, "ultra_ball": 2},
    DifficultyProfile.BOSS: {"max_potion": 1, "full_restore": 1, "nugget": 1},
}


class TrainerTeamGenerator:
    """
    Factory and utility service for generating trainer teams and instances.
    Ensures teams are progression-scaled, mechanically valid, and archetype-faithful.
    """

    @staticmethod
    def calculate_party_strength(player: Optional[Player]) -> int:
        """
        Calculates a composite party strength metric for the player.
        Blends maximum team level, average team level, and active Pokemon level
        to prevent single-lead cheesing or level manipulation.
        """
        if player is None or not getattr(player, "team", None):
            return 5

        valid_members = [p for p in player.team if p is not None and hasattr(p, "level")]
        if not valid_members:
            return 5

        levels = [m.level for m in valid_members]
        max_lvl = max(levels)
        mean_lvl = sum(levels) / len(levels)

        active = getattr(player, "active_pokemon", None)
        active_lvl = active.level if active is not None and active in valid_members else levels[0]

        composite = 0.4 * max_lvl + 0.4 * mean_lvl + 0.2 * active_lvl
        strength = int(round(composite))
        return max(1, min(100, strength))

    @staticmethod
    def get_target_level_range(
        difficulty: Union[DifficultyProfile, str],
        party_strength: int,
    ) -> tuple[int, int, int]:
        """
        Calculates (min_level, target_level, max_level) bounds based on difficulty
        and player party strength.
        """
        if isinstance(difficulty, str):
            diff = DifficultyProfile[difficulty.upper()]
        else:
            diff = difficulty

        strength = max(1, min(100, party_strength))

        if diff == DifficultyProfile.EASY:
            target = max(1, strength - 1)
            min_lvl = max(1, target - 1)
            max_lvl = max(1, target)
        elif diff == DifficultyProfile.NORMAL:
            target = strength
            min_lvl = max(1, target - 1)
            max_lvl = min(100, target + 1)
        elif diff == DifficultyProfile.HARD:
            target = min(100, strength + 1)
            min_lvl = max(1, target)
            max_lvl = min(100, target + 2)
        elif diff == DifficultyProfile.BOSS:
            target = min(100, strength + 2)
            min_lvl = max(1, target)
            max_lvl = min(100, target + 3)
        else:
            target = strength
            min_lvl = max(1, target - 1)
            max_lvl = min(100, target + 1)

        return min_lvl, target, max_lvl

    @staticmethod
    def get_team_size(
        difficulty: Union[DifficultyProfile, str],
        rng: Optional[random.Random] = None,
    ) -> int:
        """
        Determines the team size based on trainer difficulty tier.
        EASY: 1-2, NORMAL: 2-3, HARD: 3-5, BOSS: 3-6.
        """
        if isinstance(difficulty, str):
            diff = DifficultyProfile[difficulty.upper()]
        else:
            diff = difficulty

        r = rng if rng is not None else random.Random()

        if diff == DifficultyProfile.EASY:
            return r.randint(1, 2)
        elif diff == DifficultyProfile.NORMAL:
            return r.randint(2, 3)
        elif diff == DifficultyProfile.HARD:
            return r.randint(3, 5)
        elif diff == DifficultyProfile.BOSS:
            return r.randint(4, 6)
        return 2

    @staticmethod
    def get_eligible_species(
        archetype: Union[TrainerArchetype, str],
        region_id: str,
    ) -> list[PokemonSpecies]:
        """
        Retrieves eligible species for a trainer archetype in a specified region.
        Prioritizes habitat candidates matching the archetype's thematic types,
        supplemented with general habitat species if needed.
        """
        if isinstance(archetype, str):
            arch = TrainerArchetype[archetype.upper()]
        else:
            arch = archetype

        # 1. Fetch habitat candidates for region
        from src.data.habitats import get_habitat_for_region, HABITAT_CATALOG
        from src.data.species import SAMPLE_SPECIES

        habitat = get_habitat_for_region(region_id)
        candidates: list[PokemonSpecies] = []
        if habitat is not None:
            seen_names = set()
            for cand in habitat.candidates:
                if cand.species.name not in seen_names:
                    seen_names.add(cand.species.name)
                    candidates.append(cand.species)

        # Fallback to all catalog candidates if region has none
        if not candidates:
            seen_names = set()
            for hab in HABITAT_CATALOG.values():
                for cand in hab.candidates:
                    if cand.species.name not in seen_names:
                        seen_names.add(cand.species.name)
                        candidates.append(cand.species)

        # Fallback to SAMPLE_SPECIES catalog if still empty
        if not candidates:
            candidates = list(SAMPLE_SPECIES.values())

        # 2. Filter/prioritize by archetype affinities
        affinities = ARCHETYPE_TYPE_AFFINITIES.get(arch, ())
        if not affinities:
            return list(candidates)

        matching: list[PokemonSpecies] = []
        others: list[PokemonSpecies] = []
        for sp in candidates:
            sp_types = (sp.primary_type, sp.secondary_type) if sp.secondary_type else (sp.primary_type,)
            if any(t in affinities for t in sp_types):
                matching.append(sp)
            else:
                others.append(sp)

        # If matching species exist, return matching followed by others
        if matching:
            return matching + others

        return list(candidates)

    @staticmethod
    def generate_moveset(species: PokemonSpecies, level: int) -> list[Attack]:
        """
        Builds a valid, level-appropriate moveset up to MAX_KNOWN_MOVES (4)
        using the species move-learning table and available attacks.
        """
        lvl = max(1, min(100, int(level)))
        learned = get_moves_in_level_range(species, 1, lvl, inclusive_start=True)

        moves: list[Attack] = []
        # Add latest learned moves in reverse order (highest level first)
        for item in reversed(learned):
            if item.attack not in moves:
                moves.append(item.attack)
            if len(moves) >= MAX_KNOWN_MOVES:
                break

        # Reverse back so moves are in natural progression order
        moves.reverse()

        # Supplement if fewer than 2 moves known and available_attacks defined
        if len(moves) < 2 and species.available_attacks:
            for atk in species.available_attacks:
                if atk not in moves:
                    moves.append(atk)
                if len(moves) >= 2 or len(moves) >= MAX_KNOWN_MOVES:
                    break

        # Edge fallback
        if not moves and species.available_attacks:
            moves.append(species.available_attacks[0])

        return moves

    @staticmethod
    def generate_pokemon(
        species: PokemonSpecies,
        level: int,
        rng: Optional[random.Random] = None,
    ) -> Pokemon:
        """
        Creates a new ready-to-battle Pokemon instance for a trainer with
        generated personality, valid moveset, and full health.
        """
        lvl = max(1, min(100, int(level)))
        r = rng if rng is not None else random.Random()
        personality = generate_wild_personality(rng=r)
        moves = TrainerTeamGenerator.generate_moveset(species, lvl)

        mon = Pokemon(
            species=species,
            personality=personality,
            level=lvl,
            attacks=moves,
        )
        mon.heal_full()
        return mon

    @classmethod
    def generate_team(
        cls,
        trainer: Trainer,
        player: Optional[Player] = None,
        region_id: Optional[str] = None,
        rng: Optional[random.Random] = None,
        seed: Optional[int] = None,
        force_regenerate: bool = False,
    ) -> list[Pokemon]:
        """
        Generates and assigns a full team to a trainer if not already populated.
        Idempotent: preserves existing teams unless force_regenerate is True.
        """
        if not isinstance(trainer, Trainer):
            raise TypeError(f"trainer must be a Trainer instance, got {type(trainer).__name__}.")

        # Guard: do not reroll already generated teams
        if trainer.has_team and not force_regenerate:
            return list(trainer.team)

        # Setup RNG
        if rng is not None:
            r = rng
        elif seed is not None:
            r = random.Random(seed)
        else:
            r = random.Random()

        # Calculate progression bounds
        party_strength = cls.calculate_party_strength(player)
        min_lvl, target_lvl, max_lvl = cls.get_target_level_range(trainer.difficulty, party_strength)
        team_size = cls.get_team_size(trainer.difficulty, r)

        # Retrieve candidate pool
        effective_region = region_id or trainer.region_id
        eligible = cls.get_eligible_species(trainer.archetype, effective_region)
        if not eligible:
            from src.data.species import SAMPLE_SPECIES
            eligible = list(SAMPLE_SPECIES.values())

        # Select species ensuring diversity where candidate pool allows
        affinities = ARCHETYPE_TYPE_AFFINITIES.get(trainer.archetype, ())
        matching = [
            s for s in eligible
            if (s.primary_type in affinities or (s.secondary_type and s.secondary_type in affinities))
        ] if affinities else list(eligible)

        selected_species: list[PokemonSpecies] = []
        if matching and len(matching) >= team_size:
            selected_species = r.sample(matching, team_size)
        elif len(eligible) >= team_size:
            # Prioritize matching, then fill from eligible
            chosen = list(matching)
            remaining = [s for s in eligible if s not in chosen]
            needed = team_size - len(chosen)
            if needed > 0:
                chosen.extend(r.sample(remaining, needed))
            selected_species = chosen[:team_size]
        else:
            # Candidate pool smaller than team size: sample with replacement
            pool = matching if matching else eligible
            selected_species = [r.choice(pool) for _ in range(team_size)]

        # Generate Pokemon instances
        generated_team: list[Pokemon] = []
        for idx, species in enumerate(selected_species):
            # Scale level within bounds
            if idx == len(selected_species) - 1:
                # The trainer's Ace: at least target_lvl, up to max_lvl
                mon_lvl = r.randint(target_lvl, max_lvl)
            else:
                mon_lvl = r.randint(min_lvl, max_lvl)

            mon = cls.generate_pokemon(species, mon_lvl, rng=r)
            generated_team.append(mon)

        # Assign team and lead Pokemon to trainer
        trainer.team = generated_team
        if generated_team:
            trainer.set_active_pokemon(generated_team[0])

        return generated_team

    @classmethod
    def create_trainer(
        cls,
        trainer_id: str,
        name: str,
        title: str,
        archetype: Union[TrainerArchetype, str] = TrainerArchetype.YOUNGSTER,
        difficulty: Union[DifficultyProfile, str] = DifficultyProfile.NORMAL,
        region_id: str = "starting_meadow",
        player: Optional[Player] = None,
        dialogue_intro: str = "",
        dialogue_defeat: str = "",
        dialogue_victory: str = "",
        reward_items: Optional[dict[str, int]] = None,
        rng: Optional[random.Random] = None,
        seed: Optional[int] = None,
    ) -> Trainer:
        """
        Creates and returns a new Trainer instance with an automatically
        generated, level-appropriate team.
        """
        # Determine default rewards if not specified
        if reward_items is None:
            diff_enum = (
                difficulty
                if isinstance(difficulty, DifficultyProfile)
                else DifficultyProfile[str(difficulty).upper()]
            )
            reward_items = dict(DEFAULT_DIFFICULTY_REWARDS.get(diff_enum, {"potion": 1}))

        trainer = Trainer(
            trainer_id=trainer_id,
            name=name,
            title=title,
            archetype=archetype,
            difficulty=difficulty,
            region_id=region_id,
            dialogue_intro=dialogue_intro,
            dialogue_defeat=dialogue_defeat,
            dialogue_victory=dialogue_victory,
            reward_items=reward_items,
        )

        cls.generate_team(
            trainer=trainer,
            player=player,
            region_id=region_id,
            rng=rng,
            seed=seed,
        )

        return trainer


# Convenient module-level aliases
calculate_player_party_strength = TrainerTeamGenerator.calculate_party_strength
get_eligible_species_for_trainer = TrainerTeamGenerator.get_eligible_species
generate_pokemon_for_trainer = TrainerTeamGenerator.generate_pokemon
generate_trainer_team = TrainerTeamGenerator.generate_team
create_trainer = TrainerTeamGenerator.create_trainer
