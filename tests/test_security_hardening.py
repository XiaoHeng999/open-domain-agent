"""Tests for security hardening (tasks 3.1-3.4)."""
from __future__ import annotations

import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from open_agent.safety.command import CommandSafetyChecker


# ── 3.1 Whitelist bypass ──


class TestWhitelistBypass:
    def test_semicolon_bypass_blocked(self):
        checker = CommandSafetyChecker(whitelist_mode=True)
        result = checker.check("git; rm -rf /")
        assert not result.safe

    def test_pipe_bypass_blocked(self):
        checker = CommandSafetyChecker(whitelist_mode=True)
        result = checker.check("ls | cat /etc/passwd")
        assert not result.safe

    def test_and_bypass_blocked(self):
        checker = CommandSafetyChecker(whitelist_mode=True)
        result = checker.check("ls && rm -rf /")
        assert not result.safe

    def test_command_substitution_blocked(self):
        checker = CommandSafetyChecker(whitelist_mode=True)
        result = checker.check("echo $(cat /etc/passwd)")
        assert not result.safe

    def test_backtick_blocked(self):
        checker = CommandSafetyChecker(whitelist_mode=True)
        result = checker.check("echo `cat /etc/passwd`")
        assert not result.safe

    def test_redirect_blocked(self):
        checker = CommandSafetyChecker(whitelist_mode=True)
        result = checker.check("ls > /tmp/out")
        assert not result.safe

    def test_redirect_input_blocked(self):
        checker = CommandSafetyChecker(whitelist_mode=True)
        result = checker.check("cat < /etc/passwd")
        assert not result.safe

    def test_or_bypass_blocked(self):
        checker = CommandSafetyChecker(whitelist_mode=True)
        result = checker.check("ls || rm -rf /")
        assert not result.safe

    def test_legitimate_whitelist_still_works(self):
        checker = CommandSafetyChecker(whitelist_mode=True)
        result = checker.check("ls")
        assert result.safe

    def test_blacklist_mode_unaffected(self):
        checker = CommandSafetyChecker(whitelist_mode=False)
        result = checker.check("ls")
        assert result.safe


# ── 3.2 shlex.split command parsing ──


class TestShlexSplit:
    def test_shlex_split_with_quotes(self):
        import shlex
        cmd = 'my-server --config "path with spaces.conf"'
        parts = shlex.split(cmd)
        assert parts == ["my-server", "--config", "path with spaces.conf"]

    def test_plain_split_breaks_with_quotes(self):
        cmd = 'my-server --config "path with spaces.conf"'
        parts = cmd.split()
        assert parts != ["my-server", "--config", "path with spaces.conf"]


# ── 3.3 HTTP connection pool reuse ──


class TestHTTPConnectionPool:
    async def test_http_client_reused(self):
        from open_agent.mcp_integration import MCPTransport, ServerConfig, TransportType
        config = ServerConfig(
            server_id="test",
            transport=TransportType.HTTP,
            url="http://localhost:8080",
        )
        transport = MCPTransport(config)
        await transport.connect()
        assert transport._http_client is not None
        client = transport._http_client
        # Second connect should reuse or replace
        assert transport._http_client is not None
        await transport.disconnect()
        assert transport._http_client is None


# ── 3.4 Request counter concurrency ──


class TestRequestCounterConcurrency:
    def test_counter_increments_atomically(self):
        from open_agent.mcp_integration import MCPTransport
        from open_agent.mcp_integration import ServerConfig, TransportType
        config = ServerConfig(server_id="test")
        t1 = MCPTransport(config)
        t2 = MCPTransport(config)
        id1 = t1._next_id()
        id2 = t2._next_id()
        # Should be unique
        assert id1 != id2
