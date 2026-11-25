---
name: contract-sync
description: Change the JoinPilot API contract safely by updating docs/contract.md, the backend Pydantic schemas, the web TypeScript types and the mock fixtures together in one commit. Use this for any new endpoint, any new or renamed field, any status or reason code change, or whenever frontend and backend data shapes need to match, even if the owner only mentions one side.
---

# Contract sync

Four places describe the API, and they must always agree:

1. `docs/contract.md`: the human-readable source of truth
2. `backend/joinpilot/api/schemas.py`: Pydantic request and response models
3. `web/src/types/api.ts`: TypeScript types the console uses
4. `shared/fixtures/*.json`: example responses used by the mock API and the web tests

## Steps

1. Get the owner's OK on the contract change before writing code: the endpoint, its fields and their types, and the error cases.
2. Update docs/contract.md first, and bump its version number at the top.
3. Update the Pydantic models, then the TypeScript types, so field names, types, optionality and enums match exactly.
4. Update or add fixtures for the new shapes.
5. Make sure `backend/tests/api/test_contract.py` validates every fixture against the Pydantic models, and add cases for new shapes.
6. Run the `verify` skill for both backend and web.
7. Commit all four places in the same commit with `commit-step`.

## Never
- Change one side and leave the other for later.
- Rename fields silently. Note breaking changes at the top of docs/contract.md.
