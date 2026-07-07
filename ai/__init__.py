"""
AI automation package
"""

from .automation import AutomationEngine
from .frequency_lock import FrequencyLockController
from .chaimera3sp import CHAiMERA3sp, CHAiMERAProvider
from .tlc import (
    TLCModule,
    TechnicalObservation,
    KnowledgeEntry,
    TechnicalKnowledgeStore,
    PatternRecognizer,
    DreamStateEngine,
    DreamSession,
    DreamEvaluation,
    DreamResearch,
    DreamCorruption,
    ReactiveCapture,
    MindStatus,
    AnomalyFilter,
    AnomalyRecord,
    OutcomeInventory,
    PredictiveReasoner,
    Prediction,
    AutonomousDecision,
)

__all__ = [
    "AutomationEngine",
    "FrequencyLockController",
    "CHAiMERA3sp",
    "CHAiMERAProvider",
    "TLCModule",
    "TechnicalObservation",
    "KnowledgeEntry",
    "TechnicalKnowledgeStore",
    "PatternRecognizer",
    "DreamStateEngine",
    "DreamSession",
    "DreamEvaluation",
    "DreamResearch",
    "DreamCorruption",
    "ReactiveCapture",
    "MindStatus",
    "AnomalyFilter",
    "AnomalyRecord",
    "OutcomeInventory",
    "PredictiveReasoner",
    "Prediction",
    "AutonomousDecision",
]
