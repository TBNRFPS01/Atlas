from pathlib import Path

from services.plugin_manager import PluginManager

_PLUGIN_SOURCE = (
    "from services.plugin_manager import Plugin\n"
    "class HelloPlugin(Plugin):\n"
    "    name = 'hello'\n"
    "    version = '1.0.0'\n"
    "    def startup(self) -> None:\n"
    "        self.started = True\n"
)


def test_plugin_manager_discovers_and_hooks(tmp_path: Path) -> None:
    (tmp_path / "hello.py").write_text(_PLUGIN_SOURCE, encoding="utf-8")

    manager = PluginManager(folder=str(tmp_path))
    assert manager.discover() == ["hello"]

    plugin = manager.get("hello")
    assert plugin is not None
    assert getattr(plugin, "started", False) is True

    manager.stop_all()
    assert manager.list_plugins() == []


def test_plugin_manager_empty_folder(tmp_path: Path) -> None:
    manager = PluginManager(folder=str(tmp_path))
    assert manager.discover() == []
    assert manager.list_plugins() == []


def test_plugin_manager_skips_init_files(tmp_path: Path) -> None:
    (tmp_path / "__init__.py").write_text("", encoding="utf-8")
    manager = PluginManager(folder=str(tmp_path))
    assert manager.discover() == []


def test_legacy_plugin_loader_delegates(tmp_path: Path) -> None:
    from core.plugins import PluginLoader

    (tmp_path / "hello.py").write_text(_PLUGIN_SOURCE, encoding="utf-8")
    loader = PluginLoader(folder=str(tmp_path))
    assert loader.load() == ["hello"]