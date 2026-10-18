---
type: Story
id: STORY-11
title: Using the wrapper is simple, idiomatic, succinct and pretty
actor: owner
story_status: live
goals: [G-11]
via: intake, session 2026-10-18e
date: 2026-10-18
body_sha: sha256:f39e408645a4bc805289eb9be6d6e7f2f9fbe5068e8b053b5f6be52fd1b3cefc
---

Owner, 2026-10-18e (DEC-73), agreeing to add this goal: *"And I agree with your proposal adding the purpose, the simple idiomatic succint pretty goals, sensible defaults, and yes only commit the cleaned version"*.

The goal is the owner's own, from their v0 talk (27 May 2024; summary in `docs/evidence/v0-talk-deck-2026-10-18.md`), slide 17, "Design principles", verbatim:

- Unsurprising
  - Simple, idiomatic, succinct, and pretty

and the speaker notes to slide 16, "Following the documentation is painful", verbatim:

- Quite a bit of work is needed to manually instrument your code using the official OTEL libraries
- And it's also ugly; this contravenes PEP 20 "The Zen of Python", line 1: "Beautiful is better than ugly."
- Also, to export logs you need to import some protected/internal things from the OTEL library, which will make your linter complain
