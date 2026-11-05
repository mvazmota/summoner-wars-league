"""League layer: policies, replays and analysis.

Sits above the engine: `sw_core` (types) <- `sw_cards` (data) <- `sw_engine` (rules) <-
`sw_league` (bots, matchmaking, reporting). The engine must never import this package.
"""

from __future__ import annotations

__all__ = ["analysis", "policy", "replay"]
