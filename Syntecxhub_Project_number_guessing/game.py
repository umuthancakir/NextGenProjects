#!/usr/bin/env python3
"""
Number Guessing Game with leaderboard, difficulty levels, binary-search computer-guess mode,
session statistics, and AI-powered hints / performance summaries.
"""

import json
import math
import os
import random
import sys
import argparse
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

try:
    import anthropic
    _AI = True
except ImportError:
    _AI = False

# ── Difficulty levels ────────────────────────────────────────────────────────

@dataclass
class Difficulty:
    name: str
    lo: int
    hi: int
    max_guesses: Optional[int]   # None = unlimited

LEVELS: dict[str, Difficulty] = {
    "easy":    Difficulty("Easy",    1,   50,  None),
    "medium":  Difficulty("Medium",  1,  100,  10),
    "hard":    Difficulty("Hard",    1,  200,   7),
    "extreme": Difficulty("Extreme", 1,  500,   6),
}


# ── Leaderboard ──────────────────────────────────────────────────────────────

LEADERBOARD_FILE = Path(__file__).parent / "leaderboard.json"

@dataclass
class PlayerRecord:
    games_played: int = 0
    games_won: int = 0
    total_attempts: int = 0
    best: dict[str, int] = field(default_factory=dict)   # difficulty → best attempts

def _load_lb() -> dict[str, PlayerRecord]:
    if not LEADERBOARD_FILE.exists():
        return {}
    with open(LEADERBOARD_FILE) as f:
        raw = json.load(f)
    return {name: PlayerRecord(**data) for name, data in raw.items()}

def _save_lb(lb: dict[str, PlayerRecord]) -> None:
    with open(LEADERBOARD_FILE, "w") as f:
        json.dump({n: asdict(r) for n, r in lb.items()}, f, indent=2)

def record_result(player: str, difficulty: str, attempts: int, won: bool) -> None:
    lb = _load_lb()
    rec = lb.setdefault(player, PlayerRecord())
    rec.games_played += 1
    rec.total_attempts += attempts
    if won:
        rec.games_won += 1
        prev = rec.best.get(difficulty)
        if prev is None or attempts < prev:
            rec.best[difficulty] = attempts
    _save_lb(lb)

def show_leaderboard() -> None:
    lb = _load_lb()
    if not lb:
        print("  Leaderboard is empty."); return
    print(f"\n{'Player':<20} {'Played':>6} {'Won':>6} {'Win%':>6} {'Avg Att':>8}  Best per difficulty")
    print("─" * 80)
    for name, r in sorted(lb.items(), key=lambda x: -x[1].games_won):
        win_pct = 100 * r.games_won / r.games_played if r.games_played else 0
        avg = r.total_attempts / r.games_played if r.games_played else 0
        best_str = "  ".join(f"{d}:{v}" for d, v in sorted(r.best.items()))
        print(f"  {name:<18} {r.games_played:>6} {r.games_won:>6} {win_pct:>5.0f}% {avg:>8.1f}  {best_str}")

def show_stats(player: str) -> None:
    lb = _load_lb()
    if player not in lb:
        print(f"  No records found for '{player}'."); return
    r = lb[player]
    win_pct = 100 * r.games_won / r.games_played if r.games_played else 0
    avg = r.total_attempts / r.games_played if r.games_played else 0
    print(f"\n  Stats for {player}")
    print(f"  Games played : {r.games_played}")
    print(f"  Games won    : {r.games_won}  ({win_pct:.0f}%)")
    print(f"  Avg attempts : {avg:.1f}")
    for diff, best in sorted(r.best.items()):
        print(f"  Best ({diff:<7}): {best} guess(es)")


# ── AI helpers ───────────────────────────────────────────────────────────────

def _claude(system: str, user: str, max_tokens: int = 120) -> str:
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return msg.content[0].text.strip()

def ai_hint(guess: int, direction: str, attempt: int, lo: int, hi: int) -> str:
    if not _AI: return f"Go {direction}!"
    try:
        return _claude(
            "You are a fun game host for a number guessing game. "
            "Give a one-sentence, encouraging, creative hint. "
            "Never reveal the target number. Keep it under 20 words.",
            f"Player guessed {guess} (attempt {attempt}). "
            f"The answer is {direction}. Range remaining: {lo}–{hi}.",
        )
    except Exception:
        return f"Go {direction}!"

def ai_summary(player: str, secret: int, attempts: int, won: bool,
               difficulty: str, history: list[int]) -> str:
    if not _AI: return ""
    try:
        outcome = "won" if won else "did not find the number"
        return _claude(
            "You are an encouraging game host. Write a 2-sentence personalized performance summary "
            "for the player. Be specific about their guessing pattern. Keep it positive.",
            f"Player: {player}. Difficulty: {difficulty}. Secret: {secret}. "
            f"Outcome: {outcome} in {attempts} attempt(s). "
            f"Guesses in order: {history}.",
            max_tokens=150,
        )
    except Exception:
        return ""


# ── Player-guesses mode ──────────────────────────────────────────────────────

def play_game(player: str, diff: Difficulty, use_ai_hints: bool) -> None:
    secret = random.randint(diff.lo, diff.hi)
    attempts = 0
    guesses: list[int] = []
    remaining = diff.max_guesses

    print(f"\n  Guess a number between {diff.lo} and {diff.hi}.", end="")
    if remaining:
        print(f"  You have {remaining} guess(es).")
    else:
        print()

    while True:
        prompt = f"  Guess [{attempts + 1}]"
        if remaining is not None:
            prompt += f" ({remaining} left)"
        prompt += ": "
        try:
            raw = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Game aborted.")
            return

        if raw.lower() in ("quit", "exit", "q"):
            print(f"  The number was {secret}. Better luck next time!")
            return

        try:
            guess = int(raw)
        except ValueError:
            print("  Please enter a whole number."); continue

        if guess < diff.lo or guess > diff.hi:
            print(f"  Out of range! Stay between {diff.lo} and {diff.hi}."); continue

        attempts += 1
        guesses.append(guess)
        if remaining is not None:
            remaining -= 1

        if guess == secret:
            print(f"\n  Correct! You found {secret} in {attempts} guess(es).")
            record_result(player, diff.name.lower(), attempts, won=True)
            summary = ai_summary(player, secret, attempts, True, diff.name, guesses)
            if summary: print(f"\n  {summary}")
            return

        direction = "higher" if guess < secret else "lower"
        lo_rem = guess + 1 if guess < secret else diff.lo
        hi_rem = diff.hi if guess < secret else guess - 1

        if use_ai_hints:
            hint = ai_hint(guess, direction, attempts, lo_rem, hi_rem)
            print(f"  {hint}")
        else:
            print(f"  Go {direction}!")

        if remaining == 0:
            print(f"\n  Out of guesses! The number was {secret}.")
            record_result(player, diff.name.lower(), attempts, won=False)
            summary = ai_summary(player, secret, attempts, False, diff.name, guesses)
            if summary: print(f"\n  {summary}")
            return


# ── Computer-guesses mode (binary search) ────────────────────────────────────

def computer_guesses(diff: Difficulty) -> None:
    lo, hi = diff.lo, diff.hi
    attempts = 0
    print(f"\n  Think of a number between {lo} and {hi}. I'll find it using binary search.")
    print("  Respond with:  h (higher)  |  l (lower)  |  y (correct)\n")

    while lo <= hi:
        mid = (lo + hi) // 2
        attempts += 1
        try:
            response = input(f"  Attempt {attempts}: Is it {mid}?  > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n  Aborted."); return

        if response in ("y", "yes", "correct", "c"):
            print(f"\n  Found it! {mid}  —  took {attempts} guess(es).")
            optimal = math.ceil(math.log2(diff.hi - diff.lo + 1))
            print(f"  (Optimal for this range: ≤{optimal} guesses)")
            return
        elif response in ("h", "higher"):
            lo = mid + 1
        elif response in ("l", "lower"):
            hi = mid - 1
        else:
            print("  Type 'h', 'l', or 'y'."); lo -= 0  # re-try same mid

    print("  Something's off — are you cheating? ;)")


# ── Entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="Number Guessing Game")
    ap.add_argument("--name",       default="Player", help="Your name")
    ap.add_argument("--difficulty", choices=list(LEVELS), default="medium",
                    help="Game difficulty (default: medium)")
    ap.add_argument("--computer-guess", action="store_true",
                    help="Computer guesses your number using binary search")
    ap.add_argument("--leaderboard", action="store_true", help="Show leaderboard")
    ap.add_argument("--stats",       action="store_true", help="Show your stats")
    ap.add_argument("--no-ai",       action="store_true", help="Disable AI hints")
    args = ap.parse_args()

    if args.leaderboard:
        show_leaderboard(); return
    if args.stats:
        show_stats(args.name); return

    diff = LEVELS[args.difficulty]
    use_ai = _AI and not args.no_ai

    print(f"\n  Number Guessing Game  |  {diff.name}  |  Range {diff.lo}–{diff.hi}", end="")
    if diff.max_guesses:
        print(f"  |  {diff.max_guesses} guesses max")
    else:
        print("  |  Unlimited guesses")

    if args.computer_guess:
        computer_guesses(diff)
        return

    while True:
        play_game(args.name, diff, use_ai)
        show_leaderboard()
        try:
            again = input("\n  Play again? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            break
        if again not in ("y", "yes"):
            break

    print("\n  Thanks for playing!")


if __name__ == "__main__":
    main()
