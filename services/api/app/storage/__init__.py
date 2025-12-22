"""
Storage abstraction for Cat Caption Cage Match.

This module provides a clean interface for game data persistence,
allowing easy swapping between implementations (in-memory, PostgreSQL, etc.).
"""
from .base import Storage
from .memory import InMemoryStorage

__all__ = ["Storage", "InMemoryStorage"]

