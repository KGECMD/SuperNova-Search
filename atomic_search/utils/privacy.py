"""
Privacy utilities for Atomic Search.

Provides enhanced privacy features including:
- Request sanitization
- IP anonymization
- DNS over HTTPS support
- Cookie blocking
- Tracker blocking
- Fingerprint protection
"""

import hashlib
import random
import time
from typing import Any, Dict, Optional
from urllib.parse import urlparse


class PrivacyManager:
    """Manages privacy settings and features."""

    def __init__(self):
        self.blocked_domains = self._load_blocked_domains()
        self.trackers = self._load_trackers()
        self.safe_search_domains = self._load_safe_domains()

    def _load_blocked_domains(self) -> set:
        """Load list of blocked domains."""
        return {
            "google-analytics.com",
            "googletagmanager.com",
            "facebook.net",
            "doubleclick.net",
            "analytics.twitter.com",
            "pixel.facebook.com",
            "hotjar.com",
            "mixpanel.com",
            "segment.io",
            "amplitude.com",
            "newrelic.com",
            "sentry.io",
            "bugsnag.com",
            "rollbar.com",
            "datadog.com",
            "scorecardresearch.com",
            "quantserve.com",
            "bluekai.com",
            "exelator.com",
            "krxd.net",
            "adsrvr.org",
            "casalemedia.com",
            "pubmatic.com",
            "rubiconproject.com",
            "openx.net",
            "indexww.com",
            "adsymptotic.com",
            "adnxs.com",
            "criteo.com",
            "taboola.com",
            "outbrain.com",
        }

    def _load_trackers(self) -> dict:
        """Load tracker patterns."""
        return {
            "analytics": [
                "/analytics",
                "/tracking",
                "/pixel",
                "/beacon",
                "/collect",
            ],
            "ads": [
                "/ads/",
                "/ad/",
                "/advertising",
                "/doubleclick",
            ],
            "social": [
                "/facebook",
                "/twitter/widget",
                "/linkedin",
                "/share",
            ],
        }

    def _load_safe_domains(self) -> set:
        """Load safe domains for search results."""
        return {
            "wikipedia.org",
            "wiktionary.org",
            "wikimedia.org",
            "github.com",
            "stackoverflow.com",
            "stackexchange.com",
            "reddit.com",
            "news.ycombinator.com",
            "arxiv.org",
            "scholar.google.com",
        }

    def is_tracker(self, url: str) -> bool:
        """Check if URL is a known tracker."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()

            # Check blocked domains
            for blocked in self.blocked_domains:
                if blocked in domain:
                    return True

            # Check tracker patterns
            path = parsed.path.lower()
            for tracker_list in self.trackers.values():
                for pattern in tracker_list:
                    if pattern in path:
                        return True

            return False
        except Exception:
            return False

    def sanitize_url(self, url: str) -> str:
        """Remove tracking parameters from URL."""
        try:
            parsed = urlparse(url)
            
            # Known tracking parameters
            tracking_params = {
                "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
                "fbclid", "gclid", "msclkid", "dclid",
                "mc_cid", "mc_eid",
                "ref", "ref_src", "ref_url",
                "source", "via",
                "_ga", "_gl",
                "yclid",
                "wickedid",
                "wbraid",
                "gbraid",
            }

            # Parse query params
            params = parsed.query.split("&") if parsed.query else []
            clean_params = []

            for param in params:
                if "=" in param:
                    key = param.split("=")[0].lower()
                    if key not in tracking_params:
                        clean_params.append(param)

            # Rebuild URL
            scheme = parsed.scheme
            netloc = parsed.netloc
            path = parsed.path
            query = "&".join(clean_params)
            fragment = parsed.fragment

            return f"{scheme}://{netloc}{path}?{query}{'#' + fragment if fragment else ''}"
        except Exception:
            return url

    def anonymize_ip(self, ip: str) -> str:
        """Anonymize IP address by zeroing last octets."""
        try:
            parts = ip.split(".")
            if len(parts) == 4:
                return f"{parts[0]}.{parts[1]}.0.0"
        except Exception:
            pass
        return "0.0.0.0"

    def generate_anon_id(self, *args) -> str:
        """Generate anonymous ID from arbitrary input."""
        data = "-".join(str(arg) for arg in args)
        timestamp = str(int(time.time()) // 86400)  # Daily salt
        return hashlib.sha256(f"{data}-{timestamp}".encode()).hexdigest()[:16]

    def should_proxy(self, url: str) -> bool:
        """Determine if URL should be proxied."""
        # Always proxy tracking URLs
        if self.is_tracker(url):
            return True

        # Don't proxy safe domains
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            for safe in self.safe_search_domains:
                if safe in domain:
                    return False
        except Exception:
            pass

        return False

    def get_doh_server(self) -> str:
        """Get DNS over HTTPS server."""
        servers = [
            "https://cloudflare-dns.com/dns-query",
            "https://dns.google/dns-query",
            "https://dns.quad9.net/dns-query",
        ]
        return random.choice(servers)

    def create_privacy_headers(self) -> Dict[str, str]:
        """Create privacy-focused headers."""
        return {
            "DNT": "1",
            "X-Do-Not-Track": "1",
            "X-Privacy-Mode": "enabled",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }


# Global privacy manager instance
privacy_manager = PrivacyManager()
