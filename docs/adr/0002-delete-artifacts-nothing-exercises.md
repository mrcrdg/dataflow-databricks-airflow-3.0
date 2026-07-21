# 2. Delete artifacts that nothing exercises

- **Status:** accepted
- **Date:** 2026-07-21

## Context

This project has now produced the same failure three times:

| Artifact | What it claimed | Reality |
|---|---|---|
| `configs/pipeline.yaml` | `mode: incremental`, source `data/raw/posts.csv` | Path did not exist, source is XML, code did an overwrite |
| `README.md` | "Runs on Databricks, Airflow, or Kubernetes"; a file tree listing `common/io.py`, `common/logger.py`, `scripts/run_bronze_posts.py`, `requirements.txt` | None of those files existed |
| `Dockerfile` | A runnable container image | Missing `pyyaml`, wrong `PYTHONPATH` for a `src/` layout, unpinned deps over a base image that already had PySpark |

In every case the artifact was committed, looked plausible, and was wrong. In
every case nothing read it, ran it, or built it — so nothing could report the
drift. The code moved on; the artifact stayed where it was.

None of these were caught by careful reading. `pipeline.yaml` was caught by
wiring it to code that runs. The `README` and `Dockerfile` were caught by review
prompted specifically to look for inconsistency.

## Decision

**An artifact must be exercised by something automated, or it must be deleted.**

Applied here:

- `configs/pipeline.yaml` — now read by every job, and there is a test asserting
  the committed file is valid (`test_real_config_is_valid_and_complete`).
- `README.md` — rewritten to describe what exists. Not automatically verified,
  which is a known weakness; keeping it short and factual limits the surface.
- `Dockerfile` — **deleted.** It could not be built or tested in the development
  environment, so shipping it would mean publishing unverified code as working.
  Recorded in `ROADMAP.md`; it returns only alongside a CI job that builds the
  image and runs a pipeline in it.

Deletion is the default when an artifact cannot be exercised. Git preserves it,
so nothing is lost that cannot be recovered.

## Consequences

**Positive**

- Documentation and configuration that survives is documentation that is true.
- The repo stops making claims it cannot support — which is the same reason the
  "runs on Databricks, Airflow and Kubernetes" portability claim was cut.
- Reviewers can trust what they read, which is the entire value of a README.

**Negative**

- The project ships without a container image, which some readers will expect.
- `README.md` is still verified only by human attention, so it remains the most
  likely thing to drift next. Mitigated by keeping it factual and linking to
  `ROADMAP.md` rather than restating scope in two places.

## Notes

The general form: **a claim nothing checks is a claim that will eventually be
false.** Config, docs, and build files are code with a slower feedback loop, and
the absence of a failure is not evidence that they work — it is usually evidence
that nothing tried.
