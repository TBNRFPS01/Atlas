"""Entry point for launching the ATLAS desktop UI.

Wires the existing ATLAS backend (config, memory, brain, router, tools, voice)
into the tkinter interface.
"""
from __future__ import annotations


def build_backend():
    """Construct the standard ATLAS backend components and return them."""
    from config.manager import ConfigManager
    from core.brain import Brain
    from core.router import Router
    from core.smart_provider import SmartProvider
    from core.openrouter import OpenRouterProvider
    from core.providers import LocalProvider, GatewayProvider
    from memory.facts import FactStore
    from tools.registry import ToolRegistry
    from voice.controller import VoiceController
    import os

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

    # The GUI uses the same task-aware provider path as the CLI.
    if config.get("openrouter_enabled", False):
        openrouter_key = config.get("openrouter_api_key", "") or os.getenv("OPENROUTER_API_KEY", "")
        if openrouter_key:
            local = LocalProvider(
                base_url=brain.endpoint,
                api_key=brain.api_key,
                model=brain.model,
                temperature=brain.temperature,
                max_tokens=brain.max_tokens,
            )
            cloud = OpenRouterProvider(
                api_key=openrouter_key,
                model=config.get("openrouter_model", OpenRouterProvider.DEFAULT_MODEL),
                models=config.get_openrouter_models(),
                base_url=config.get("openrouter_base_url", OpenRouterProvider.DEFAULT_BASE_URL),
                temperature=brain.temperature,
                max_tokens=brain.max_tokens,
                site_url=config.get("openrouter_site_url", ""),
                app_name=config.get("openrouter_app_name", "ATLAS"),
            )
            providers = {"local": local, "openrouter": cloud}
            gateway_key = config.get("gateway_api_key", "")
            if config.get("gateway_enabled", False) and gateway_key:
                providers["gateway"] = GatewayProvider(
                    api_key=gateway_key,
                    models=config.get_gateway_models(),
                    base_url=config.get("gateway_base_url", GatewayProvider.DEFAULT_BASE_URL),
                    temperature=brain.temperature,
                    max_tokens=brain.max_tokens,
                )
            brain.provider = SmartProvider(
                providers,
                local_model=brain.model,
                cloud_model=config.get("openrouter_model", OpenRouterProvider.DEFAULT_MODEL),
                prefer_local=True,
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
