"""Default specialized-agent profiles for ATLAS.

These are profiles, not separate LLMs. The existing planner/model layer decides
how a profile is executed, so users can plug in local or hosted models later.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AgentProfile:
    name: str
    purpose: str
    capabilities: tuple[str, ...]
    max_steps: int = 8


BUILTIN_AGENTS: tuple[AgentProfile, ...] = (
    AgentProfile("researcher", "Find, compare, and verify information.", ("research", "browser", "verification"), 10),
    AgentProfile("coder", "Inspect, modify, test, and explain code.", ("coding", "testing", "debugging"), 12),
    AgentProfile("browser", "Navigate web tasks through approved browser tools.", ("browser", "research"), 8),
    AgentProfile("vision", "Interpret screenshots and visual input.", ("vision", "ocr"), 8),
    AgentProfile("planner", "Break goals into bounded executable plans.", ("planning", "reasoning"), 10),
    AgentProfile("verifier", "Check outputs, assumptions, and task completion.", ("verification", "testing"), 8),
    AgentProfile("memory", "Retrieve and organize useful persistent context.", ("memory", "retrieval"), 6),
    AgentProfile("orchestrator", "Coordinate specialist agents and synthesize results.", ("delegation", "planning", "verification"), 12),
)


def get_agent(name: str) -> AgentProfile | None:
    return next((agent for agent in BUILTIN_AGENTS if agent.name == name), None)
