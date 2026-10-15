"""fridge-assistant over real Streamable HTTP: the MCP Lambda's app served locally by uvicorn.

Local only (127.0.0.1); Converse is stubbed.
"""

import logging
import socket
import threading
import time

import pytest
import uvicorn

from fridgesense import assistant
from fridgesense.handlers import mcp as mcp_handler
from tests.api_helpers import link_account
from tests.mcp_helpers import put_item

pytestmark = pytest.mark.anyio
KEY = "0123456789abcdef" * 4  # looks like a real mcp_key


@pytest.fixture
def anyio_backend():
    return "asyncio"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def mcp_base(aws):
    """Base URL of the MCP app at /mcp/k1 on a local port."""
    link_account()
    port = free_port()
    config = uvicorn.Config(
        mcp_handler.build_app(f"/mcp/{KEY}"), host="127.0.0.1", port=port, log_level="warning"
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        assert time.monotonic() < deadline, "uvicorn did not start"
        time.sleep(0.02)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(5)


async def test_do_i_have_milk_over_http(mcp_base, converse_stub):
    put_item("milk", 1)
    converse_stub.answer("tool_use_find_milk.json", "end_turn_milk.json")
    result = await assistant.run(
        "Do I have milk?", server=f"{mcp_base}/mcp/{KEY}", bedrock=converse_stub.client
    )
    assert result.answer == "Yes, you have 1 milk, added 2 minutes ago."
    assert result.tools == ["find_item"]
    tools = converse_stub.requests[0]["toolConfig"]["tools"]
    assert len(tools) == 6
    data = converse_stub.requests[1]["messages"][-1]["content"][0]["toolResult"]["content"][0]
    assert data["json"]["in_fridge"] is True


async def test_wrong_key_is_mcp_error(mcp_base, converse_stub):
    result = await assistant.run(
        "Do I have milk?", server=f"{mcp_base}/mcp/wrong", bedrock=converse_stub.client
    )
    assert result.reason == "mcp_error"
    assert converse_stub.requests == []


async def test_key_never_logged(mcp_base, converse_stub, caplog):
    """The MCP URL holds the key: no logger (ours or the HTTP client's) may write it."""
    caplog.set_level(logging.INFO)  # what the API Lambda sets on the root logger
    put_item("milk", 1)
    converse_stub.answer("tool_use_find_milk.json", "end_turn_milk.json")
    await assistant.run(
        "Do I have milk?", server=f"{mcp_base}/mcp/{KEY}", bedrock=converse_stub.client
    )
    assert caplog.records, "nothing was logged at all"
    assert KEY not in caplog.text
