from __future__ import annotations

import sys
import threading

from config.manager import ConfigManager
from core.brain import Brain
from core.events import EventBus
from core.router import Router
from memory.experience import ExperienceStore
from memory.facts import FactStore
from memory.goals import GoalManager
from memory.state import AgentStateStore
from plugins import PluginLoader
from services.daily_briefing import DailyBriefingService
from services.event_manager import EventManager
from services.goal_service import AutonomousGoalService
from services.health_monitor import HealthMonitor
from services.plugin_manager import PluginManager
from services.provider_monitor import ProviderMonitor
from tools.registry import ToolRegistry
from utils.logger import get_logger
from voice.controller import VoiceController
from voice.config import VOICE_ENABLED


def print_startup_screen(brain: Brain, registry: ToolRegistry, config: ConfigManager) -> None:
    print("====================================")
    print("ATLAS v1")
    print("Brain:")
    print("✓ Online")
    print("Memory:")
    print("✓ Connected")
    print("Router:")
    print("✓ Ready")
    print("Model:")
    print(f"  {config.get('model')}")
    print("Tools:")
    print(f"  Loaded {len(registry.list())} tools")
    print("Plugins:")
    print("  Loaded")
    print("Voice:")
    print("  " + ("✓ Enabled" if VOICE_ENABLED else "Disabled"))
    print("====================================")
    print(f"Using LM Studio endpoint: {brain.endpoint}")


def main() -> None:
    if "--ui" in sys.argv:
        # Launch the desktop interface instead of the CLI loop.
        from interface.gui import launch_ui
        from interface.run import build_backend

        backend = build_backend()
        launch_ui(
            router=backend["router"],
            brain=backend["brain"],
            memory=backend["memory"],
            voice_controller=backend["voice_controller"],
            config_manager=backend["config_manager"],
            tool_registry=backend["tool_registry"],
        )
        return

    config = ConfigManager()
    logger = get_logger("ATLAS")
    logger.info("ATLAS starting up (model=%s, endpoint=%s)", config.get("model"), config.get("endpoint", "http://localhost:1234/v1"))
    event_bus = EventBus()
    memory = FactStore()
    registry = ToolRegistry()
    registry.discover()
    brain = Brain(
        config_manager=config,
        history_limit=config.get("history_size"),
        temperature=config.get("temperature"),
        max_tokens=config.get("max_tokens")
    )
    # Persistent agent state, goals, and learned experience share the memory DB
    # so autonomy survives restarts. Built once here and shared with the router,
    # briefing, and the background goal service.
    state_store = AgentStateStore()
    goals = GoalManager(memory=memory)
    experiences = ExperienceStore(memory=memory)
    router = Router(
        brain=brain,
        memory=memory,
        registry=registry,
        config=config,
        state_store=state_store,
        goals=goals,
        experiences=experiences,
    )

    plugin_manager = PluginManager()
    plugin_manager.discover()

    briefing = DailyBriefingService(router=router, memory=memory, goal_manager=goals)
    briefing.start()

    # Background autonomous goal loop - disabled by default; enabled with
    # autonomy_enabled: true in config.json. It respects hard safety and never
    # auto-approves destructive steps.
    goal_service: AutonomousGoalService | None = None
    if config.get("planner_enabled", True) and config.get("autonomy_enabled", False):
        goal_service = AutonomousGoalService(
            autonomy=router._autonomy,
            interval_seconds=config.get("autonomy_interval_seconds", 600.0),
            max_tasks=config.get("autonomy_max_tasks_per_cycle", 2),
            enabled=True,
        )
        goal_service.start()
        print("Autonomy: ✓ Background goal service enabled")

    voice_controller: VoiceController | None = None
    voice_enabled = config.get("voice_enabled", False)
    if voice_enabled:
        try:
            voice_controller = VoiceController(
                router=router,
                enabled=voice_enabled,
                whisper_model=config.get("whisper_model"),
                tts_engine=config.get("tts_engine"),
                tts_voice=config.get("tts_voice"),
            )
            voice_controller.start()
            voice_thread = threading.Thread(target=voice_controller.run_background, daemon=True)
            voice_thread.start()
            print("Voice: ✓ Voice assistant enabled")
        except Exception as e:
            print(f"Voice: Warning - Failed to start voice: {e}")
            print("Voice: Continuing in CLI mode.")
    else:
        # Store a disabled controller for runtime toggling
        voice_controller = VoiceController(router=router, enabled=False)

    # Pass voice controller to router for voice commands
    router._voice_controller = voice_controller

    print_startup_screen(brain, registry, config)
    print("ATLAS is ready. Type /help for commands or 'exit' to quit.")

    while True:
        try:
            prompt = input("You: ").strip()
        except EOFError:
            print()
            break

        if not prompt:
            continue

        if prompt.lower() in {"exit", "quit"}:
            print("ATLAS: Goodbye.")
            if voice_controller is not None:
                voice_controller.stop()
            if goal_service is not None:
                goal_service.stop()
            briefing.stop()
            break

        if prompt.startswith("/") or prompt.lower().startswith(("remember ", "forget ", "recall ", "search ")):
            print(router.route(prompt))
            continue

        if brain.stream:
            print("ATLAS: ", end="", flush=True)
            for chunk in router.stream(prompt):
                print(chunk, end="", flush=True)
            print()
        else:
            print(router.route(prompt))


if __name__ == "__main__":
    main()
