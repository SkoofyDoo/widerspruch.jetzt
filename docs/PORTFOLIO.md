# Portfolio case study — WIDERSPRUCH.JETZT

## EN (short)

**Problem.** Jobcenter decisions in Germany are hard to understand. Deadlines are short; formal objections (Widerspruch) must be structured correctly. Many people lose money because of form/process failures, not substance.

**Constraints.** The product must not invent law, must avoid overconfident legal conclusions, and must stay clearly positioned as **document assistance** (not legal advice).

**Approach.**
1. Ingest official statute text (SGB II / SGB X).
2. Embed with multilingual E5 into Chroma.
3. Retrieve grounded chunks for each case.
4. Generate a formal letter with a local LLM (Ollama).
5. Run a multi-stage post-process: style enforcement, citation allowlist, claim softening, domain topic guards.
6. Ship a real product surface: UI, preview/paywall (Stripe), beta magic links, PDF export.

**Trade-offs.**
- JSON file store for credits → simple demo, not multi-instance safe.
- Local LLM → privacy-friendly, heavier local setup.
- Modular monolith → clear domains without microservice ops cost.

**What this demonstrates.** Applied RAG, FastAPI backend design, payment webhooks, safety-aware LLM product thinking, end-to-end ownership.

**Next upgrades.** Postgres billing store, structure-aware chunking (§ metadata), hybrid retrieval, offline eval harness for letter quality.

---

## RU (кратко)

**Проблема.** Решения Jobcenter сложны, сроки короткие. Формальный Widerspruch легко сделать неправильно.

**Ограничения.** Нельзя выдумывать закон, нельзя писать «уверенные» правовые выводы, нельзя позиционировать сервис как Rechtsberatung.

**Решение.**
1. Парсинг официальных текстов SGB II/X.
2. Эмбеддинги E5 → Chroma.
3. Retrieval по кейсу.
4. Генерация письма через Ollama.
5. Пост-обработка: Amtsstil, allowlist цитат, смягчение claim’ов, topic-guards.
6. Продукт: UI, preview/paywall, beta-ссылки, PDF.

**Компромиссы.** JSON-хранилище кредитов (просто, но не multi-instance); локальная LLM (приватность, сложнее setup); modular monolith вместо микросервисов.

**Что показывает проект.** Applied RAG, backend на FastAPI, Stripe webhooks, safety-мышление вокруг LLM, end-to-end ownership.

**Что улучшил бы дальше.** Postgres, §-aware chunking, hybrid retrieval, eval harness качества писем.
