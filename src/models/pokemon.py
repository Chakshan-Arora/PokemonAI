"""
Individual Pokémon instance model.
"""
from typing import Optional, Sequence, Union, Any
from src.models.species import PokemonSpecies
from src.models.personality import Personality
from src.models.attack import Attack

# Valid stat ranges for bond and obedience
MIN_BOND: int = 0
MAX_BOND: int = 100
MIN_OBEDIENCE: int = 0
MAX_OBEDIENCE: int = 100

# Default maximum number of known attacks
MAX_KNOWN_MOVES: int = 4

# Module-level counter and registry to generate unique 5-digit IDs (e.g. "10001", "10002")
_pokemon_id_counter: int = 10000
_used_pokemon_ids: set[str] = set()


def generate_pokemon_id() -> str:
    """Generates a unique 5-digit string ID for a Pokemon instance."""
    global _pokemon_id_counter
    while True:
        _pokemon_id_counter += 1
        candidate = f"{_pokemon_id_counter:05d}"
        if candidate not in _used_pokemon_ids:
            _used_pokemon_ids.add(candidate)
            return candidate


class Pokemon:
    """
    Represents an individual Pokémon instance with its own level, stats,
    personality, bond, obedience, and moves.
    """

    def __init__(
        self,
        species: PokemonSpecies,
        personality: Personality,
        level: int = 1,
        experience: int = 0,
        current_hp: Optional[int] = None,
        bond: int = 0,
        obedience: int = 100,
        unique_id: Optional[str] = None,
        nickname: Optional[str] = None,
        attacks: Optional[Sequence[Attack]] = None,
        trained_stats: Optional[dict[str, int]] = None,
        trust: Optional[float] = None,
        affection: Optional[float] = None,
        last_talk_time: float = 0.0,
    ) -> None:
        if not isinstance(species, PokemonSpecies):
            raise TypeError(f"species must be a PokemonSpecies instance, got {type(species).__name__}.")
        if not isinstance(personality, Personality):
            raise TypeError(f"personality must be a Personality instance, got {type(personality).__name__}.")

        self._species = species
        self._personality = personality
        if unique_id is not None:
            self._unique_id = str(unique_id)
            _used_pokemon_ids.add(self._unique_id)
        else:
            self._unique_id = generate_pokemon_id()
        self._nickname = nickname.strip() if nickname and nickname.strip() else None

        # Validate and set level and experience
        self.level = level
        self.experience = experience

        # Validate and set bond and obedience
        self.bond = bond
        self.obedience = obedience

        # Validate and set trust and affection
        self._trust: float = float(trust) if trust is not None else float(self._obedience)
        self._affection: float = float(affection) if affection is not None else float(self._bond)
        self._last_talk_time: float = float(last_talk_time)
        self._awarded_max_bond_xp: bool = (self._bond >= 100)

        # Initialize trained combat stats (Attack, Defense, Speed)
        self._trained_stats: dict[str, int] = {
            "attack": 0,
            "defense": 0,
            "speed": 0,
        }
        if trained_stats:
            for k, v in trained_stats.items():
                self.set_trained_stat(k, v)

        # Initialize attacks list
        self._attacks: list[Attack] = []
        # Level-up moves awarded to this Pokemon instance: set of (level, attack_name)
        self._awarded_level_moves: set[tuple[int, str]] = set()
        # Active status effects on this Pokemon instance
        self._status_effects: list[Any] = []
        if attacks:
            for attack in attacks:
                self.assign_attack(attack)

        # Set current HP (defaults to max_hp if not explicitly provided)
        if current_hp is None:
            self._current_hp = self.max_hp
        else:
            self.current_hp = current_hp

    # --- Properties ---

    @property
    def unique_id(self) -> str:
        """Unique identifier for this specific Pokémon instance."""
        return self._unique_id

    @property
    def species(self) -> PokemonSpecies:
        """Reference to the Pokémon's species blueprint."""
        return self._species

    @property
    def personality(self) -> Personality:
        """Personality trait values for this individual Pokémon."""
        return self._personality

    @property
    def nickname(self) -> Optional[str]:
        """Custom nickname for this Pokémon, if set."""
        return self._nickname

    @nickname.setter
    def nickname(self, value: Optional[str]) -> None:
        self._nickname = value.strip() if value and value.strip() else None

    @property
    def display_name(self) -> str:
        """Returns the nickname if present, otherwise the species name."""
        return self._nickname if self._nickname else self._species.name

    @property
    def max_hp(self) -> int:
        """
        Derives maximum HP from species base HP and current level.
        Formula: base_hp + (level * 2).
        Can be replaced with a progression system formula later.
        """
        return self._species.base_hp + (self._level * 2)

    # --- Individual Combat Stats & Training ---

    @property
    def attack(self) -> int:
        """Effective Attack stat (species base_attack + trained attack bonus)."""
        return self._species.base_attack + self._trained_stats["attack"]

    @property
    def effective_attack(self) -> int:
        """Effective combat Attack stat including active temporary modifications."""
        from src.models.status_effect import StatusEffectType
        mult = 1.0
        for eff in self._status_effects:
            if getattr(eff, "effect_type", None) == StatusEffectType.ATTACK_REDUCTION:
                m = getattr(eff, "multiplier", 0.8)
                mult *= (m if m is not None else 0.8)
        mult = max(0.25, mult)
        return max(1, int(self.attack * mult))

    @property
    def defense(self) -> int:
        """Effective Defense stat (species base_defense + trained defense bonus)."""
        return self._species.base_defense + self._trained_stats["defense"]

    @property
    def effective_defense(self) -> int:
        """Effective combat Defense stat including active temporary modifications."""
        from src.models.status_effect import StatusEffectType
        mult = 1.0
        for eff in self._status_effects:
            if getattr(eff, "effect_type", None) == StatusEffectType.DEFENSE_REDUCTION:
                m = getattr(eff, "multiplier", 0.8)
                mult *= (m if m is not None else 0.8)
        mult = max(0.25, mult)
        return max(1, int(self.defense * mult))

    @property
    def speed(self) -> int:
        """Effective Speed stat (species base_speed + trained speed bonus)."""
        return self._species.base_speed + self._trained_stats["speed"]

    @property
    def base_attack(self) -> int:
        """Species baseline Attack stat."""
        return self._species.base_attack

    @property
    def base_defense(self) -> int:
        """Species baseline Defense stat."""
        return self._species.base_defense

    @property
    def base_speed(self) -> int:
        """Species baseline Speed stat."""
        return self._species.base_speed

    @property
    def trained_attack(self) -> int:
        """Trained Attack bonus."""
        return self._trained_stats["attack"]

    @property
    def trained_defense(self) -> int:
        """Trained Defense bonus."""
        return self._trained_stats["defense"]

    @property
    def trained_speed(self) -> int:
        """Trained Speed bonus."""
        return self._trained_stats["speed"]

    @property
    def trained_stats(self) -> dict[str, int]:
        """Copy of trained stats dictionary."""
        return dict(self._trained_stats)

    def get_stat(self, stat_name: str) -> int:
        """Returns the effective value for the specified stat name."""
        norm = stat_name.strip().lower()
        if norm == "attack":
            return self.attack
        elif norm == "defense":
            return self.defense
        elif norm == "speed":
            return self.speed
        elif norm in ("hp", "max_hp"):
            return self.max_hp
        raise ValueError(f"Unknown stat: '{stat_name}'.")

    def get_trained_stat(self, stat_name: str) -> int:
        """Returns the trained bonus for the specified stat name."""
        norm = stat_name.strip().lower()
        if norm in self._trained_stats:
            return self._trained_stats[norm]
        raise ValueError(f"Unknown stat: '{stat_name}'.")

    def set_trained_stat(self, stat_name: str, value: int) -> None:
        """Sets the trained bonus for a supported stat."""
        norm = stat_name.strip().lower()
        if norm not in self._trained_stats:
            raise ValueError(f"Unsupported stat for training: '{stat_name}'.")
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(f"Trained stat value must be an integer, got {type(value).__name__}.")
        if value < 0:
            raise ValueError(f"Trained stat bonus cannot be negative, got {value}.")
        self._trained_stats[norm] = value

    @property
    def current_hp(self) -> int:
        """Current hit points of the Pokémon."""
        return self._current_hp

    @current_hp.setter
    def current_hp(self, value: int) -> None:
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(f"Current HP must be an integer, got {type(value).__name__}.")
        if value < 0:
            raise ValueError(f"Current HP cannot be negative, got {value}.")
        if value > self.max_hp:
            raise ValueError(f"Current HP ({value}) cannot exceed maximum HP ({self.max_hp}).")
        self._current_hp = value

    def take_damage(self, amount: int) -> int:
        """
        Applies incoming damage to the Pokemon.
        Clamps HP at zero so it never falls below 0.
        Returns the actual damage taken.
        """
        if not isinstance(amount, int) or isinstance(amount, bool):
            raise TypeError(f"Damage amount must be an integer, got {type(amount).__name__}.")
        if amount < 0:
            raise ValueError(f"Damage amount cannot be negative, got {amount}.")
        actual_damage = min(self._current_hp, amount)
        self._current_hp = max(0, self._current_hp - amount)
        return actual_damage

    def heal(self, amount: int) -> int:
        """
        Restores HP to the Pokemon.
        Clamps HP at max_hp so it never exceeds maximum HP.
        Returns the actual amount healed.
        """
        if not isinstance(amount, int) or isinstance(amount, bool):
            raise TypeError(f"Heal amount must be an integer, got {type(amount).__name__}.")
        if amount < 0:
            raise ValueError(f"Heal amount cannot be negative, got {amount}.")
        actual_healed = min(self.max_hp - self._current_hp, amount)
        self._current_hp = min(self.max_hp, self._current_hp + amount)
        return actual_healed

    def heal_full(self) -> int:
        """
        Restores HP to maximum and clears all temporary combat status effects and stat debuffs.
        Returns the actual amount of HP restored.
        """
        actual_healed = self.max_hp - self._current_hp
        self._current_hp = self.max_hp
        self.clear_status_effects()
        return actual_healed

    def restore_stats(self) -> None:
        """Restores the Pokemon to full health and returns all combat stats to default values."""
        self.heal_full()

    @property
    def is_fainted(self) -> bool:
        """Returns True if the Pokemon has 0 HP and cannot battle."""
        return self._current_hp <= 0

    @property
    def can_battle(self) -> bool:
        """Returns True if the Pokemon has more than 0 HP and can battle."""
        return self._current_hp > 0

    @property
    def level(self) -> int:
        """Current level of the Pokémon."""
        return self._level

    @level.setter
    def level(self, value: int) -> None:
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(f"Level must be an integer, got {type(value).__name__}.")
        if value < 1:
            raise ValueError(f"Level must be positive (>= 1), got {value}.")
        if value > 100:
            raise ValueError(f"Level cannot exceed maximum level of 100, got {value}.")
        self._level = value

    @property
    def is_max_level(self) -> bool:
        """Returns True if the Pokémon has reached maximum level (100)."""
        return self._level >= 100

    @property
    def xp_for_next_level(self) -> int:
        """XP required to advance to the next level."""
        from src.models.progression import get_xp_for_next_level
        return get_xp_for_next_level(self._level)

    def gain_experience(self, xp: int):
        """
        Awards experience points to this Pokémon, updating level, stats, and HP.
        Returns a LevelUpResult with detailed progression metrics.
        """
        from src.models.progression import apply_experience
        return apply_experience(self, xp)

    @property
    def experience(self) -> int:
        """Total accumulated experience points."""
        return self._experience

    @experience.setter
    def experience(self, value: int) -> None:
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(f"Experience must be an integer, got {type(value).__name__}.")
        if value < 0:
            raise ValueError(f"Experience cannot be negative, got {value}.")
        self._experience = value

    @property
    def bond(self) -> int:
        """Bond level with the trainer (0 to 100)."""
        return self._bond

    @bond.setter
    def bond(self, value: int) -> None:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise TypeError(f"Bond must be a number, got {type(value).__name__}.")
        if not (MIN_BOND <= value <= MAX_BOND):
            raise ValueError(f"Bond must be between {MIN_BOND} and {MAX_BOND}, got {value}.")
        self._bond = int(value)

    @property
    def obedience(self) -> int:
        """Obedience level (0 to 100)."""
        return self._obedience

    @obedience.setter
    def obedience(self, value: int) -> None:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise TypeError(f"Obedience must be a number, got {type(value).__name__}.")
        if not (MIN_OBEDIENCE <= value <= MAX_OBEDIENCE):
            raise ValueError(f"Obedience must be between {MIN_OBEDIENCE} and {MAX_OBEDIENCE}, got {value}.")
        self._obedience = int(value)

    @property
    def trust(self) -> float:
        """Trust level with trainer (0.0 to 100.0)."""
        return self._trust

    @trust.setter
    def trust(self, value: float) -> None:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise TypeError("Trust must be a float or int.")
        self._trust = max(0.0, min(100.0, float(value)))
        self._obedience = int(round(self._trust))

    @property
    def affection(self) -> float:
        """Affection level with trainer (0.0 to 100.0)."""
        return self._affection

    @affection.setter
    def affection(self, value: float) -> None:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise TypeError("Affection must be a float or int.")
        self._affection = max(0.0, min(100.0, float(value)))

    @property
    def last_talk_time(self) -> float:
        """Timestamp or game time of last conversation."""
        return self._last_talk_time

    @last_talk_time.setter
    def last_talk_time(self, value: float) -> None:
        self._last_talk_time = float(value)

    @property
    def bond_multiplier(self) -> float:
        """Returns 1.5x multiplier if both trust and affection > 50, otherwise 1.0."""
        return 1.5 if (self._trust > 50.0 and self._affection > 50.0) else 1.0

    def check_and_award_max_bond_exp(self) -> int:
        """
        If bond reaches 100%, awards 50% of total EXP required to go from current level to next level.
        Returns the awarded exp amount (0 if not awarded or already awarded).
        """
        if self._bond >= 100 and not getattr(self, "_awarded_max_bond_xp", False):
            self._awarded_max_bond_xp = True
            total_needed = self.xp_for_next_level
            bonus_xp = int(total_needed * 0.5)
            if bonus_xp > 0:
                self.gain_experience(bonus_xp)
            return bonus_xp
        elif self._bond < 100:
            self._awarded_max_bond_xp = False
        return 0

    def decay_trust_and_affection(self, amount: float = 2.0) -> None:
        """Decreases trust and affection by the specified amount (minimum 0)."""
        self.trust = max(0.0, self._trust - amount)
        self.affection = max(0.0, self._affection - amount)

    @property
    def attacks(self) -> list[Attack]:
        """List of attacks currently assigned to this Pokémon."""
        return list(self._attacks)

    def assign_attack(self, attack: Attack) -> None:
        """
        Assigns an attack to this Pokémon.
        Ensures the attack is an Attack instance and avoids duplicate entries.
        """
        if not isinstance(attack, Attack):
            raise TypeError(f"Expected Attack instance, got {type(attack).__name__}.")
        if attack not in self._attacks:
            self._attacks.append(attack)

    def knows_attack(self, attack: Union[Attack, str]) -> bool:
        """Checks if this Pokemon currently knows the specified attack (by Attack instance or name)."""
        if isinstance(attack, Attack):
            return attack in self._attacks
        elif isinstance(attack, str):
            norm = attack.strip().lower()
            return any(a.name.strip().lower() == norm for a in self._attacks)
        return False

    def get_attack_by_name(self, name: str) -> Optional[Attack]:
        """Returns the known attack matching the given name, or None if not known."""
        if not isinstance(name, str):
            return None
        norm = name.strip().lower()
        for a in self._attacks:
            if a.name.strip().lower() == norm:
                return a
        return None

    def forget_attack(self, attack: Union[Attack, str]) -> bool:
        """
        Removes an attack from known attacks.
        Returns True if the attack was found and removed, False otherwise.
        """
        target = self.get_attack_by_name(attack) if isinstance(attack, str) else attack
        if isinstance(target, Attack) and target in self._attacks:
            self._attacks.remove(target)
            return True
        return False

    def replace_attack(self, old_attack: Union[Attack, str], new_attack: Attack) -> bool:
        """
        Replaces an existing known attack with a new attack.
        Preserves original loadout if replacement cannot be performed.
        Returns True on success, False otherwise.
        """
        if not isinstance(new_attack, Attack):
            raise TypeError(f"new_attack must be an Attack instance, got {type(new_attack).__name__}.")
        target_old = self.get_attack_by_name(old_attack) if isinstance(old_attack, str) else old_attack
        if not isinstance(target_old, Attack) or target_old not in self._attacks:
            return False
        if self.knows_attack(new_attack):
            return False
        idx = self._attacks.index(target_old)
        self._attacks[idx] = new_attack
        return True

    def is_level_move_awarded(self, level: int, attack_name: str) -> bool:
        """Checks if a level-up move has already been awarded at the given level."""
        return (level, attack_name.strip().lower()) in self._awarded_level_moves

    def mark_level_move_awarded(self, level: int, attack_name: str) -> None:
        """Marks a level-up move as awarded for this Pokemon instance."""
        self._awarded_level_moves.add((level, attack_name.strip().lower()))

    @property
    def awarded_level_moves(self) -> tuple[tuple[int, str], ...]:
        """Awarded level-up moves as sorted (level, attack_name) tuples."""
        return tuple(sorted(self._awarded_level_moves))

    # --- Battle Status Effects ---

    @property
    def status_effects(self) -> tuple[Any, ...]:
        """Active status effects currently on this Pokemon instance."""
        return tuple(self._status_effects)

    def add_status_effect(self, effect: Any) -> None:
        """Adds an active status effect to this Pokemon instance."""
        if effect not in self._status_effects:
            self._status_effects.append(effect)

    def remove_status_effect(self, effect_type: Any) -> bool:
        """
        Removes an active status effect of the specified type.
        Returns True if found and removed, False otherwise.
        """
        for eff in list(self._status_effects):
            if getattr(eff, "effect_type", None) == effect_type:
                self._status_effects.remove(eff)
                return True
        return False

    def clear_status_effects(self) -> None:
        """Clears all active status effects from this Pokemon instance."""
        self._status_effects.clear()

    def has_status_effect(self, effect_type: Any) -> bool:
        """Checks if this Pokemon has an active status effect of the specified type."""
        return any(getattr(eff, "effect_type", None) == effect_type for eff in self._status_effects)

    def get_status_effect(self, effect_type: Any) -> Optional[Any]:
        """Returns the active status effect of the specified type, or None if absent."""
        for eff in self._status_effects:
            if getattr(eff, "effect_type", None) == effect_type:
                return eff
        return None

    def __repr__(self) -> str:
        return (
            f"Pokemon(id='{self.unique_id}', species='{self._species.name}', "
            f"level={self._level}, hp={self._current_hp}/{self.max_hp}, "
            f"bond={self._bond}, obedience={self._obedience})"
        )
