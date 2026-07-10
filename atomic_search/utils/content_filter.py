"""
Content filter for Atomic Search.

Provides content filtering and moderation.
"""

import re
import threading
from collections import defaultdict
from typing import Dict, List, Optional, Set


class ContentFilter:
    """Content filtering and moderation."""

    def __init__(self):
        self._profanity_list: Set[str] = set()
        self._spam_patterns: List[re.Pattern] = []
        self._blocked_keywords: Set[str] = set()
        self._link_patterns: List[re.Pattern] = []
        self._lock = threading.RLock()
        self._load_default_filters()

    def _load_default_filters(self):
        """Load default filter patterns."""
        # Common spam patterns
        spam_patterns = [
            r"click\s*here\s*now",
            r"limited\s*time\s*offer",
            r"act\s*fast",
            r"winner",
            r"congratulations",
            r"you\s*have\s*won",
            r"free\s*(?:money|iphone|gift)",
            r"make\s*\$?\d+\s*(?:per\s*day|fast)",
            r"work\s*from\s*home",
            r"earn\s*(?:\$\d+|passive)",
            r"buy\s*now\s*pay\s*later",
            r"risk\s*free",
            r"no\s*obligation",
            r"call\s*now",
            r"special\s*promotion",
        ]

        for pattern in spam_patterns:
            self._spam_patterns.append(re.compile(pattern, re.IGNORECASE))

        # Link patterns
        self._link_patterns = [
            re.compile(r"https?://[^\s]+", re.IGNORECASE),
            re.compile(r"www\.[^\s]+", re.IGNORECASE),
        ]

    def add_profanity(self, words: List[str]):
        """Add words to profanity filter."""
        with self._lock:
            self._profanity_list.update(w.lower() for w in words)

    def remove_profanity(self, words: List[str]):
        """Remove words from profanity filter."""
        with self._lock:
            self._profanity_list.difference_update(w.lower() for w in words)

    def add_blocked_keyword(self, keyword: str):
        """Add blocked keyword."""
        with self._lock:
            self._blocked_keywords.add(keyword.lower())

    def remove_blocked_keyword(self, keyword: str):
        """Remove blocked keyword."""
        with self._lock:
            self._blocked_keywords.discard(keyword.lower())

    def is_profanity(self, text: str) -> bool:
        """Check if text contains profanity."""
        text_lower = text.lower()
        words = set(re.findall(r"\w+", text_lower))
        return bool(words & self._profanity_list)

    def is_spam(self, text: str) -> bool:
        """Check if text matches spam patterns."""
        for pattern in self._spam_patterns:
            if pattern.search(text):
                return True
        return False

    def contains_blocked_keyword(self, text: str) -> bool:
        """Check if text contains blocked keywords."""
        text_lower = text.lower()
        for keyword in self._blocked_keywords:
            if keyword in text_lower:
                return True
        return False

    def filter_profanity(self, text: str, replacement: str = "***") -> str:
        """Replace profanity with replacement."""
        result = text
        words = re.findall(r"\w+", text)

        for word in words:
            if word.lower() in self._profanity_list:
                pattern = re.compile(re.escape(word), re.IGNORECASE)
                result = pattern.sub(replacement, result)

        return result

    def extract_links(self, text: str) -> List[str]:
        """Extract all links from text."""
        links = []
        for pattern in self._link_patterns:
            matches = pattern.findall(text)
            links.extend(matches)
        return links

    def remove_links(self, text: str) -> str:
        """Remove all links from text."""
        result = text
        for pattern in self._link_patterns:
            result = pattern.sub("[link removed]", result)
        return result

    def moderate(self, text: str) -> Dict:
        """Perform full content moderation."""
        return {
            "is_safe": not (
                self.is_profanity(text) or
                self.is_spam(text) or
                self.contains_blocked_keyword(text)
            ),
            "has_profanity": self.is_profanity(text),
            "is_spam": self.is_spam(text),
            "has_blocked_keyword": self.contains_blocked_keyword(text),
            "links": self.extract_links(text),
        }

    def safe_content(self, text: str) -> str:
        """Clean content for display."""
        result = text
        result = self.filter_profanity(result)
        return result


class SafeSearchFilter:
    """Safe search content filter."""

    def __init__(self, level: str = "moderate"):
        self.level = level
        self._categories = self._load_categories()

    def _load_categories(self) -> Dict[str, Set[str]]:
        """Load content categories."""
        return {
            "explicit": {
                "nsfw", "porn", "xxx", "adult", "nude", "naked",
                "explicit", "sexual", "erotic",
            },
            "violence": {
                "gore", "death", "kill", "murder", "violence",
                "blood", "weapon", "bomb", "terror",
            },
            "hate": {
                "hate", "racist", "sexist", "discrimination",
                "supremacy", "nazi", "kKK",
            },
            "dangerous": {
                "suicide", "self-harm", "anorexia", "bulimia",
                "drugs", "marijuana", "cocaine", "heroin",
            },
        }

    def set_level(self, level: str):
        """Set safe search level."""
        self.level = level

    def filter_query(self, query: str) -> str:
        """Filter search query."""
        if self.level == "off":
            return query

        query_lower = query.lower()
        words = set(re.findall(r"\w+", query_lower))

        for category, blocked in self._categories.items():
            if self.level == "strict":
                if words & blocked:
                    return "[filtered]"
            elif self.level == "moderate":
                if category in ["explicit", "dangerous"] and words & blocked:
                    return "[filtered]"

        return query

    def filter_results(self, results: List[Dict]) -> List[Dict]:
        """Filter search results."""
        if self.level == "off":
            return results

        filtered = []

        for result in results:
            title = result.get("title", "").lower()
            snippet = result.get("snippet", "").lower()
            content = f"{title} {snippet}"
            words = set(re.findall(r"\w+", content))

            should_filter = False

            if self.level == "strict":
                for blocked in self._categories.values():
                    if words & blocked:
                        should_filter = True
                        break
            elif self.level == "moderate":
                for category in ["explicit", "dangerous"]:
                    if words & self._categories[category]:
                        should_filter = True
                        break

            if not should_filter:
                filtered.append(result)

        return filtered


# Global filter instances
content_filter = ContentFilter()
safe_search_filter = SafeSearchFilter()
