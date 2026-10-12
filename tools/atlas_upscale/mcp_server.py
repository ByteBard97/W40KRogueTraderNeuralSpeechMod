#!/usr/bin/env python3
"""MCP server for the Rogue Trader game bridge (stdio). Forwards tool calls to the AtlasUpscale mod's HTTP listener."""
import json
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP, Image

sys.path.insert(0, str(Path(__file__).parent))
import bridge  # noqa: E402

mcp = FastMCP("rogue-trader-game")


def _call(command, **args):
    """bridge.call exits the process when the game is unreachable; turn that into a tool error instead."""
    try:
        return bridge.call(command, **args)
    except SystemExit as exit_:
        raise RuntimeError(str(exit_)) from None


def _text(reply):
    if reply.get("path"):
        reply["linuxPath"] = bridge.to_linux(reply["path"])
    if reply.get("files"):
        reply["linuxFiles"] = [bridge.to_linux(p) for p in reply["files"].split("|") if p]
    return json.dumps(reply, indent=2)


@mcp.tool()
def game_state() -> str:
    """Texture set, quality, mip limit, anti-aliasing, screen size, doll camera, zoom and pan of the running game."""
    return _text(_call("state"))


@mcp.tool()
def game_screenshot(name: str = "shot", doll_only: bool = False, show_label: bool = False) -> list:
    """Lossless screenshot of the game. doll_only captures just the character viewer render. Returns the image and its file path."""
    reply = _call("shot", name=name, label=int(show_label), doll=int(doll_only))
    if not reply.get("ok"):
        return [_text(reply)]
    path = bridge.to_linux(reply["path"])
    return [_text(reply), Image(path=path)]


@mcp.tool()
def game_texture_set(name: str = "") -> str:
    """Switch the character texture set by name (e.g. 'plain resize', 'topaz_recover', 'probe_stripes') and wait for the rebuild. Empty name lists the sets."""
    return _text(_call("texture_set", name=name or None))


@mcp.tool()
def game_dump_atlas() -> str:
    """F9 atlas dump: rebuild characters and save the Idira atlas before and after DXT compression. Returns the PNG paths."""
    return _text(_call("dump_atlas"))


@mcp.tool()
def game_zoom(mode: str = "", value: float = -1.0) -> str:
    """Character viewer zoom: mode 'min' (farthest through the character with the mod's extended range), 'max' or 'reset', or value 0..1 (1 = default view, ~0.5 = close-up). Empty reads the current value."""
    return _text(_call("zoom", mode=mode or None, value=None if value < 0 else value))


@mcp.tool()
def game_pan(x: float = 0.0, y: float = 0.0, reset: bool = False) -> str:
    """Character viewer pan offset in units of camera distance, or reset=True."""
    return _text(_call("pan", reset=1 if reset else None, x=None if reset else x, y=None if reset else y))


@mcp.tool()
def game_antialiasing(mode: str = "") -> str:
    """Set the game's anti-aliasing to 'off', 'smaa' or 'taa'. Empty reads the current mode."""
    return _text(_call("aa", mode=mode or None))


@mcp.tool()
def game_ui_list(filter: str = "") -> str:
    """List the active, clickable UI elements (path, label text, screen position). Optional text/path filter."""
    reply = _call("ui_list", filter=filter or None)
    items = reply.pop("items", "")
    return _text(reply) + "\n" + items


@mcp.tool()
def game_ui_click(match: str, index: int = -1) -> str:
    """Click an active UI button whose label or path contains `match`. If several match, pass index from game_ui_list."""
    return _text(_call("ui_click", match=match, index=index if index >= 0 else None))


@mcp.tool()
def game_timescale(value: float = -1.0) -> str:
    """Freeze (0) or resume (1) game time. Freeze before screenshots to compare one pose; always resume afterwards. Negative just reads it."""
    return _text(_call("timescale", value=None if value < 0 else value))


@mcp.tool()
def game_wait(frames: int = 30) -> str:
    """Wait for a number of rendered frames."""
    return _text(_call("wait", frames=frames))


if __name__ == "__main__":
    mcp.run()
