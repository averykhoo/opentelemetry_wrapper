---
type: Decision
id: DEC-89
title: A decorated class spans only the members defined in its own body, not inherited ones
decision_status: PROVISIONAL
actor: owner
tasks: [OTW-6, OTW-16]
tags: [api]
decided: 2026-10-19
session: 2026-10-19a
body_sha: sha256:04ef4937d54f2c4329e1432c9b2ac8ce92126b0923e9e55043760321d89a5b2b
---

Owner, 2026-10-19 (session 2026-10-19a). The session asked (multiple choice): "OTW-6 (classes) is built and reviewed. One design call is yours. The plan says that when a decorated class inherits methods, the base's functions get copied into the subclass, as v0 did. Review showed that this breaks method lookup under multiple inheritance (fixed by an extra descriptor that walks the MRO on every access), changes inspect.signature for DI frameworks (patched), puts spans on library bases' internals (pydantic BaseModel, Enum), and makes `@dataclass` above `@otel` on a dataclass subclass crash. How should inherited methods work?" The owner chose, verbatim:

> Own body only (Recommended)

whose option read: "Only the members defined in the class's own body get spans. Decorate a base yourself to span its methods. This is simpler, adds no per-access cost and has no MRO or signature or dataclass hazards. It's a change from v0, so it goes in the Upgrading guide."

This replaces OTW-6's plan line "Inherited methods: wrap the base's function into the subclass's `__dict__`."
