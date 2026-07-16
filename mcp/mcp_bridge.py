#!/usr/bin/env python3
"""MCP bridge CLI buat Kai (text-based tool dispatch).

Stateless: tiap invocation buka koneksi ke server MCP, lakuin operasi, tutup.
Transport otomatis: config punya "url" -> streamable-HTTP (remote, mis. windows-agent
via tailnet). Config punya "command" -> stdio (local subprocess).

Dipanggil Kai lewat shell:
  python3 mcp_bridge.py list-servers
  python3 mcp_bridge.py list-tools <server>
  python3 mcp_bridge.py call <server> <tool> '<json-args>'
"""
import sys
import os
import json
import asyncio
from contextlib import asynccontextmanager

BASE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(BASE, "servers.json")

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client


def _load_cfg():
    with open(CONFIG, encoding="utf-8") as f:
        return json.load(f)


def _server_cfg(name):
    cfg = _load_cfg()
    if name not in cfg:
        raise SystemExit(f"ERROR: server '{name}' ga ada di servers.json. Tersedia: {list(cfg)}")
    return cfg[name]


@asynccontextmanager
async def _open_session(name):
    s = _server_cfg(name)
    if s.get("url"):
        headers = s.get("headers", {})
        async with streamablehttp_client(s["url"], headers=headers) as (r, w, _):
            async with ClientSession(r, w) as session:
                await session.initialize()
                yield session
    else:
        env = dict(os.environ)
        env.update(s.get("env", {}))
        params = StdioServerParameters(command=s["command"], args=s.get("args", []), env=env)
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w) as session:
                await session.initialize()
                yield session


async def _list_tools(name):
    async with _open_session(name) as session:
        res = await session.list_tools()
        return [{"name": t.name, "description": (t.description or "")[:200]} for t in res.tools]


async def _call(name, tool, args):
    async with _open_session(name) as session:
        res = await session.call_tool(tool, args)
        parts = []
        for c in res.content:
            if getattr(c, "type", None) == "text":
                parts.append(c.text)
            else:
                parts.append(str(c))
        return "\n".join(parts) if parts else "(no output)"


def main():
    if len(sys.argv) < 2:
        print("usage: mcp_bridge.py [list-servers|list-tools <server>|call <server> <tool> <json-args>]")
        return
    cmd = sys.argv[1]
    if cmd == "list-servers":
        cfg = _load_cfg()
        for k, v in cfg.items():
            kind = "http" if v.get("url") else "stdio"
            print(f"- {k} [{kind}]: {v.get('description','')}")
    elif cmd == "list-tools":
        name = sys.argv[2]
        print(json.dumps(asyncio.run(_list_tools(name)), ensure_ascii=False, indent=2))
    elif cmd == "call":
        name, tool = sys.argv[2], sys.argv[3]
        args = json.loads(sys.argv[4]) if len(sys.argv) > 4 else {}
        _lim = int(os.environ.get("MCP_MAX", "2000000"))
        print(asyncio.run(_call(name, tool, args))[:_lim])
    else:
        print(f"unknown cmd: {cmd}")


if __name__ == "__main__":
    main()
