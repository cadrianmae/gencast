"""Shared pytest fixtures."""

from unittest.mock import MagicMock

import pytest

from gencast.cost import CostMeter


@pytest.fixture
def cost_meter():
    return CostMeter()


@pytest.fixture
def mock_llm_outline_response():
    """Build a mock LLMResponse-like object that returns a valid Outline JSON."""
    def _make(json_str: str = '{"segments":[{"name":"A","description":"d","size":"short"},{"name":"B","description":"d","size":"medium"},{"name":"C","description":"d","size":"long"},{"name":"D","description":"d","size":"medium"},{"name":"E","description":"d","size":"short"}]}'):
        resp = MagicMock()
        resp.content = json_str
        resp.tokens_in = 5000
        resp.tokens_out = 600
        resp.cache_reads_in = 0
        resp.cache_writes_in = 0
        resp.usd = 0.005
        return resp
    return _make
