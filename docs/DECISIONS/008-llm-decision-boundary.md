# 008 — LLM orchestration and explanation boundary

- **Decision:** LLMs may orchestrate validated reads and explain reports, but
  cannot determine or override market prices, structural state, deterministic
  strategy results, risk approval or execution authorization. [U-PRODUCT-001]
- **Reason:** Market evidence and causal decisions must remain inspectable and
  deterministic. Generated wording cannot fill an unimplemented strategy or
  acquire permissions from external development tools.
- **Consequence:** Prefer deterministic report → deterministic/template
  explanation → optional LLM enhancement. Useful public-market output must work
  without an LLM. Enforce tool/access/risk boundaries in application services;
  keep authoritative fields separate from generated wording and exclude secrets
  from model inputs/logs. No LLM integration or Python behavior changes at Ch.0.
- **Date:** 2026-09-12.
