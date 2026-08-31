from __future__ import annotations

import os
import sys
import threading

from config.manager import ConfigManager
from core.brain import Brain
from core.events import EventBus
from core.execution import ExecutionPipeline
from core.router import Router
from core.natural_router import install as install_natural_routing
from core.smart_provider import SmartProvider
from core.openrouter import OpenRouterProvider
from core.providers import LocalProvider, GatewayProvider
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


def install_smart_provider(brain: Brain, config: ConfigManager) -> None:
    """Attach task-aware provider routing to the shared Brain instance."""
    providers: dict[str, object] = {}
    local = LocalProvider(
        base_url=brain.endpoint,
        api_key=brain.api_key,
        model=brain.model,
        temperature=brain.temperature,
        max_tokens=brain.max_tokens,
    )
    providers["local"] = local

    openrouter_key = config.get("openrouter_api_key", "") or os.getenv("OPENROUTER_API_KEY", "")
    if config.get("openrouter_enabled", False) and openrouter_key:
        providers["openrouter"] = OpenRouterProvider(
            api_key=openrouter_key,
            model=config.get("openrouter_model", OpenRouterProvider.DEFAULT_MODEL),
            models=config.get_openrouter_models(),
            base_url=config.get("openrouter_base_url", OpenRouterProvider.DEFAULT_BASE_URL),
            temperature=brain.temperature,
            max_tokens=brain.max_tokens,
            site_url=config.get("openrouter_site_url", ""),
            app_name=config.get("openrouter_app_name", "ATLAS"),
        )

    gateway_key = config.get("gateway_api_key", "")
    if config.get("gateway_enabled", False) and gateway_key:
        providers["gateway"] = GatewayProvider(
            api_key=gateway_key,
            models=config.get_gateway_models(),
            base_url=config.get("gateway_base_url", GatewayProvider.DEFAULT_BASE_URL),
            temperature=brain.temperature,
            max_tokens=brain.max_tokens,
        )

    primary_name = config.get("primary_provider", "local")
    fallback_name = config.get("fallback_provider", "none")
    primary = providers.get(primary_name)
    fallback = providers.get(fallback_name) if fallback_name != "none" else None
    if primary is None:
        primary = providers["local"]
    if fallback is primary:
        fallback = None

    if primary_name != "local" or fallback is not None or config.get("openrouter_enabled") or config.get("gateway_enabled"):
        if fallback is not None:
            from core.providers import MultiProvider
            brain.provider = MultiProvider(primary=primary, fallback=fallback)
        else:
            brain.provider = primary


def install_execution_pipeline(router: Router, config: ConfigManager) -> None:
    """Attach the single execution pipeline to the existing router."""
    router._execution = ExecutionPipeline(
        max_retries=int(config.get("execution_max_retries", 1)),
        dry_run=bool(config.get("dry_run", False)),
    )
    original = router._timed_tool_call

    def pipeline_call(tool_name: str, action: str, fn) -> str:
        execution = router._execution.run(tool_name, action, fn, signature=f"{tool_name}:{action}")
        router._call_log.append({
            "tool": tool_name, "action": action, "ok": execution.ok,
            "attempts": execution.attempts, "verified": execution.verified,
            "error": execution.error,
        })
        if len(router._call_log) > 200:
            router._call_log = router._call_log[-200:]
        router._record_trace(tool_name, action, "ok" if execution.ok else "error")
        return str(execution.result)

    router._original_timed_tool_call = original
    router._timed_tool_call = pipeline_call


def _mask_secret(value: str) -> str:
    if not value:
        return "not set"
    return value[:7] + "..." if len(value) > 10 else "set"


def configure_cli(config: ConfigManager) -> None:
    """Interactive first-run/configuration screen for AI providers."""
    while True:
        print("\n====================================")
        print("          ATLAS CONFIGURE")
        print("====================================")
        print("AI Providers")
        print(f"  1. OpenRouter   {'✓ configured' if config.get('openrouter_enabled') and (config.get('openrouter_api_key') or os.getenv('OPENROUTER_API_KEY')) else '○ not configured'}")
        print(f"  2. LM Studio    {'✓ configured' if config.get('endpoint') or os.getenv('LM_STUDIO_BASE_URL') else '○ default/unverified'}")
        print(f"  3. Gateway      {'✓ configured' if config.get('gateway_enabled') and config.get('gateway_api_key') else '○ disabled'}")
        print(f"\n  Primary:  {config.get('primary_provider', 'local')}")
        print(f"  Fallback: {config.get('fallback_provider', 'none')}")
        print("\nActions")
        print("  4. Configure OpenRouter")
        print("  5. Configure LM Studio")
        print("  6. Select primary/fallback")
        print("  7. Test configuration")
        print("  8. Save and restart")
        print("  Q. Cancel")
        choice = input("\nSelect: ").strip().lower()

        if choice == "1":
            key = input(f"OpenRouter API key [{_mask_secret(config.get('openrouter_api_key') or os.getenv('OPENROUTER_API_KEY', ''))}]: ").strip()
            if key:
                config.set("openrouter_api_key", key)
            config.set("openrouter_enabled", True)
            model = input(f"Model [{config.get('openrouter_model')}]: ").strip()
            if model:
                config.set("openrouter_model", model)
        elif choice == "2":
            endpoint = input(f"LM Studio endpoint [{config.get('endpoint', 'http://localhost:1234/v1')}]: ").strip()
            if endpoint:
                config.set("endpoint", endpoint)
            model = input(f"Local model [{config.get('model')}]: ").strip()
            if model:
                config.set("model", model)
        elif choice == "3":
            enabled = input("Enable gateway? [y/N]: ").strip().lower() == "y"
            config.set("gateway_enabled", enabled)
            if enabled:
                key = input("Gateway API key: ").strip()
                if key:
                    config.set("gateway_api_key", key)
                model = input(f"Gateway model [{config.get('gateway_model')}]: ").strip()
                if model:
                    config.set("gateway_model", model)
        elif choice == "4":
            key = input(f"OpenRouter API key [{_mask_secret(config.get('openrouter_api_key') or os.getenv('OPENROUTER_API_KEY', ''))}]: ").strip()
            if key:
                config.set("openrouter_api_key", key)
            config.set("openrouter_enabled", True)
            model = input(f"OpenRouter model [{config.get('openrouter_model')}]: ").strip()
            if model:
                config.set("openrouter_model", model)
        elif choice == "5":
            endpoint = input(f"LM Studio endpoint [{config.get('endpoint', 'http://localhost:1234/v1')}]: ").strip()
            if endpoint:
                config.set("endpoint", endpoint)
            model = input(f"LM Studio model [{config.get('model')}]: ").strip()
            if model:
                config.set("model", model)
        elif choice == "6":
            print("Providers: local, openrouter, gateway")
            primary = input(f"Primary [{config.get('primary_provider', 'local')}]: ").strip().lower()
            fallback = input(f"Fallback [local/openrouter/gateway/none] [{config.get('fallback_provider', 'openrouter')}]: ").strip().lower()
            if primary in {"local", "openrouter", "gateway"}:
                config.set("primary_provider", primary)
            if fallback in {"local", "openrouter", "gateway", "none"}:
                config.set("fallback_provider", fallback)
        elif choice == "7":
            issues = config.validate()
            if issues:
                print("\nConfiguration issues:")
                for issue in issues:
                    print(f"  ✗ {issue}")
            else:
                print("\n✓ Configuration is valid.")
                print(f"  Primary: {config.get('primary_provider')}")
                print(f"  Fallback: {config.get('fallback_provider')}")
                print(f"  OpenRouter key: {_mask_secret(config.get('openrouter_api_key') or os.getenv('OPENROUTER_API_KEY', ''))}")
                print("  Note: provider connectivity is tested when ATLAS starts.")
        elif choice == "8":
            issues = config.validate()
            if issues:
                print("\nCannot save yet:")
                for issue in issues:
                    print(f"  ✗ {issue}")
                continue
            config.save()
            print("\n✓ Configuration saved to config.json.")
            return
        elif choice == "q":
            return
        else:
            print("Unknown option.")


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
    provider = config.get("primary_provider", "local")
    fallback = config.get("fallback_provider", "none")
    print("AI Routing:")
    print(f"  ✓ Primary: {provider} | Fallback: {fallback}")
    print("====================================")


def main() -> None:
    config = ConfigManager()

    if "--configure" in sys.argv:
        configure_cli(config)
        return

    if "--ui" in sys.argv:
        from interface.gui import launch_ui
        from interface.run import build_backend
        backend = build_backend()
        launch_ui(router=backend["router"], brain=backend["brain"], memory=backend["memory"],
                  voice_controller=backend["voice_controller"], config_manager=backend["config_manager"],
                  tool_registry=backend["tool_registry"])
        return

    logger = get_logger("ATLAS")
    logger.info("ATLAS starting up (model=%s, primary=%s)", config.get("model"), config.get("primary_provider"))
    event_bus = EventBus()
    memory = FactStore()
    registry = ToolRegistry()
    registry.discover()
    brain = Brain(config_manager=config, history_limit=config.get("history_size"),
                   temperature=config.get("temperature"), max_tokens=config.get("max_tokens"))
    install_smart_provider(brain, config)
    state_store = AgentStateStore()
    goals = GoalManager(memory=memory)
    experiences = ExperienceStore(memory=memory)
    router = Router(brain=brain, memory=memory, registry=registry, config=config,
                    state_store=state_store, goals=goals, experiences=experiences)
    install_natural_routing(router)
    install_execution_pipeline(router, config)

    plugin_manager = PluginManager()
    plugin_manager.discover()
    briefing = DailyBriefingService(router=router, memory=memory, goal_manager=goals)
    briefing.start()

    goal_service: AutonomousGoalService | None = None
    if config.get("planner_enabled", True) and config.get("autonomy_enabled", False):
        goal_service = AutonomousGoalService(autonomy=router._autonomy,
            interval_seconds=config.get("autonomy_interval_seconds", 600.0),
            max_tasks=config.get("autonomy_max_tasks_per_cycle", 2), enabled=True)
        goal_service.start()
        print("Autonomy: ✓ Background goal service enabled")

    voice_controller: VoiceController | None = None
    voice_enabled = config.get("voice_enabled", False)
    if voice_enabled:
        try:
            voice_controller = VoiceController(router=router, enabled=voice_enabled,
                whisper_model=config.get("whisper_model"), tts_engine=config.get("tts_engine"),
                tts_voice=config.get("tts_voice"))
            voice_controller.start()
            voice_thread = threading.Thread(target=voice_controller.run_background, daemon=True)
            voice_thread.start()
            print("Voice: ✓ Voice assistant enabled")
        except Exception as e:
            print(f"Voice: Warning - Failed to start voice: {e}")
            print("Voice: Continuing in CLI mode.")
    else:
        voice_controller = VoiceController(router=router, enabled=False)

    router._voice_controller = voice_controller
    print_startup_screen(brain, registry, config)
    print("ATLAS is ready. Type /help, /configure, or 'exit' to quit.")

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
        if prompt.lower() in {"/configure", "/config", "--configure"}:
            configure_cli(config)
            print("ATLAS: Configuration saved. Restarting with the new provider setup...")
            os.execv(sys.executable, [sys.executable, *sys.argv])
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
