# Groww Generic Algo ID Correction Design

**Date:** 2026-07-13
**Status:** Approved direction; implementation pending

## Summary

Market Sentinel currently treats `GROWW_ALGO_ID` as both a regulatory Algo ID and the Groww SDK `order_reference_id`. These values have different purposes. This change separates them:

- Groww or the exchange remains responsible for generic Algo ID handling in the selected low-throughput retail API mode.
- The operator must explicitly confirm that Groww has enabled or confirmed that handling for the live account.
- Market Sentinel generates a unique tracking reference for every order and sends only that value as `order_reference_id`.

This correction does not enable live trading by itself. Static-IP allowlisting, API subscription, fresh credentials, account allowlisting, protected-order requirements, market-hours checks, risk approval, and all other live readiness gates remain mandatory.

## Problem

The current implementation asks for `GROWW_ALGO_ID` and passes it to the Groww SDK as `order_reference_id`. This conflates two distinct concepts:

- A regulatory or exchange Algo ID identifies an approved algorithm or the generic low-throughput API category handled by the broker and exchange.
- Groww's `order_reference_id` is a user-supplied client tracking reference. Groww documents it as 8 to 20 alphanumeric characters with no more than two hyphens.

The conflation can produce invalid SDK payloads, incorrectly report an account as compliant, and invite operators to paste a value that Market Sentinel should not collect.

## Selected Operating Mode

This design supports only low-throughput retail API trading where Groww and the exchange apply the appropriate generic Algo ID handling. The application does not collect, infer, register, or submit an exchange-approved strategy Algo ID.

Registered or high-throughput algorithmic trading is out of scope. Supporting that mode later requires a separate design based on the broker's then-current API contract and exchange registration process.

## Goals

- Remove the false equivalence between regulatory Algo ID and SDK order reference.
- Require an explicit operator confirmation that Groww has confirmed generic Algo ID handling for the account.
- Generate a valid, unique client tracking reference for every Groww order.
- Fail closed when the new confirmation is absent.
- Preserve all existing risk, compliance, credential, account, and live-mode gates.
- Provide a clear migration path without accepting the legacy value as evidence of readiness.

## Non-Goals

- Do not register an algorithm with Groww, NSE, or SEBI.
- Do not discover or retrieve broker credentials, account identifiers, or regulatory identifiers from a browser session.
- Do not derive a regulatory Algo ID from an API key, strategy name, account number, or order reference.
- Do not enable high-throughput or registered-algorithm execution.
- Do not place a real-money order while verifying this change.
- Do not relax static-IP, subscription, account allowlist, risk, protected-order, or explicit live-confirmation requirements.

## Configuration Contract

### New setting

Add a boolean setting named `groww_generic_algo_id_confirmed`, populated from:

`GROWW_GENERIC_ALGO_ID_CONFIRMED=true`

The default is `false`. Only an explicit true value satisfies the gate.

The setting means the operator has independently confirmed with Groww that the account's selected low-throughput retail API use receives the required broker or exchange generic Algo ID handling. It is an attestation, not an ID value.

### Removed setting

Remove `groww_algo_id` from active settings and remove `GROWW_ALGO_ID` from templates and setup instructions.

For safety, a legacy `GROWW_ALGO_ID` environment value is ignored. It must not populate the new setting, satisfy readiness, or be sent to Groww. Migration requires the operator to answer the new confirmation prompt explicitly.

## Readiness And Compliance

Groww live readiness continues to require all existing gates. The Algo ID-related checks change as follows:

- `INDIA_ALGO_COMPLIANCE_VERIFIED=true` remains required as the broader regulatory attestation.
- `GROWW_GENERIC_ALGO_ID_CONFIRMED=true` becomes a separate required account and broker handling attestation.
- Missing confirmation is reported as `GROWW_GENERIC_ALGO_ID_CONFIRMED` in preflight output.
- A populated legacy `GROWW_ALGO_ID` does not change readiness.
- Readiness remains false when either attestation is absent.

No code path may directly set or persist `ready_to_trade=true`. Readiness remains a derived result of all current configuration, credential, connectivity, account, compliance, and risk checks.

## Order Reference Generation

Market Sentinel generates a new `order_reference_id` immediately before each Groww order submission.

The format is:

`MS` followed by 16 lowercase hexadecimal characters

This produces an 18-character alphanumeric value that fits Groww's documented 8 to 20 character constraint and does not require hyphens. A cryptographically strong random UUID source supplies the hexadecimal portion. A new value is generated once for each logical order submission. If a transport retry is ever added around the same SDK request, it must reuse that reference rather than create a second apparent order.

The reference contains no credentials, account identifiers, symbols, strategy names, timestamps, or regulatory identifiers. It is used only for client-side and broker-side order correlation.

The implementation should isolate generation in a small helper or injectable factory. Tests can inject deterministic values without weakening production randomness.

## Groww Adapter Mapping

The Groww adapter must:

1. Generate a client order reference for the submission.
2. Pass that generated value to the SDK's `order_reference_id` field.
3. Never pass `GROWW_ALGO_ID`, `GROWW_GENERIC_ALGO_ID_CONFIRMED`, or any compliance attestation as an SDK order field.
4. Include the generated reference in sanitized audit metadata where order correlation is already recorded.

The adapter must reject a generated value that does not satisfy the documented format before calling the SDK. This defensive validation protects future alternate generators and tests.

## Setup Wizard

The local live-session wizard removes the free-text Groww Algo ID prompt. It asks a yes/no question equivalent to:

`Has Groww confirmed generic Algo ID handling for this low-throughput API account? [y/N]`

The default is no. The wizard must not infer or auto-affirm the answer from an existing strategy, API subscription, credential, browser session, or legacy environment variable.

An affirmative answer sets `GROWW_GENERIC_ALGO_ID_CONFIRMED=true` only for the locally managed session configuration. A negative or blank answer leaves the gate false and allows the wizard to continue to a blocked preflight result with a clear remediation message.

## Migration And Documentation

Update all operator-facing surfaces that currently request or describe `GROWW_ALGO_ID`:

- environment templates
- broker plugin setup skill and scripts
- local operating guide and live setup runbook
- preflight and status output
- dashboard fixtures or labels that display the missing gate
- tests and example configuration

Migration text must tell existing operators that the old value was a client-reference misuse, is ignored after this change, and should be removed from local configuration. Documentation must not instruct users to paste credentials or broker secrets into chat, source control, screenshots, or command history.

## Failure Behavior

The system fails closed in these cases:

- the generic Algo ID confirmation is absent or false;
- broader India algo compliance is absent or false;
- a legacy Algo ID is present without the new confirmation;
- reference generation returns an invalid value;
- the Groww SDK rejects the generated reference;
- any existing credential, static-IP, subscription, account, market, risk, or protected-order gate fails.

An invalid generated reference blocks the submission before the SDK call and emits a sanitized error and audit event. It must not fall back to a constant, strategy name, account identifier, or legacy environment value.

## Test-Driven Implementation

Implementation starts with failing tests for:

- settings parsing defaults the new confirmation to false;
- explicit true parses successfully;
- live readiness reports `GROWW_GENERIC_ALGO_ID_CONFIRMED` when missing;
- a legacy `GROWW_ALGO_ID` cannot satisfy readiness;
- broader India compliance and the new confirmation are independently required;
- generated references are 18-character alphanumeric values beginning with `MS`;
- repeated generation produces distinct references;
- the Groww SDK receives the generated value as `order_reference_id`;
- no Algo ID or confirmation value is sent as an SDK order field;
- an invalid injected reference blocks before the SDK is called;
- the wizard records only an explicit affirmative answer;
- documentation and templates no longer present `GROWW_ALGO_ID` as an active setting.

After each failing test is observed, implement the smallest production change that makes it pass. Existing broker readiness, compliance, execution, dashboard, and plugin tests must remain green.

## Verification

Verification is read-only with respect to broker accounts and real funds:

- run the focused settings, compliance, broker adapter, and wizard tests;
- run the full Python test suite;
- run dashboard build and relevant UI tests if fixtures or labels change;
- run a local preflight using placeholder or deliberately incomplete credentials and confirm it remains blocked;
- inspect the sanitized SDK mock payload to confirm reference mapping;
- search the repository for remaining active `GROWW_ALGO_ID` dependencies.

No live order is submitted as part of implementation or verification.

## Rollout And Rollback

Rollout is a configuration migration. Operators remove `GROWW_ALGO_ID`, rerun the local wizard, explicitly answer the generic-handling question, and then run preflight. All other readiness failures remain visible and must be resolved independently.

Rollback means reverting the software change, not restoring the old value as a valid order reference. If the new broker-handling assumption proves incorrect, Groww live readiness must remain disabled until a revised broker contract and design are approved.

## Security And Audit Notes

- The confirmation is non-secret but belongs in local runtime configuration rather than source control.
- Generated order references are non-secret correlation identifiers, but logs should remain sanitized and avoid unnecessary account context.
- Credentials remain entered only through the local session workflow and are never committed.
- Previously exposed credentials must be revoked and regenerated before any live preflight.
- RUFLO or any other agent cannot affirm compliance, change readiness, or exercise discretionary trading authority.

## Primary References

- Groww Python SDK order documentation: <https://groww.in/trade-api/docs/python-sdk/orders>
- NSE implementation standards for safer participation of retail investors in algorithmic trading: <https://nsearchives.nseindia.com/content/circulars/INSP73850.pdf>
- SEBI circular on safer participation of retail investors in algorithmic trading: <https://www.sebi.gov.in/legal/circulars/feb-2025/safer-participation-of-retail-investors-in-algorithmic-trading_91614.html>

## Acceptance Criteria

The correction is complete when:

- no production path uses `GROWW_ALGO_ID` to determine readiness or construct a Groww order;
- the new confirmation gate is explicit, independent, and fail-closed;
- every Groww order receives a valid generated client tracking reference;
- setup, status, templates, tests, and documentation use the corrected concepts consistently;
- all relevant tests and builds pass; and
- verification performs no real-money transaction.
