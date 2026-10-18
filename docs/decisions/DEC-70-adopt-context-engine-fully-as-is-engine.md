---
type: Decision
id: DEC-70
title: 'Adopt context-engine fully, as is: engine defaults, automatic commits, a full migration of the v1 plan, an OTW board with a v1 epic'
actor: owner
decision_status: BUILT
tags: [process]
decided: 2026-10-18
session: 2026-10-18a
body_sha: sha256:d108dd913c20ed01e9eb274d20258eea0f4e9904f59b499ac0b314a7a5887dbe
---

Owner, 2026-10-18, session 2026-10-18a (the first message of the conversation):

"I have a repo in GitHub called context-engine. I want to adopt that in this repo, go pull that into scratch and figure out how to do the migration"

The agent cloned it, trialled `init` on a throwaway clone, and proposed a plan with open points (timing, auto-commit, task prefix, hook or plugin, whether to import PLAN.md as decisions, the engine install). Owner, in reply:

"Do an extra check to ensure everything is migrated and normalized to the new schemas and conventions 

Also migrate any history or archived stuff

Commit automatically is fine, adopt the engine defaults and use it's override in Claude md, we're adopting it fully as is

Try to do a full migration if it's not too much effort, rewriting everything to match if needed

Okay to OT or otw and consider creating an epic or parent task for v1 that lists what's needed to be done for v1

Also create a context-engine-feedback.md and add a note to put any AAR in there, note down frictions or wasted token consumption etc, possible problems or improvements in the workflows, simplifications that might help, etc

Yup I'll look at the charter and decisions after you're done

Okay to auto commit whenever it says to

Okay to keep or at least archive plan but do migrate it as well

Okay to install whatever"
