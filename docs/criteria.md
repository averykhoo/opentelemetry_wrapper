# Criteria

LIVING. The definition of correct (FRAMEWORK §3.3). One row per criterion; ids are `AC-n`, never reused
or renumbered. `status` is `planned`, `tested` or `retired`: a criterion moves to `tested` only
when a test claims it and that test has been seen to fail with the behaviour broken.

**How a test claims a criterion.** In a pytest repo, mark the test
`@pytest.mark.criterion("AC-n")` and register the marker in the pytest config
(`markers = ["criterion(id): the AC-n criterion in docs/criteria.md that this test claims"]`).
Elsewhere, put `criterion: AC-n` in a comment on the line above the test. Either way, the trace
check by hand is: every `tested` row has at least one claiming test, and every claimed id has a
row here.

| Id | Criterion | Story | Status | Claimed by |
|---|---|---|---|---|
