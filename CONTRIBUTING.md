# Contributing

Contributions are welcome.

Please preserve the core design:

- decentralized task ownership;
- one task / one agent / one branch / one worktree;
- shared durable coordination state;
- advisory claims rather than broad file locks;
- serialized integration;
- candidate integration before advancing the target;
- intent-aware conflict resolution;
- staging-derived operational integration targets.

Before submitting changes to the helper, run:

```bash
python scripts/test_cwa.py
```
