# M4: MCPMark external-state validation

Date: 2026-08-12

## Outcome

MCPMark now has an opt-in `external-state` backend while
`legacy-docker` remains the default. The backend prepares a unique writable
database/search slot for every task and can mount historical media from the
pristine baseline read-only. Containers use unique names and Docker-assigned
localhost ports.

The cleanup path is ownership checked and idempotent. The evaluator now runs
cleanup in `finally`, including when agent execution or verification raises.

## Local integration evidence

The real Shopping Admin slim runtime and its exported pristine baseline were
started through `PlaywrightStateManager`, not through a hand-written Docker
smoke command.

```text
backend: external-state
runtime image: ai-01.my.harbor.shopeemobile.com/ai-infra/shopping-admin-final-0719:2.0.0
baseline: /home/toc/SSE/mcpmark-data/baselines/shopping-admin-v1-pristine
snapshot driver: reflink
media mode: readonly
assigned URL: http://localhost:20000/admin
MySQL ready: yes
Magento ready: yes
HTTP ready: yes
setup result: true
cleanup result: true
container residue: none
state-directory residue: none
```

The first integration attempt also exercised failure rollback. Docker rejected
an invalid mount option before container creation; MCPMark removed the already
prepared state slot. The mount renderer was corrected to Docker's official
`readonly` syntax and the full test then passed.

## Automated checks

Four dependency-light test methods pass locally; together they verify:

- writable clones do not modify the pristine baseline;
- read-only media is emitted as a nested bind mount;
- duplicate run IDs never overwrite existing state;
- an incorrect cleanup token cannot delete state;
- service configuration preserves `legacy-docker` as the default.

The evaluator exception-cleanup test is included but is skipped in the minimal
system Python because the complete MCPMark runtime dependencies are not
installed there. It is intended to run in the project environment/CI.

## AEnv remote boundary and exact evidence

Admin and Postmill `2.0.0` artifacts are present in AEnv Hub, but remote Web
execution is not validated. A direct diagnostic request to the exact endpoint
used by official `shopee-aenvironment==0.1.96` returned:

```text
POST /env-service
HTTP 404
Content-Type: application/json; charset=utf-8
Body: null
```

The official client then attempts `APIResponse(**response.json())`; because the
JSON value is `null`, it reports the less useful Python error
`argument after ** must be a mapping, not NoneType`. No diagnostic service or
PVC was created.

Separately, `aenv instance create` timed out and the subsequent complete
official instance list contained no matching `shopping-admin-final-0719:2.0.0`
instance. Therefore Hub upload success must not be reported as remote runtime
success.

Even after `/env-service` is enabled, storage alone is insufficient: the
official configuration can create/mount a PVC, but no documented baseline
upload or per-task PVC snapshot/clone API has been identified. Production AEnv
acceptance requires both a working service endpoint and an approved baseline
population/reset mechanism.
