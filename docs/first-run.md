# First Run Guide

This guide walks through what happens the **first time you run Archive Brain**, what to expect, and how to tell whether things are working as intended.

If you’re comfortable with Docker but new to this project, this is the right place to start.

---

## ⏳ What Happens on First Startup

On the first run, Archive Brain does more work than on subsequent starts. Specifically, it will:

1. Pull required LLM models (several GB total)
2. Initialize the PostgreSQL database and vector indexes
3. Start scanning configured source directories
4. Begin ingesting, segmenting, and enriching documents

Depending on your hardware and dataset size, this can take anywhere from a few minutes to over an hour.

During this time:
- CPU usage may spike
- Memory usage may increase
- Fans may spin up
- The UI may appear empty or partially populated

All of this is expected behavior.

---

## 🔍 Monitoring Progress

The background pipeline runs inside the **worker** container.

To follow progress in real time:

```bash
docker compose logs -f worker
````

To check model downloads and LLM readiness:

```bash
docker compose logs ollama
```

If models are still downloading, the pipeline will wait and retry automatically.

---

## 📂 Source Directories

Archive Brain only processes files from directories explicitly listed in:

```
config/config.yaml
```

### First-Run Recommendation

For your first run:

* Start with a **small test folder**
* Avoid pointing at your entire home directory
* Confirm ingestion works as expected before expanding scope

This makes it easier to understand the system and avoids long initial processing times.

---

## 🧠 Resource Usage & Performance

Recommended minimums:

* **16 GB RAM**
* SSD storage
* GPU optional (but helpful)

If you experience out-of-memory issues:

* Switch to a smaller LLM model
* Use an external Ollama instance with GPU acceleration
* Reduce the number or size of source directories

The system is designed to favor correctness and clarity over speed.

---

## 🔄 Restarting & Experimenting Safely

It is safe to:

* Restart containers
* Re-run the pipeline
* Change models and retry enrichment
* Adjust source directories

Most pipeline steps are **idempotent**, meaning unchanged files are skipped automatically.

To fully reset the system and start fresh:

```bash
docker compose down -v
docker compose up -d --build
```

This removes all stored data and embeddings.

---

## ❓ Common First-Run Questions

### “Nothing is showing up in the UI”

* Documents may still be processing
* Check worker logs for activity

### “It seems slow”

* First runs are the slowest
* Subsequent runs reuse metadata and embeddings

### “Images aren’t being enriched”

Verify the vision model is installed:

```bash
docker compose exec ollama ollama list
```

Pull it manually if needed:

```bash
docker compose exec ollama ollama pull llava
```

---

## 🧭 How to Know You’re Done

You’ll know the first run has stabilized when:

* Worker logs quiet down
* Search results start appearing consistently
* CPU and memory usage drop back to idle levels

From here, Archive Brain behaves incrementally — only new or changed files are processed.

---

## Next Steps

* Explore semantic search in the UI
* Try natural-language questions
* Gradually expand your source directories
* Read the architecture overview if you want to customize or extend the system

This system rewards curiosity and iteration. Take it slow, observe the logs, and adjust as you go.


