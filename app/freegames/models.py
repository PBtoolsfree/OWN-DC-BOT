"""
Models module for Free Games Tracker.
Re-exports the persistent database models for the freegames domain.
"""

from app.database.models import (
    FreeGameSettings,
    FreeGameOfferModel,
    FreeGameSourceModel,
    FreeGameNotificationModel,
)

__all__ = [
    "FreeGameSettings",
    "FreeGameOfferModel",
    "FreeGameSourceModel",
    "FreeGameNotificationModel",
]
