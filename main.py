from __future__ import annotations

import threading

from config.manager import ConfigManager
from core.brain import Brain
from core.events import EventBus
from core.router import Router
from memory.facts import FactStore
from plugins import PluginLoader
from services.daily_briefing import DailyBriefingService
from services.event_manager import EventManager
from services.health_monitor import HealthMonitor
from services.plugin_manager import PluginManager
from services.provider_monitor import ProviderMonitor
from tools.registry import ToolRegistry
from voice.controller import VoiceController
from voice.config import VOICE_ENABLED


def print_startup_screen(brain: Brain, registry: ToolRegistry, config: ConfigManager) -> None:
    print("====================================")
    print("ATLAS v2")
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
    config = ConfigManager()
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
    router = Router(brain=brain, memory=memory, registry=registry, config=config)

    plugin_manager = PluginManager()
    plugin_manager.discover()

    briefing = DailyBriefingService(router=router, memory=memory)
    briefing.start()

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
