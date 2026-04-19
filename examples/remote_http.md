# Running the server over HTTP

By default the server talks stdio (for Claude Desktop). For remote use — Claude
Code's `--mcp-config`, n8n, or any other HTTP MCP client — run it as a web
service.

## Start it

```bash
linkedin-mcp --transport streamable-http --host 0.0.0.0 --port 8765
```

The MCP endpoint is `http://<host>:8765/mcp`.

## Behind a reverse proxy

Always terminate TLS and add auth at the proxy layer — this server does not
authenticate callers. Example with Caddy:

```
linkedin.example.com {
  basicauth {
    you JDJhJDE0JDdxc... # htpasswd-style
  }
  reverse_proxy 127.0.0.1:8765
}
```

## Claude Code config

```bash
claude mcp add linkedin https://linkedin.example.com/mcp
```
