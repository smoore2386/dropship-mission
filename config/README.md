# OpenClaw Configuration

This directory contains reproducible configuration for the dropship-mission
openclaw setup.

---

## Shopify MCP Setup

The agents in this repo use the official **Shopify Dev MCP server** (`@shopify/dev-mcp`)
via [mcporter](http://mcporter.dev) to access Shopify's GraphQL APIs and documentation.

### One-time setup (run once per machine)

```bash
# 1. Install mcporter globally
npm install -g mcporter

# 2. Install the Shopify dev MCP server globally (faster than npx, no download per call)
npm install -g @shopify/dev-mcp

# 3. Add the Shopify MCP server to the system-level mcporter config
mcporter config add shopify-dev \
  --command "shopify-dev-mcp" \
  --description "Shopify Dev MCP - GraphQL schema, docs, app development" \
  --scope home

# 4. Verify it works
mcporter list
# → shopify-dev — Shopify Dev MCP ... (8 tools, ~0.7s)

# 5. Install and restart openclaw gateway (runs as launchd service — auto-starts on boot)
openclaw node install
openclaw gateway restart
```

The project-level config (`config/mcporter.json`) is checked into this repo and
is automatically picked up by mcporter when run from this directory.

---

## What `shopify-dev` provides

| Tool | Purpose |
|------|---------|
| `learn_shopify_api` | Start a session for a specific API, returns `conversationId` |
| `introspect_graphql_schema` | Query Admin, Storefront, Partner GraphQL schemas |
| `search_docs_chunks` | Semantic search across shopify.dev docs |
| `fetch_full_docs` | Retrieve full doc pages by path |
| `get_started_with_*` | Guided onboarding for specific Shopify APIs |

**APIs available:** `admin`, `storefront-graphql`, `partner`, `functions`, `payments-apps`

---

## Agent access

All four agents have Shopify MCP usage instructions in their workspace `TOOLS.md`:

| Agent | Workspace TOOLS.md | Focus |
|-------|--------------------|-------|
| Engineering ⚙️ | `~/.openclaw/workspace-engineering/TOOLS.md` | Full dev tooling, schema, app builds |
| CEO 👔 | `~/.openclaw/workspace-ceo/TOOLS.md` | Orders, revenue, KPI data |
| Sales 💰 | `~/.openclaw/workspace-sales/TOOLS.md` | Orders, customers, fulfillment, refunds |
| Marketing 📈 | `~/.openclaw/workspace-marketing-research/TOOLS.md` | Products, collections, promos |

---

## Shopify app credentials

Stored in `shopify/.env` (not committed). Required env vars:

```
SHOPIFY_API_KEY=<partner app client id>
SHOPIFY_API_SECRET=<partner app secret>
SCOPES=write_products
```

---

## OpenClaw auth note

The openclaw config uses two Anthropic profiles:
- `anthropic:default` — has had auth failures; currently on cooldown
- `anthropic:manual` — working profile; used as `lastGood`

If you see `HTTP 401 authentication_error`, the `anthropic:default` token is
invalid. Run `openclaw configure` and update it, or ensure `anthropic:manual`
is set as the active profile.
