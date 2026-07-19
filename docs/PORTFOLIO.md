# Portfolio case study — WIDERSPRUCH.JETZT

**Live demo:** https://sgb2-rag-production.up.railway.app/ui/  
**Health:** https://sgb2-rag-production.up.railway.app/health  
**Preview GIF:** [docs/assets/demo-preview.gif](assets/demo-preview.gif)

---

## EN (short)

**Problem.** Jobcenter decisions in Germany are hard to understand. Deadlines are short; formal objections (Widerspruch) must be structured correctly. Many people lose money because of form/process failures, not substance.

**Constraints.** The product must not invent law, must avoid overconfident legal conclusions, and must stay clearly positioned as **document assistance** (not legal advice).

**Approach.**
1. Ingest official statute text (SGB II / SGB X).
2. Embed with multilingual E5 into Chroma.
3. Retrieve grounded chunks for each case.
4. Generate a formal letter with an LLM (Ollama locally; HuggingFace on Railway).
5. Multi-stage post-process: style enforcement, citation allowlist, claim softening, domain topic guards.
6. Ship UI + preview/paywall (Stripe) + beta magic links + PDF; deploy with Docker on Railway using **remote HF embeddings** (no torch OOM on hobby RAM).

**Trade-offs.**
- JSON file store for credits → simple demo, not multi-instance safe.
- Remote LLM/embeddings → free public demo possible; free-tier rate limits & cold starts.
- Modular monolith → clear domains without microservice ops cost.

**What this demonstrates.** Applied RAG, FastAPI backend design, payment webhooks, safety-aware LLM product thinking, production deploy under resource constraints, end-to-end ownership.

**Next upgrades.** Postgres billing store, structure-aware chunking (§ metadata), hybrid retrieval, offline eval harness for letter quality.

---

## RU (кратко)

**Live demo:** https://sgb2-rag-production.up.railway.app/ui/

**Проблема.** Решения Jobcenter сложны, сроки короткие. Формальный Widerspruch легко сделать неправильно.

**Ограничения.** Нельзя выдумывать закон, нельзя писать «уверенные» правовые выводы, нельзя позиционировать сервис как Rechtsberatung.

**Решение.**
1. Парсинг официальных текстов SGB II/X.
2. Эмбеддинги E5 → Chroma.
3. Retrieval по кейсу.
4. Генерация письма (Ollama локально / HuggingFace в облаке).
5. Пост-обработка: Amtsstil, allowlist цитат, смягчение claim’ов, topic-guards.
6. UI + paywall + Docker → Railway; remote HF embeddings, чтобы demo жил на ~1GB RAM.

**Компромиссы.** JSON-кредиты; free-tier HF; modular monolith.

**Что показывает проект.** Applied RAG, FastAPI, safety вокруг LLM, деплой под ограничениями, end-to-end ownership.
