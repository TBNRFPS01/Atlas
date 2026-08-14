"""Entry point for launching the ATLAS desktop UI.

Wires the existing ATLAS backend (config, memory, brain, router, tools,
voice) into the tkinter interface. Run with:

    python -m interface.run
"""
from __future__ import annotations


def build_backend():
    """Construct the standard ATLAS backend components and return them."""
    from config.manager import ConfigManager
    from core.brain import Brain
    from core.router import Router
    from memory.facts import FactStore
    from tools.registry import ToolRegistry
    from voice.controller import VoiceController

    config = ConfigManager()
    memory = FactStore()
    registry = ToolRegistry()
    registry.discover()
    brain = Brain(
        config_manager=config,
        history_limit=config.get("history_size"),
        temperature=config.get("temperature"),
        max_tokens=config.get("max_tokens"),
    )
    router = Router(brain=brain, memory=memory, registry=registry, config=config)

    voice_enabled = config.get("voice_enabled", False)
    voice_controller: VoiceController | None = None
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
        except Exception:
            voice_controller = None
    if voice_controller is None:
        try:
            voice_controller = VoiceController(router=router, enabled=False)
        except Exception:
            voice_controller = None

    router._voice_controller = voice_controller

    return {
        "config_manager": config,
        "memory": memory,
        "brain": brain,
        "router": router,
        "voice_controller": voice_controller,
        "tool_registry": registry,
    }


def main() -> None:
    # Apply component-level geometry corrections before any widgets are built.
    from interface.layout_fixes import apply_layout_fixes
    apply_layout_fixes()

    from interface.gui import launch_ui

    backend = build_backend()
    launch_ui(
        router=backend["router"],
        brain=backend["brain"],
        memory=backend["memory"],
        voice_controller=backend["voice_controller"],
        config_manager=backend["config_manager"],
        tool_registry=backend["tool_registry"],
    )


if __name__ == "__main__":
    main()
