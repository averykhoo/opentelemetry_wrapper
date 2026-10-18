---
type: Decision
id: DEC-12
title: 'No Kubernetes API calls: labels and annotations from the Downward API (Q12)'
actor: owner
decided: 2026-10-18
session: 2026-10-18a
decision_status: PROVISIONAL
imported_from: docs/evidence/decision-log-import-2026-10-18.md
aliases: [Q-12]
body_sha: sha256:a4108e529e09d078486d87b5eeb4a5c258496f4f77eee8f8bdeb27a6924bed7f
tags: [resources]
tasks: [OTW-9]
---

- **Q12. The k8s API lookup** (pod labels/annotations, one HTTPS call at startup). *Verified 2026-10-18:* Falco's
  default stable ruleset has "Contact K8S API Server From Container" (any container connecting to the API server,
  minus a short image allowlist), and Elastic Security ships "Kubernetes Denied Service Account Request" (medium) for
  exactly the usual 403. CIS 5.1.5/5.1.6 recommend `automountServiceAccountToken: false`, so in hardened clusters
  there's no token at all. Nobody comparable reads the API from inside the application: the OTel Operator computes
  `service.*` in its admission webhook and injects Downward API env vars, `k8sattributes` runs in the Collector, and
  Datadog uses `fieldRef` labels or its admission controller (second review, from their docs and source). AWS's EKS
  detectors do call the API, but only when configured to. The alternative needs no API: a **Downward API volume**
  exposes the full `metadata.labels` / `metadata.annotations` maps as files (one `key="Go-quoted value"` per line,
  sorted, updated atomically), and single labels can be `fieldRef` env vars. *Suggested* (second review,
  medium-high confidence): **no API calls at all**, read labels/annotations from the volume (e.g.
  `OTEL_WRAPPER_PODINFO_DIR`, default `/etc/podinfo`) and ship the snippet in the README; an opt-in API lookup needs
  a Role + RoleBinding, the same manifest edit as adding the volume, for more risk. *Decided 2026-10-18:* no
  Kubernetes API calls; labels and annotations from the Downward API volume or `fieldRef` env vars (workstream 6).
  May be revisited as an explicit opt-in if a user asks.

*Imported at adoption (2026-10-18) from `PLAN.md` § Questions for later, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*
