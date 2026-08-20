from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

from core.autonomy import AutonomyController
from core.brain import Brain
from core.context import ContextStore
from core.fast_router import FastIntentRouter
from core.personality import ATLASPersonality
from core.permissions import Decision, PermissionManager
from core.safety import HardSafety, SafetyViolation
from core.skill_manager import SkillManager
from core.undo import UndoStack
from memory.experience import ExperienceStore
from memory.facts import FactStore
from memory.goals import GoalManager
from memory.state import AgentStateStore
from planner.evaluator import SelfEvaluator
from planner.strategies import StrategySelector


class Router:
    """Intelligent request router for ATLAS.

    Requests first get a deterministic fast-path attempt. Unambiguous commands
    are dispatched without waking the LLM; everything else continues through
    ATLAS's existing command, task, skill, tool, and LLM pipelines.
    """

    def __init__(
        self,
        brain: Brain | None = None,
        personality: ATLASPersonality | None = None,
        memory: FactStore | None = None,
        registry=None,
        config=None,
        state_store: AgentStateStore | None = None,
        goals: GoalManager | None = None,
        experiences: ExperienceStore | None = None,
        autonomy: AutonomyController | None = None,
    ) -> None:
        self._voice_controller: Any | None = None
        self._planner_inst: Any | None = None
        self._permissions = PermissionManager()
        self._safety = HardSafety()
        self._undo = UndoStack()
        self._trace: list[str] = []
        self._call_log: list[dict[str, Any]] = []
        self._fast_router = FastIntentRouter()
        self._context = ContextStore()
        if registry is None:
            from tools.registry import ToolRegistry
            registry = ToolRegistry()
            registry.discover()
        self._registry = registry
        self.brain = brain or Brain()
        self.personality = personality or ATLASPersonality()
        self.memory = memory or FactStore()
        self._skill_manager = SkillManager(
            skills_dir="skills",
            permission_manager=self._permissions,
            safety=self._safety,
            registry=self._registry,
        )
        self._skill_manager.load_all()
        self._skills = self._skill_manager.list()
        self._config = config
        self._state = state_store or AgentStateStore()
        self._goals = goals or GoalManager(memory=self.memory)
        self._experiences = experiences or ExperienceStore(memory=self.memory)
        self._strategy_selector = StrategySelector()
        self._self_evaluator = SelfEvaluator(experiences=self._experiences, brain=self.brain)
        self._autonomy = autonomy or AutonomyController(
            router=self,
            state_store=self._state,
            goals=self._goals,
            experiences=self._experiences,
            selector=self._strategy_selector,
            evaluator=self._self_evaluator,
        )

    def _try_fast_path(self, prompt: str) -> str | None:
        """Resolve context and dispatch an unambiguous command without the LLM."""
        resolved = self._context.resolve(prompt)
        intent = self._fast_router.route(resolved)
        if intent is None:
            return None
        dispatch = self._fast_router.to_dispatch(intent)
        if dispatch is None:
            return None
        self._record_trace("fast_intent", intent.name, intent.target or "")
        result = self._dispatch_tool(dispatch)
        self._context.remember(
            prompt,
            intent=intent.name,
            target=intent.target,
            result=result,
        )
        return result

    def route(self, prompt: str) -> str:
        lowered = prompt.lower().strip()

        if lowered.startswith("/auto"):
            goal = prompt[5:].strip()
            if not goal:
                return self.personality.respond("Usage: /auto <goal>  e.g. /auto open VS Code and take a screenshot")
            return self.personality.respond(self._run_autonomous_mission(goal))
        if lowered.startswith("/"):
            return self.personality.respond(self._handle_command(lowered))
        if lowered.startswith("remember "):
            return self.personality.respond(self._remember_memory(prompt))
        if lowered.startswith("forget "):
            return self.personality.respond(self._forget(prompt))
        if lowered.startswith("recall "):
            return self.personality.respond(self._recall(prompt))
        if lowered.startswith("search "):
            return self.personality.respond(self._search(prompt))

        fast_result = self._try_fast_path(prompt)
        if fast_result is not None:
            return self.personality.respond(fast_result)

        if any(phrase in lowered for phrase in self._TASK_TRIGGER_PHRASES):
            return self.personality.respond(self._run_task(prompt))
        if self._skills:
            for skill in self._skills:
                if skill.enabled and skill.valid and skill.matches(lowered):
                    ok, reason = self._skill_manager.can_run(skill)
                    if not ok:
                        self._record_trace("skill", skill.name, "blocked")
                        return self.personality.respond(f"Skill '{skill.name}' blocked: {reason}")
                    return self.personality.respond(skill.run(self, prompt))
        if lowered.startswith("spotify "):
            tool = self._registry.get("spotify")
            if tool is None:
                return self.personality.respond("Spotify tool not loaded.")
            return self.personality.respond(self._spotify_request(prompt))
        if self._looks_like_tool_request(prompt, lowered):
            return self.personality.respond(self._dispatch_tool(lowered))
        return self.personality.respond(self.brain.ask(prompt))

    def stream(self, prompt: str) -> Iterator[str]:
        lowered = prompt.lower().strip()
        if lowered.startswith("/auto"):
            goal = prompt[5:].strip()
            yield self._run_autonomous_mission(goal) if goal else "Usage: /auto <goal>"
            return
        if lowered.startswith("/"):
            yield self._handle_command(lowered)
            return
        if lowered.startswith("remember "):
            yield self._remember_memory(prompt)
            return
        if lowered.startswith("forget "):
            yield self._forget(prompt)
            return
        if lowered.startswith("recall "):
            yield self._recall(prompt)
            return
        if lowered.startswith("search "):
            yield self._search(prompt)
            return

        fast_result = self._try_fast_path(prompt)
        if fast_result is not None:
            yield fast_result
            return

        if any(phrase in lowered for phrase in self._TASK_TRIGGER_PHRASES):
            yield self._run_task(prompt)
            return
        if self._skills:
            for skill in self._skills:
                if skill.enabled and skill.valid and skill.matches(lowered):
                    ok, reason = self._skill_manager.can_run(skill)
                    if not ok:
                        yield f"Skill '{skill.name}' blocked: {reason}"
                        return
                    yield skill.run(self, prompt)
                    return
        if self._looks_like_tool_request(prompt, lowered):
            yield self._dispatch_tool(lowered)
            return
        if self.brain.stream:
            yield from self.brain.ask_stream(prompt)
            return
        yield self.brain.ask(prompt)
