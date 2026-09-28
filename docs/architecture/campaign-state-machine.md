# Campaign state machine

## Document responsibility

This document owns the P05 campaign-draft lifecycle. It depends on the domain glossary and `CampaignState`/`CampaignTrigger` in `marketing_ai.domain.advertising`. Application use cases must use this table before recording an external dispatch; a provider timeout or ambiguous result must enter `RECONCILIATION_REQUIRED` rather than claim publication.

| Current state | Trigger | Next state | Meaning |
|---|---|---|---|
| `DRAFT` | `VALIDATE` | `VALIDATED` | Deterministic validation completed successfully. |
| `VALIDATED` | `REQUEST_APPROVAL` | `PENDING_APPROVAL` | The exact canonical payload is awaiting human authorization. |
| `PENDING_APPROVAL` | `APPROVE` | `APPROVED` | A valid human approval was granted. |
| `PENDING_APPROVAL` | `REJECT` | `REJECTED` | The requested action was rejected. |
| `APPROVED` | `START_EXECUTION` | `EXECUTING` | A durable, approved mutation intent is ready for dispatch. |
| `EXECUTING` | `CONFIRM_PUBLISHED` | `PUBLISHED` | The remote outcome is known to have published. |
| `EXECUTING` | `MARK_FAILED` | `FAILED` | The remote outcome is known to have failed without an ambiguous effect. |
| `EXECUTING` | `REQUIRE_RECONCILIATION` | `RECONCILIATION_REQUIRED` | Dispatch may have had an effect but cannot be proven. |
| `RECONCILIATION_REQUIRED` | `RECONCILE_PUBLISHED` | `PUBLISHED` | Read-based reconciliation established publication. |
| `RECONCILIATION_REQUIRED` | `RECONCILE_FAILED` | `FAILED` | Read-based reconciliation established failure. |
| `REJECTED`, `PUBLISHED`, `FAILED` | — | Terminal | No campaign transition is allowed. |

Any state/trigger pair absent from this table is invalid and raises the stable `INVALID_STATE_TRANSITION` domain error. Campaign drafts are immutable; the only public lifecycle change is `transition_campaign`, which returns the next version.
