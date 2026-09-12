# Handoff — Ch.0 product-scope closure

Updated: 2026-09-12. Keep these fields reusable for later safe handoffs.
Current user instructions prevail; do not infer implementation permission
from prepared worktrees or this document.

## LAST AGENT

Codex. Formal Ch.0 documentation/Git closure; no product implementation.

## CURRENT BRANCH / CHECKPOINT

Integration: `strategy-v0.1` in `C:/Users/Serdar Arif/Desktop/Agent Trading`.
Base: `364a3a7d50024520065e74a9c9e9da899d4e3897`.
Closure checkpoint: the commit containing this document with message
`chore: freeze hackathon product scope and ch0 plan`.
Its exact hash is in Git and the final closure report; this document does not
embed its own future commit hash. Preserve foundation-v0.1 and
shadow-foundation-v0.2; create no additional tag, remote or push.

## LAST COMPLETED WORK

- Preserved the deterministic/MTF/real-OKX CLI SHADOW foundation.
- Recorded approved open-source/self-hosted copilot direction and new rubric.
- Created [product-mvp-v0.1](specs/product-mvp-v0.1.md), scope P0/P0.5/P1/P2,
  shared Web/Mini App architecture, user journeys, safety and demo acceptance.
- Added ADRs 006–009 for self-hosting, actual runtime MCP, LLM boundary and
  Telegram optionality; updated shared memory/source records.
- Kept the committed DD Market Structure draft, ADRs 001–005 and research history.
- Checkpoint commit/test/worktree operations follow this document freeze;
  inspect their actual final state in Git and the closure report.

## FILES CHANGED / UNCOMMITTED WORK

Ten authored/updated Ch.0 documentation files and one incoming research
document belong to this checkpoint:

| File | Change |
|---|---|
| AGENTS.md | Updated shared product constitution, scope and responsibilities |
| docs/PROJECT_STATE.md | Updated actual/target state, history and closure gates |
| docs/HANDOFF.md | Updated this handoff |
| docs/NEXT_TASK.md | Future Ch.1 contract/runtime-MCP work; explicit approval gate |
| docs/SOURCE_REGISTRY.md | Added confirmed product/rubric provenance, preserved old sources |
| docs/specs/product-mvp-v0.1.md | New approved MVP scope |
| docs/DECISIONS/006-open-source-self-hosting-first.md | New ADR |
| docs/DECISIONS/007-runtime-atk-mcp.md | New ADR |
| docs/DECISIONS/008-llm-decision-boundary.md | New ADR |
| docs/DECISIONS/009-telegram-as-interface.md | New ADR |
| docs/research/agentic-market-intelligence-ecosystem-2026-09-12.md | Incoming ecosystem research from the parallel Kaynak Tarama task; preserved without editing |

All fifteen files from the previous shared-memory task were committed at
364a3a7. Earlier claims that they were worktree-only/uncommitted are superseded.
This closure commits its ten docs plus the completed incoming research;
use `git status` to verify the final
clean state rather than carrying forward historical uncommitted-file lists.
CLAUDE.md/CODEX.md still delegate to AGENTS.md and remain unchanged.
No Python, test, dependency, runtime configuration or strategy-spec file changes.
The incoming research is reference material [R-COPILOT-001], not product-scope
approval, an installed dependency set or permission to invent trading rules.

## CURRENT TEST STATUS

Previous verified baseline: 36 existing tests passing, zero failures/errors.
Fresh Ch.0 closure verification on 2026-09-12: **36 tests passed, zero
failures/errors**, exit 0; the full existing suite was rerun before the commit.
Full command: `py -B -m unittest discover -s tests -v`.
Interpreter fallback and bytecode suppression are in PROJECT_STATE.
Passing infrastructure tests do not validate a strategy, product-runtime MCP,
UI or financial performance. The final closure report gives the fresh result.

## IMPORTANT DECISIONS

- Preserve core; open-source/self-hosted copilot, Telegram optional.
- Utility 30%, UX 30%, ATK MCP 20%, Reliability 10%, Innovation 10%.
- One shared React/Vite/TypeScript Web/Mini App; thin API-based Telegram bot.
- Actual product-runtime MCP is mandatory and not currently implemented;
  verify public ticker/4H/1H/15m candles/orderbook early in Ch.1.
- Useful template explanation without LLM. Optional LLM cannot determine/
  override prices, structure, strategy result, risk or execution authorization.
- P0.5 before final demo needs an approved, honest intelligence slice; placeholder
  relabeling is not completion.
- Premium/Discount remains context; EQ reaction/reclaim is not universally
  mandatory; preserve DD ordinary side blocks.
- READ-ONLY/SHADOW first; LIVE and full portfolio/advanced theories are outside MVP.
- One easy Compose start command is the target, not necessarily one container.

## UNRESOLVED / KNOWN LIMITS

No completed strategy. MarketStructureEngine N-1–N-7 remain open; no confirmed
Range material is registered. P0.5 algorithm and fixtures must be explicitly
approved before intelligence coding. No FastAPI, frontend, runtime MCP client,
SQLite, deployment files, position model, fill/PnL accounting or LIVE is built.
Existing CLI/OAuth evidence does not prove application-runtime MCP.
The shared API contract is a first Ch.1 deliverable, not already finalized here.

## WORKTREES / RESPONSIBILITY

After the clean documentation checkpoint commit, prepare these exact branches
from that checkpoint, leaving them clean and untouched:
- Codex/backend: `work/copilot-backend`,
  `C:/Users/Serdar Arif/Desktop/Agent Trading-backend`.
- Claude/UX: `work/copilot-ux`,
  `C:/Users/Serdar Arif/Desktop/Agent Trading-ux`.

These setup actions happen after this text is committed. Inspect
`git worktree list --porcelain`, branch HEADs and each checkout's status;
the final report records actual paths/hashes. If an existing branch/worktree is
found, inspect/report it instead of recreating/destroying it.

Codex owns backend/MCP/FastAPI/core/persistence/backend tests/Compose and shared
contract/root integration/memory. Claude owns frontend/Mini App/bot/interface
and frontend tests. Define/review shared API before parallel work.
One owner edits trading-intelligence core files at a time; do not share a
working directory. Merge/cherry-pick reviewed commits and verify the integration.

## DO NOT

Do not start Ch.1, install packages, implement features, modify Python behavior,
invent trading rules, bypass DD gates, relabel unavailable intelligence,
enable LIVE, expose secrets, create a tag/remote or push during this closure.
Do not edit either new worktree after checkout.

## NEXT

**Stop for user review of formal Ch.0 closure.**
Only after explicit approval: read AGENTS → PROJECT_STATE → HANDOFF → NEXT_TASK →
product spec; inspect Git/worktree status; define the shared API contract, then
prove actual runtime MCP → real public market data → normalized core input.
The frontend may proceed in parallel only after the contract is reviewed.
