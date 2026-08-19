"""Self-evaluation for ATLAS missions.

After every mission (autonomous or user-initiated) ATLAS assesses its own
outcome: what happened, how much of the goal was actually accomplished, what
went wrong, and what to try next time. The distilled recommendation becomes
a reusable lesson so the agent learns without repeating failures.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Evaluation:
    """Structured outcome of a self-evaluation."""

    goal: str
    verdict: str  # "success" | "partial" | "failed"
    score: float  # 0.0 .. 1.0
    summary: str = ""
    issues: list[str] = field(default_factory=list)
    recommendation: str = ""
    lessons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "verdict": self.verdict,
            "score": self.score,
            "summary": self.summary,
            "issues": self.issues,
            "recommendation": self.recommendation,
            "lessons": self.lessons,
        }


class SelfEvaluator:
    """Heuristic (with optional LLM refinement) mission self-evaluation.

    ``experiences`` is an optional :class:`memory.experience.ExperienceStore`
    (used to record lessons) and ``brain`` an optional :class:`core.brain.Brain`
    used only for a richer, best-effort recommendation.
    """

    def __init__(self, experiences: Any | None = None, brain: Any | None = None) -> None:
        self.experiences = experiences
        self.brain = brain

    # -- core evaluation -----------------------------------------------
    def evaluate_mission(
        self,
        goal: str,
        plan_result: dict[str, Any] | None,
        *,
        task_type: str = "",
        strategy_key: str = "",
    ) -> Evaluation:
        plan_result = plan_result or {}
        tasks: list[dict[str, Any]] = plan_result.get("tasks", []) or []
        total = max(len(tasks), 1)
        completed = sum(1 for t in tasks if t.get("status") == "completed")
        failed = sum(1 for t in tasks if t.get("status") == "failed")
        recovered = sum(
            1
            for i, t in enumerate(tasks)
            if i > 0 and t.get("status") == "completed" and tasks[i - 1].get("status") == "failed"
        )

        score = completed / float(total) if tasks else (1.0 if plan_result.get("success") else 0.0)

        # Verdict is driven by the plan-level success flag first: steps can be
        # recorded as "completed" yet still fail verification, and that must
        # not be reported as a clean success.
        if tasks:
            if plan_result.get("success"):
                verdict = "success"
            elif completed > 0:
                verdict = "partial"
            else:
                verdict = "failed"
        else:
            verdict = "success" if plan_result.get("success") else "failed"

        issues = [
            f"[{t.get('id')}] {t.get('description', '')}: {t.get('error') or t.get('result', '')[:80]}"
            for t in tasks
            if t.get("status") == "failed" or t.get("error")
        ]

        summary = (
            f"{completed}/{total} steps completed, {failed} failed, {recovered} recovered "
            f"(score {score:.2f}, {verdict})."
        )
        recommendation = self._recommendation(goal, verdict, summary, task_type, strategy_key, issues)
        lessons = self._lessons(goal, verdict, score, task_type, strategy_key, recommendation, issues)

        return Evaluation(
            goal=goal,
            verdict=verdict,
            score=score,
            summary=summary,
            issues=issues,
            recommendation=recommendation,
            lessons=lessons,
        )

    # -- recommendation -------------------------------------------------
    def _recommendation(
        self,
        goal: str,
        verdict: str,
        summary: str,
        task_type: str,
        strategy_key: str,
        issues: list[str],
    ) -> str:
        if self.brain is not None and self.brain.ask is not None:
            try:
                prompt = (
                    "ATLAS just finished an autonomous mission and is evaluating itself. "
                    f"Goal: {goal}\nVerdict: {verdict}\n{summary}\n"
                    f"Task type: {task_type or 'unknown'}, strategy: {strategy_key or 'unknown'}\n"
                    + (f"Issues:\n" + "\n".join(issues) if issues else "No issues reported.")
                    + "\nGive ONE concise suggestion (max 2 sentences) for how to do better next time. "
                      "If it went well, say what to keep doing. No markdown."
                )
                suggestion = self.brain.ask(prompt)
                if suggestion and not suggestion.startswith(("LM Studio", "LLM")):
                    return suggestion.strip()
            except Exception:
                pass
        if verdict == "success" and strategy_key:
            return f"The '{strategy_key}' approach worked for this {task_type or 'task'} type; keep using it."
        if issues:
            return f"Consider a different strategy or more verification for: {issues[0]}"
        return "Break the goal into smaller, verifiable steps next time."

    # -- lessons --------------------------------------------------------
    def _lessons(
        self,
        goal: str,
        verdict: str,
        score: float,
        task_type: str,
        strategy_key: str,
        recommendation: str,
        issues: list[str],
    ) -> list[str]:
        short_goal = goal[:100]
        lessons = [
            f"Mission '{short_goal}' finished {verdict} (score {score:.2f}). "
            f"Strategy '{strategy_key or 'default'}' for type '{task_type or 'general'}'. {recommendation}"
        ]
        if verdict == "failed" and issues:
            lessons.append(f"Repeat failure for '{short_goal}': {issues[0]}")
        return lessons

    # -- persistence ----------------------------------------------------
    def persist_lessons(self, evaluation: Evaluation) -> None:
        """Store lessons into the experience store's memory (best-effort)."""
        if self.experiences is None:
            return
        for i, lesson in enumerate(evaluation.lessons):
            self.experiences.record_lesson(
                f"lesson:{i}",
                lesson,
                importance=1.3 if evaluation.verdict == "failed" else 1.0,
            )