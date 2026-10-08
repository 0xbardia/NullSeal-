# NullSeal V1 Certification Record

**Status: CERTIFIED — all mandatory V1 gates passed on the final stable Studionet deployment.** Prior deployments are explicitly superseded below.

## Candidate and environment

- Project: NullSeal V1, Bounded Proof of Non-Observation
- Python: 3.12.13
- `genlayer-py`: 0.18.0, source commit `a3dc35e04898e3889cbfa855bcaf7d2664675b8f`
- `genlayer-testing-suite`: 0.29.2, source commit `9c09578b143905471fb0657dd53bdaf18da8e35f`
- `genvm-linter`: 0.11.1-rc.2, source commit `28450e665666300fc648dbe495110dfd0cb6a7b4`
- Stable contract runner: `py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6`
- Local network used for Direct Mode: localnet test VM; no local GenLayer node required.
- At certification time the source workspace had no Git metadata; the certified candidate is anchored by its SHA-256. The public release commit and tag are recorded in the release freeze below.

## Official documentation reviewed

The current official documentation was read from `https://docs.genlayer.com/full-documentation.txt` on 2026-10-07, with these pages used for implementation decisions:

- [Equivalence Principle](https://docs.genlayer.com/understand-genlayer-protocol/core-concepts/optimistic-democracy/equivalence-principle)
- [Non-determinism](https://docs.genlayer.com/developers/intelligent-contracts/features/non-determinism)
- [Testing Intelligent Contracts](https://docs.genlayer.com/developers/intelligent-contracts/testing)
- [GenLayer Testing Suite](https://docs.genlayer.com/api-references/genlayer-test)
- [Direct Mode API](https://docs.genlayer.com/api-references/genlayer-test/direct)
- [Development Setup](https://docs.genlayer.com/developers/intelligent-contracts/tooling-setup)
- [Prompt & Data Techniques](https://docs.genlayer.com/developers/intelligent-contracts/crafting-prompts)
- [Prompt Injection](https://docs.genlayer.com/developers/intelligent-contracts/security-and-best-practices/prompt-injection)
- [Web Access](https://docs.genlayer.com/developers/intelligent-contracts/features/web-access)
- [Transaction Context](https://docs.genlayer.com/developers/intelligent-contracts/features/transaction-context)
- [Introduction to Intelligent Contracts](https://docs.genlayer.com/developers/intelligent-contracts/introduction)
- [Persistent Storage](https://docs.genlayer.com/developers/intelligent-contracts/features/storage)
- [First Contract](https://docs.genlayer.com/developers/intelligent-contracts/first-contract)
- [GenLayer Studio](https://docs.genlayer.com/developers/intelligent-contracts/tools/genlayer-studio)
- [Studio Validators](https://docs.genlayer.com/developers/intelligent-contracts/tools/genlayer-studio/validators)
- [Current Intelligent Contract State](https://docs.genlayer.com/developers/intelligent-contracts/tools/genlayer-studio/contract-state)
- [Deploying Intelligent Contracts](https://docs.genlayer.com/developers/intelligent-contracts/deploying)
- [Writing to Intelligent Contracts](https://docs.genlayer.com/developers/decentralized-applications/writing-data)
- [Reading from Intelligent Contracts](https://docs.genlayer.com/developers/decentralized-applications/reading-data)
- [Transaction Statuses](https://docs.genlayer.com/understand-genlayer-protocol/core-concepts/transactions/transaction-statuses)
- [Finality](https://docs.genlayer.com/understand-genlayer-protocol/core-concepts/optimistic-democracy/finality)
- [Fee Outcomes and Debugging](https://docs.genlayer.com/developers/decentralized-applications/fee-outcomes-and-debugging)
- [Optimistic Democracy](https://docs.genlayer.com/understand-genlayer-protocol/core-concepts/optimistic-democracy)
- [Networks](https://docs.genlayer.com/developers/networks)
- [GenLayer Node transaction status](https://docs.genlayer.com/api-references/genlayer-node/gen/gen_getTransactionStatus)
- [GenLayer Node transaction lifecycle](https://docs.genlayer.com/api-references/genlayer-node/gen/gen_getTransactionLifecycle)
- [GenLayer Node contract code](https://docs.genlayer.com/api-references/genlayer-node/gen/gen_getContractCode)

### Material API decisions

1. The official stable Studionet preset in `genlayer-py 0.18.0` points at `https://studio.genlayer.com/api`, chain ID `61999`. A read-only `eth_chainId` request returned `0xf22f` (`61999`). Studio-dev is a separate chain (`61997`) and was not selected.
2. The stable docs and official boilerplate use runner `1jb…`. Current `genvm-lint` reports informational I200 that an RC runner `5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng` is available. That runner is not used because the target is stable Studionet and the current stable contract docs/preset still target `1jb…`.
3. The Web Access guide contains examples reading `response.status_code`; the installed stable runner and Direct Mode fixture expose `response.status`. The contract uses `response.status`, verified against the current `1jb…` runtime through Direct Mode.
4. The stable GenLayer Python SDK 0.18.0 does not expose the docs' `wait_for_finalization` convenience method. It does expose `wait_for_transaction_receipt(..., status=TransactionStatus.FINALIZED)`. The integration harness uses that current installed method, preserves the returned transaction ID, and checks execution success separately.
5. The GenLayer Testing Suite documents `direct_vm.check_pickling`, but its 0.29.2 Direct Mode implementation applies that check to `run_nondet`, not `run_nondet_unsafe`. NullSeal uses `run_nondet_unsafe`; therefore no claim is made that closure pickling was tested. Persistent GenVM storage behavior, JSON round-trips, constructor state, and all views are exercised in Direct Mode; serialized closure coverage remains unavailable in this test runner.
6. The current SDK forbids direct `DynArray()` construction; contract storage is zero-initialized by the runtime. The constructor therefore uses `pass`. Persisted source assessment arrays are JSON strings, while top-level state uses supported `DynArray[str]` and `TreeMap[str, ClaimRecord]` types.
7. The stable node's `gen_getContractCode` accepted the contract address as a positional parameter; an object parameter failed in the node adapter. The final verification uses the accepted positional form. The SDK's remote schema helper was rate-limited, so schema validation used `genvm-lint schema` on the exact fetched deployed source bytes.
8. `tx_execution_succeeded` alone is not a consensus-success check: the SDK can report leader execution success when the final consensus is `MAJORITY_DISAGREE`. The integration harness requires `FINALIZED`, `MAJORITY_AGREE`, and successful execution as separate conditions.

## Local certification

Final clean local run after the integration harness fixes:

| Gate | Command | Result |
|---|---|---|
| Direct Mode (included in complete run) | `./.venv/bin/pytest -q tests/direct/` | 46 passed, 0 failed, 0 skipped |
| Complete local suite | `./.venv/bin/pytest -q tests/` | 47 passed, 1 explicitly gated live test skipped, 0 failed |
| SDK receipt helper | `./.venv/bin/pytest -q tests/integration/test_nullseal_studio.py::test_execution_success_requires_consensus_acceptance` | 1 passed; confirms a finalized `MAJORITY_DISAGREE` is not an accepted successful write |
| GenVM lint | `./.venv/bin/genvm-lint check contracts/NullSeal.py --json` | Passed 3 checks; 0 errors; 1 documented informational I200 advisory |
| Schema | `./.venv/bin/genvm-lint schema contracts/NullSeal.py --json` | 13 methods: 11 views, 2 writes; expected method types/decorators present |

The 46 Direct Mode tests cover initialization, every read method, frozen source policy, URL/event boundaries, exact deadline boundary, positive/negative/inconclusive outcomes, HTTP and transport failures, empty/malformed/truncated inputs, retry behavior, prompt injection text, malicious leader results, fake coverage, wrong source set/deadline, source drift, prose variation, terminal immutability, and persistence round-trips.

Direct Mode's prompt-injection test verifies that hostile page text is included as untrusted evidence and the structured response is safely classified. Validator tests execute the custom validator against independent mocked web evidence and reject unsafe leader results. These deterministic tests do not claim live model behavior. The installed test runner's pickling check applies to `run_nondet`, not `run_nondet_unsafe`; closure pickling is unavailable for this contract path. Persistent storage types and JSON round-trips are exercised.

## Security review

See [SECURITY.md](SECURITY.md). Current review counts: P0 open 0, P1 open 0, P2 known limitations 7. No global non-occurrence claim is made. Main bounded limitations are incomplete source universes, common-mode model error, exact-body-digest liveness, missing redirect-final-URL provenance, static-text-only review, input truncation, and residual prompt-injection risk.

## Studio and Studionet

- Stable Studio URL opened: `https://studio.genlayer.com/contracts`.
- Hosted RPC chain ID: verified as `61999` (`0xf22f`).
- Network: stable GenLayer Studionet, SDK preset `https://studio.genlayer.com/api`, chain ID `61999`.
- The test account balance was `0 GEN`; the SDK reported `fee_manager_contract=None`. Deployment and writes succeeded under the current no-fee-manager network configuration. A Studio faucet request returned HTTP 429 (`Rate limit exceeded: 5000 requests per day`) and was not relied on for funding.
- Final deployment: `0x6b8f3D5Bcf7fb2e8f12b9bf1624F102745B21d02`.
- Deployment transaction: `0x14c2c86fe09437f7a0db9a66418408b89ca1f9a67715e41903f21a2a700b0904`, finalized at `2026-10-07T23:04:14.100174Z`, `MAJORITY_AGREE`, leader execution successful. The fetched receipt recorded two validator executions agreeing and two idling after quorum.
- Final resolution receipts showed heterogeneous validator configurations. The successful `OBSERVED` transaction recorded `prd-sonnet`, `prd-mistral`, and `prd-grok` primary policies with different OpenRouter fallback model IDs. Other final resolutions recorded `prd-gpt-5-4`, `prd-deepseek`, `prd-glm`, and `prd-gemma` policies. These are configured policy/fallback names; the report does not infer a single underlying model was selected by each dynamic policy.
- Deployed code was fetched with `gen_getContractCode` and exactly matched local `contracts/NullSeal.py`. The SDK's `get_contract_schema_for_code` route had exhausted its documented remote request bucket; the schema was derived from those exact fetched bytes with installed `genvm-lint schema` and contained the expected 13 methods (11 views, 2 writes).
- Final candidate source SHA-256: `b8f038b859fa130154786f5fcd623570ed08729f6ad29bf9b4207f88ec572fd4` (20,640 bytes).

### Final live scenarios

Each write was followed to `FINALIZED`; the harness separately checked consensus result and leader execution result. The following IDs are from the final address above.

| Scenario | Claim | Resolution transaction | Result and evidence | Validator receipt configuration |
|---|---:|---|---|---|
| Premature resolution | 0 | `0x061e801ebb77b6c32719c5ee8abf380c07888c2fdf162933aeb32c629cd517c4` | `FINALIZED`, `MAJORITY_AGREE` on rollback; execution failed as expected, status remained `OPEN`; four recorded validator executions agreed | — |
| `OBSERVED` | 0 | `0x1765e03de5137943dfc12310f2d793f147a040668d5db5604f458cc53a3be3cd` | `FINALIZED`, `MAJORITY_AGREE`; exact tag and `published_at` quotes from the official `v0.18.0` GitHub release record; stored body length 2,870, not truncated; three recorded validator executions agreed and one idled after quorum | `prd-sonnet`, `prd-mistral`, `prd-grok` policies |
| `NOT_OBSERVED` | 1 | `0xd62e699fcb3e97ca634515c882989b80cd913fc86ed01da69d53de2a995094ff` | `FINALIZED`, `MAJORITY_AGREE`; the declared commit record was successfully assessed and did not contain the exact claimed message; `bounded_negative=true`; two recorded validator executions agreed and two idled after quorum | `prd-gemma`, `prd-glm` policies |
| `INCONCLUSIVE` | 2 | `0x76ec05c0e4b771d9908f3d40822ae19f7d4cd9ff839d2ac89e0fc1d04688e9b9` | `FINALIZED`, `MAJORITY_AGREE`; the required declared GitHub URL was unavailable and persisted as `UNAVAILABLE`; `bounded_negative=false`; two recorded validator executions agreed and two idled after quorum | `prd-deepseek`, `prd-sonnet` policies |

Claim-creation transactions were finalized as follows: claim 0 `0xd7a2ca2127a95ed93888b0aa82a2fffa5ae40a7c0ea92e4878c21ec9cb25532d`; claim 1 `0x2107899651100deddd5322b19defb89531f12fe859e847f494d1bd89cf2a83c9`; claim 2 `0xe13929aef78fbc74db3d3eae65dab5411e043773a65c32121cde8612c732b71d`.

### Final read-method certification

The final integration run read the finalized deployed state, called all 11 public view methods, checked unknown IDs and invalid indexes, and passed **77/77 assertions**. The return values matched the expected state: claim 0 `OBSERVED`, claim 1 `NOT_OBSERVED`, claim 2 `INCONCLUSIVE`; unknown IDs and invalid indexes returned the documented empty, zero, or false values.

| Public view | Final arguments checked | Returned / expected | Result |
|---|---|---|---|
| `get_version` | `[]` | `"1.0.0"` / `"1.0.0"` | PASS |
| `get_claim_count` | `[]` | `3` / `3` | PASS |
| `get_claim_id_at` | `[0]`, `[-1]`, `[3]` | `"0"`, `""`, `""` / same | PASS |
| `get_claim` | `["0"]`, `["1"]`, `["2"]`, `["missing"]` | records match stored definitions/statuses; unknown ID `""` / expected records and `""` | PASS |
| `get_status` | `["0"]`, `["1"]`, `["2"]`, `["missing"]` | `OBSERVED`, `NOT_OBSERVED`, `INCONCLUSIVE`, `""` / same | PASS |
| `get_source_policy` | `["0"]`, `["missing"]` | `EVERY_DECLARED_SOURCE_REQUIRED`, `""` / same | PASS |
| `get_source_count` | `["0"]`, `["missing"]` | `1`, `0` / same | PASS |
| `get_source` | `["0",0]`, `["missing",0]`, `["0",-1]`, `["0",1]` | frozen release URL, then `""` / same | PASS |
| `get_resolution` | `["0"]`, `["1"]`, `["2"]`, `["missing"]` | finalized statuses, attempts, source outcomes, and bounded-negative flags match; unknown ID `""` | PASS |
| `is_resolved` | `["0"]`, `["1"]`, `["2"]`, `["missing"]` | `true`, `true`, `false`, `false` / same | PASS |
| `get_source_assessment` | `["0",0]`, `["1",0]`, `["2",0]`, `["missing",0]`, `["0",-1]`, `["0",1]` | `OCCURRENCE_EVIDENCE`, `NO_QUALIFYING_EVIDENCE`, `UNAVAILABLE`, then `""` for invalid ID/index / same | PASS |

**TOTAL: 77/77 PASS.** The test also verified initialized empty state before claim creation and the created `OPEN` claim state before resolution. It uses `TransactionHashVariant.LATEST_FINAL` for view calls.

The hosted endpoint rate-limited some reads and pre-submission writes. The harness retried only explicit rate-limit errors with a 20-second delay. Once a transaction ID existed, that same ID was tracked to finality; no state-changing transaction was blindly resubmitted.

### Superseded deployments

| Candidate | Address / deployment tx | Source SHA-256 | Disposition |
|---|---|---|---|
| A | `0x607B133c25EE9413110b938fBeb4847F92D58dff` / `0x278cf32f3b22472b025dd703457ea574d4e0a530f9eb2c718a0f6d733e19a082` | `f42addce343970a64cac92db9612796833d732f7b7ca12d9af300613794775c2` | Superseded after its quote-equality validator rejected legitimate independent quote variation; its live resolution finalized `MAJORITY_DISAGREE` and left state unchanged. |
| B | `0x6117D3b317B1b0916a20E790Cc11d66fD69AACF1` / `0x5ce05970e5153fba93380d67f66ece4884719a8d6b6adf080fdf4f5b7beebb9f` | `b8f038b859fa130154786f5fcd623570ed08729f6ad29bf9b4207f88ec572fd4` | Superseded under the requested post-deployment regression loop after the integration harness's stale-deadline and single-attempt assumptions were corrected. A live positive attempt `0xa3e6536037ed137473b0e6d36bb3c15d6a36a86817cd38ca161237dc5876da63` finalized `MAJORITY_DISAGREE` and left state `OPEN`; subsequent accepted assessments were `INCONCLUSIVE` when independent evidence did not consistently establish timing. Contract source was unchanged; the final candidate is freshly deployed and fully recertified. |

## Judge/reviewer attack pass

| Objection | Evidence | Result |
|---|---|---|
| Thin LLM wrapper | Leader and every validator independently fetch and classify the frozen URL list; exact quote/hash fields are checked. | Rejected |
| Decorative consensus | Direct VM validator execution rejects forged positive/negative results, fake coverage, wrong source set, post-deadline evidence, malformed data, and changed content. | Rejected locally |
| Ordinary oracle | Natural-language evidence/timing judgment, incomplete content, ambiguity, and validator source drift affect the decision. | Rejected |
| Universal-negative claim | `NOT_OBSERVED` is limited to the stored source list and explicit source policy everywhere. | Avoided |
| Mutable source policy | Claim definition, ordered sources, and policy are written once. | Avoided |
| Unavailable evidence becomes absence | Any unavailable/ambiguous/truncated required source makes the result `INCONCLUSIVE` unless another source establishes `OBSERVED`. | Avoided |
| Meaningless state | Claim identity, creator, event, deadline, times, policy, sources, state, attempts, and compact assessments persist. | Avoided |
| Demo-only | README lists reusable bounded applications; no extra product subsystems were added. | Addressed |
| Happy-path-only tests | 46 Direct Mode tests include rejection, errors, boundaries, drift, and retries. | Addressed locally |

## Release freeze

- Candidate contract source SHA-256: `b8f038b859fa130154786f5fcd623570ed08729f6ad29bf9b4207f88ec572fd4` (20,640 bytes); the deployed bytes exactly match this file.
- Public repository: `https://github.com/0xbardia/NullSeal-`.
- Git release tag: `v1.0.0`, pointing to the published `main` release commit.
- Worktree clean: YES after the release commit; no contract source change occurred after the final deployment and hash verification.
- Network / chain ID: stable GenLayer Studionet / `61999`.
- Final contract: `0x6b8f3D5Bcf7fb2e8f12b9bf1624F102745B21d02`.
- Deployment transaction: `0x14c2c86fe09437f7a0db9a66418408b89ca1f9a67715e41903f21a2a700b0904`.
- Scenario transactions: OBSERVED `0x1765e03de5137943dfc12310f2d793f147a040668d5db5604f458cc53a3be3cd`; NOT_OBSERVED `0xd62e699fcb3e97ca634515c882989b80cd913fc86ed01da69d53de2a995094ff`; INCONCLUSIVE `0x76ec05c0e4b771d9908f3d40822ae19f7d4cd9ff839d2ac89e0fc1d04688e9b9`.
- Final integration command: `./.venv/bin/pytest -s -v tests/integration/test_nullseal_studio.py::test_studionet_release_scenarios_and_all_public_views` with `NULLSEAL_STUDIO_PRIVATE_KEY` supplied from the local environment; **1 passed**, 0 failed, 23m01s. It verified deployment, source/schema, all three finalized scenarios, premature-resolution rollback, and 77/77 public-view assertions.

## Final verdict

All mandatory V1 gates are green on the final Studionet deployment. P0 open: 0; P1 open: 0; known P2 limitations: 7. The separate account balance was zero and the faucet was rate-limited, but the current stable Studionet preset reported no fee manager and all final deployment/write transactions reached `FINALIZED` with the required execution and consensus results. Prior deployments are listed as superseded; only the final address above is certified.
