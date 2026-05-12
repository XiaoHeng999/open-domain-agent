"""SSRF protection — block private IPs, private domains, cloud metadata endpoints."""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from open_agent.safety.command import SafetyCheckResult

# Private IP ranges
_PRIVATE_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local (cloud metadata)
    ipaddress.ip_network("::1/128"),  # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),  # IPv6 private
]

# Cloud metadata endpoints
_BLOCKED_HOSTS = {
    "169.254.169.254",
    "metadata.google.internal",
    "metadata.azure.com",
}

# Private domain patterns
_PRIVATE_DOMAIN_PATTERNS = [
    re.compile(r"\.local$", re.IGNORECASE),
    re.compile(r"\.internal$", re.IGNORECASE),
    re.compile(r"^localhost$", re.IGNORECASE),
]


class SSRFProtector:
    """Validate URLs against SSRF attacks — private IPs, domains, cloud metadata."""

    def check_url(self, url: str) -> SafetyCheckResult:
        """Check if a URL is safe from SSRF perspective."""
        try:
            parsed = urlparse(url)
            hostname = parsed.hostname
        except Exception:
            return SafetyCheckResult(safe=False, reason="Invalid URL", risk_level="blocked")

        if not hostname:
            return SafetyCheckResult(safe=False, reason="No hostname in URL", risk_level="blocked")

        # Check blocked hosts
        if hostname.lower() in _BLOCKED_HOSTS:
            return SafetyCheckResult(
                safe=False, reason=f"Cloud metadata endpoint blocked: {hostname}",
                risk_level="blocked",
            )

        # Check private domain patterns
        for pattern in _PRIVATE_DOMAIN_PATTERNS:
            if pattern.search(hostname):
                return SafetyCheckResult(
                    safe=False, reason=f"Private domain blocked: {hostname}",
                    risk_level="blocked",
                )

        # Check if hostname resolves to private IP
        ip_result = self._check_hostname_ip(hostname)
        if not ip_result.safe:
            return ip_result

        return SafetyCheckResult(safe=True, risk_level="safe")

    def check_ip(self, ip_str: str) -> SafetyCheckResult:
        """Check if an IP address is in a private/blocked range."""
        try:
            addr = ipaddress.ip_address(ip_str)
        except ValueError:
            return SafetyCheckResult(safe=False, reason=f"Invalid IP: {ip_str}", risk_level="blocked")

        for network in _PRIVATE_NETWORKS:
            if addr in network:
                return SafetyCheckResult(
                    safe=False,
                    reason=f"Private/blocked IP range: {network}",
                    risk_level="blocked",
                )

        return SafetyCheckResult(safe=True, risk_level="safe")

    def _check_hostname_ip(self, hostname: str) -> SafetyCheckResult:
        """Check if hostname is a literal IP in a private range."""
        try:
            addr = ipaddress.ip_address(hostname)
            return self.check_ip(str(addr))
        except ValueError:
            pass  # Not a literal IP, OK for now (DNS resolution check deferred)
        return SafetyCheckResult(safe=True, risk_level="safe")

    def check_resolved_ip(self, ip_str: str, original_hostname: str) -> SafetyCheckResult:
        """DNS rebinding defense — check resolved IP after DNS lookup."""
        result = self.check_ip(ip_str)
        if not result.safe:
            return SafetyCheckResult(
                safe=False,
                reason=f"DNS rebinding detected: {original_hostname} resolved to private IP {ip_str}",
                risk_level="blocked",
            )
        return SafetyCheckResult(safe=True, risk_level="safe")
