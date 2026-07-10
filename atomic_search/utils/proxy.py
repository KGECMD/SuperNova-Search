"""
Proxy manager for Atomic Search.

Provides proxy rotation and routing.
"""

import random
import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class Proxy:
    """Proxy configuration."""
    url: str
    protocol: str
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    enabled: bool = True
    last_used: float = 0
    failures: int = 0
    success_count: int = 0
    avg_response_time: float = 0


class ProxyPool:
    """Pool of proxy servers."""

    def __init__(self):
        self._proxies: Dict[str, Proxy] = {}
        self._lock = threading.RLock()
        self._response_times: Dict[str, List[float]] = {}

    def add_proxy(self, proxy: Proxy):
        """Add a proxy to the pool."""
        with self._lock:
            self._proxies[proxy.url] = proxy

    def remove_proxy(self, url: str):
        """Remove a proxy from the pool."""
        with self._lock:
            if url in self._proxies:
                del self._proxies[url]

    def get_proxy(self, strategy: str = "round_robin") -> Optional[Proxy]:
        """Get a proxy using the specified strategy."""
        with self._lock:
            enabled = [p for p in self._proxies.values() if p.enabled]

            if not enabled:
                return None

            if strategy == "random":
                return random.choice(enabled)

            elif strategy == "least_used":
                return min(enabled, key=lambda p: p.last_used)

            elif strategy == "best_performance":
                return min(enabled, key=lambda p: p.avg_response_time)

            elif strategy == "round_robin":
                # Sort by last used
                sorted_proxies = sorted(enabled, key=lambda p: p.last_used)
                return sorted_proxies[0] if sorted_proxies else None

            elif strategy == "failover":
                # Prefer proxies with fewer failures
                min_failures = min(p.failures for p in enabled)
                candidates = [p for p in enabled if p.failures == min_failures]
                return random.choice(candidates) if candidates else None

            return None

    def record_success(self, url: str, response_time: float):
        """Record successful proxy usage."""
        with self._lock:
            proxy = self._proxies.get(url)
            if not proxy:
                return

            proxy.last_used = time.time()
            proxy.success_count += 1

            # Update average response time
            if url not in self._response_times:
                self._response_times[url] = []

            self._response_times[url].append(response_time)

            # Keep last 10 response times
            if len(self._response_times[url]) > 10:
                self._response_times[url] = self._response_times[url][-10:]

            proxy.avg_response_time = sum(self._response_times[url]) / len(self._response_times[url])

            # Reset failures on success
            proxy.failures = 0

    def record_failure(self, url: str):
        """Record proxy failure."""
        with self._lock:
            proxy = self._proxies.get(url)
            if not proxy:
                return

            proxy.failures += 1

            # Disable after 5 consecutive failures
            if proxy.failures >= 5:
                proxy.enabled = False

    def enable_proxy(self, url: str):
        """Enable a proxy."""
        with self._lock:
            proxy = self._proxies.get(url)
            if proxy:
                proxy.enabled = True
                proxy.failures = 0

    def disable_proxy(self, url: str):
        """Disable a proxy."""
        with self._lock:
            proxy = self._proxies.get(url)
            if proxy:
                proxy.enabled = False

    def get_stats(self) -> List[Dict]:
        """Get proxy statistics."""
        with self._lock:
            return [
                {
                    "url": p.url,
                    "enabled": p.enabled,
                    "failures": p.failures,
                    "success_count": p.success_count,
                    "avg_response_time": round(p.avg_response_time, 2),
                    "last_used": p.last_used,
                    "success_rate": (
                        p.success_count / (p.success_count + p.failures) * 100
                        if (p.success_count + p.failures) > 0 else 0
                    ),
                }
                for p in self._proxies.values()
            ]

    def health_check(self, timeout: float = 5.0) -> Dict[str, bool]:
        """Perform health check on all proxies."""
        import httpx

        results = {}

        with self._lock:
            proxies = list(self._proxies.values())

        for proxy in proxies:
            try:
                proxies_dict = {
                    proxy.protocol: f"http://{proxy.url}"
                }

                response = httpx.get(
                    "https://httpbin.org/ip",
                    proxies=proxies_dict,
                    timeout=timeout
                )

                results[proxy.url] = response.status_code == 200

                if response.status_code == 200:
                    self.record_success(proxy.url, timeout)
                else:
                    self.record_failure(proxy.url)

            except Exception:
                results[proxy.url] = False
                self.record_failure(proxy.url)

        return results


class TorManager:
    """Manages Tor proxy connections."""

    def __init__(self, control_port: int = 9051, socks_port: int = 9050):
        self.control_port = control_port
        self.socks_port = socks_port
        self._enabled = False

    def get_tor_proxy(self) -> Dict[str, str]:
        """Get Tor proxy configuration."""
        return {
            "http": f"socks5://127.0.0.1:{self.socks_port}",
            "https": f"socks5://127.0.0.1:{self.socks_port}",
        }

    def new_identity(self) -> bool:
        """Request new Tor identity."""
        try:
            import stem
            from stem.control import Controller

            with Controller.from_port(port=self.control_port) as controller:
                controller.authenticate()
                controller.signal(stem.Signal.NEWNYM)
                return True
        except Exception:
            return False

    def is_connected(self) -> bool:
        """Check if Tor is connected."""
        try:
            import httpx
            response = httpx.get(
                "https://check.torproject.org/api/ip",
                proxies=self.get_tor_proxy(),
                timeout=10
            )
            return response.status_code == 200
        except Exception:
            return False


# Global proxy pool
proxy_pool = ProxyPool()
tor_manager = TorManager()
