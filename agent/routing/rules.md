# Routing Rules — Human-readable version of taxonomy.yml
# AI reads this when taxonomy.yml match is ambiguous
# TODO: Customize these rules for your project's executors and risk levels

## Priority Order (when task spans multiple domains)
1. Security concern present → always smart-model regardless of other factors
2. Task touches core data schema or auth → smart-model
3. Task touches ≤ 3 files AND no business logic → fast-model
4. Tests only → fast-model or local-script
5. Default → smart-model

## Override Triggers
- Developer adds `override_executor: [model]` to task frontmatter → use that model
- Task has `risk: critical` → escalate to smart-model regardless of other rules
- Task is in lessons.md with routing correction → follow lessons.md correction

## Ambiguity Resolution
When uncertain between two executors:
- Prefer cheaper option for output quality risk < medium
- Prefer more capable option for output quality risk ≥ medium
