# Project conventions

- Use async-native Django request paths. `select_related` every relation an async path touches, and use `sync_to_async` only at a real sync boundary.
- Keep each controlled value in one enum under its Django app's `enums.py`; expose API enums in schemas so generated frontend types share the contract.
- Use Python 3.14's PEP 758 form for multiple exceptions: `except ValueError, TypeError:`.
- Add a database `CheckConstraint` for every Django choices field. Give migrations descriptive names that explain the behavior they change.
- Build list endpoints from batched maps; never issue one query per returned row.
- After a mutation, invalidate every client query that reads the data it changed.
- Keep comments to two lines or fewer and explain why the code needs to work that way.
- Update the relevant documentation in the same change as behavior.
- Keep source clue fields distinct from metadata added by this application.
- Treat attempts and grading decisions as the source of truth for recomputable proficiency.

