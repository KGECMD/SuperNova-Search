"""
Plugin system for Atomic Search.

Provides extensibility through plugins.
"""

import importlib
import importlib.util
import json
import os
import sys
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type


@dataclass
class PluginInfo:
    """Plugin metadata."""
    name: str
    version: str
    description: str
    author: str
    enabled: bool = True
    config: Dict = field(default_factory=dict)


class Plugin(ABC):
    """Base plugin class."""

    @abstractmethod
    def on_load(self):
        """Called when plugin is loaded."""
        pass

    @abstractmethod
    def on_enable(self):
        """Called when plugin is enabled."""
        pass

    @abstractmethod
    def on_disable(self):
        """Called when plugin is disabled."""
        pass

    def get_info(self) -> PluginInfo:
        """Return plugin info."""
        return PluginInfo(
            name=self.__class__.__name__,
            version="1.0.0",
            description="",
            author="Unknown"
        )


class PluginHook:
    """Plugin hook definitions."""

    SEARCH_PRE = "search_pre"
    SEARCH_POST = "search_post"
    RESULTS_PRE = "results_pre"
    RESULTS_POST = "results_post"
    RENDER_PRE = "render_pre"
    RENDER_POST = "render_post"
    REQUEST_PRE = "request_pre"
    REQUEST_POST = "request_post"


class PluginManager:
    """Manages plugin lifecycle and hooks."""

    def __init__(self, plugin_dir: str = None):
        self.plugin_dir = plugin_dir or "/tmp/atomic_search_plugins"
        self._plugins: Dict[str, Plugin] = {}
        self._hooks: Dict[str, List[Callable]] = {}
        self._lock = threading.RLock()
        self._ensure_plugin_dir()

    def _ensure_plugin_dir(self):
        """Ensure plugin directory exists."""
        Path(self.plugin_dir).mkdir(parents=True, exist_ok=True)

    def load_plugin(self, name: str) -> bool:
        """Load a plugin by name."""
        with self._lock:
            if name in self._plugins:
                return True

            try:
                # Try to import plugin
                spec = importlib.util.find_spec(f"atomic_search_plugins.{name}")
                if spec:
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[f"atomic_search_plugins.{name}"] = module
                    spec.loader.exec_module(module)
                else:
                    # Try to load from file
                    plugin_path = Path(self.plugin_dir) / f"{name}.py"
                    if plugin_path.exists():
                        spec = importlib.util.spec_from_file_location(name, plugin_path)
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                    else:
                        return False

                # Find plugin class
                for item in dir(module):
                    obj = getattr(module, item)
                    if isinstance(obj, type) and issubclass(obj, Plugin) and obj != Plugin:
                        plugin = obj()
                        plugin.on_load()
                        self._plugins[name] = plugin
                        return True

                return False

            except Exception:
                return False

    def unload_plugin(self, name: str) -> bool:
        """Unload a plugin."""
        with self._lock:
            if name not in self._plugins:
                return False

            try:
                plugin = self._plugins[name]
                plugin.on_disable()
                del self._plugins[name]
                return True
            except Exception:
                return False

    def enable_plugin(self, name: str) -> bool:
        """Enable a plugin."""
        with self._lock:
            if name not in self._plugins:
                return False

            try:
                self._plugins[name].on_enable()
                info = self._plugins[name].get_info()
                info.enabled = True
                return True
            except Exception:
                return False

    def disable_plugin(self, name: str) -> bool:
        """Disable a plugin."""
        with self._lock:
            if name not in self._plugins:
                return False

            try:
                self._plugins[name].on_disable()
                info = self._plugins[name].get_info()
                info.enabled = False
                return True
            except Exception:
                return False

    def register_hook(self, hook: str, callback: Callable):
        """Register a hook callback."""
        with self._lock:
            if hook not in self._hooks:
                self._hooks[hook] = []
            self._hooks[hook].append(callback)

    def unregister_hook(self, hook: str, callback: Callable):
        """Unregister a hook callback."""
        with self._lock:
            if hook in self._hooks:
                self._hooks[hook] = [c for c in self._hooks[hook] if c != callback]

    def call_hooks(self, hook: str, *args, **kwargs) -> List[Any]:
        """Call all hooks for an event."""
        results = []

        with self._lock:
            callbacks = self._hooks.get(hook, []).copy()

        for callback in callbacks:
            try:
                result = callback(*args, **kwargs)
                results.append(result)
            except Exception:
                pass

        return results

    def get_plugin(self, name: str) -> Optional[Plugin]:
        """Get a loaded plugin."""
        return self._plugins.get(name)

    def list_plugins(self) -> List[PluginInfo]:
        """List all loaded plugins."""
        return [
            plugin.get_info()
            for plugin in self._plugins.values()
        ]

    def save_config(self, config_path: str):
        """Save plugin configuration."""
        config = {
            "enabled": [
                name for name, plugin in self._plugins.items()
                if plugin.get_info().enabled
            ],
            "config": {
                name: plugin.get_info().config
                for name, plugin in self._plugins.items()
            }
        }

        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)

    def load_config(self, config_path: str):
        """Load plugin configuration."""
        if not os.path.exists(config_path):
            return

        with open(config_path) as f:
            config = json.load(f)

        for name in config.get("enabled", []):
            self.load_plugin(name)
            self.enable_plugin(name)

        for name, plugin_config in config.get("config", {}).items():
            if name in self._plugins:
                info = self._plugins[name].get_info()
                info.config = plugin_config


# Global plugin manager
plugin_manager = PluginManager()
