# NullSeal V1

**Bounded Proof of Non-Observation for GenLayer**

NullSeal is a reusable Intelligent Contract primitive. It records an immutable event definition, deadline, and source list, then asks GenLayer validators to independently inspect that exact evidence universe.

`NOT_OBSERVED` means every declared source was retrieved and assessed and no qualifying evidence that the event occurred by the deadline was found. It does **not** prove that the event did not happen elsewhere.

## What it is and is not

NullSeal handles natural-language evidence, event timing, incomplete sources, and disagreement between independent fetches. A deterministic contract cannot safely decide all of these from a live web page. GenLayer's leader and validators retrieve and judge the source material, and the contract accepts a result only when the custom validator independently reaches the same decision-bearing assessment.

NullSeal is not a global oracle, search engine, archive, legal determination, or guarantee that a source is complete or truthful. It never searches for replacement sources. It does not claim universal non-occurrence.

## Evidence universe and source policy

At claim creation the contract freezes:

- the event statement and Unix UTC deadline;
- the ordered HTTPS hostname URLs;
- the policy `EVERY_DECLARED_SOURCE_REQUIRED`.

V1 allows 1–5 unique URLs, 512 characters per URL, 512 characters per event statement, and 256 claims per contract instance. URLs are normalized by lowercasing scheme and hostname, removing `:443` and fragments, and adding `/` when the path is empty. IP literals, credentials, non-HTTPS schemes, local names, whitespace, and duplicates are rejected.

An inspection stores only a compact outcome, short exact evidence/timing quotes, a SHA-256 body digest, response length, and a truncation flag. Webpage bodies are never persisted. If the fetch fails, the content is empty or malformed, or the inspected text is truncated, that source cannot support a negative result.

## Statuses and deadlines

```text
OPEN ── qualifying evidence ──> OBSERVED (terminal)
  ├── all sources cleanly assessed, no qualifying evidence ──> NOT_OBSERVED (terminal)
  └── missing, truncated, ambiguous, or conflicting assessment ──> INCONCLUSIVE (retryable)
```

- `OBSERVED`: at least one source contains exact quoted evidence for the event and its timing on or before the deadline.
- `NOT_OBSERVED`: every required source was available, complete within the contract's review limits, and unambiguously assessed without qualifying evidence. This is bounded non-observation only.
- `INCONCLUSIVE`: the contract cannot issue a reliable bounded negative. Retrying rechecks the same frozen sources and may reach a terminal result.
- `OPEN`: no assessment has been accepted yet.

`resolve_claim` is permitted at or after the deadline, using GenLayer's transaction timestamp. It rejects a pre-deadline call. `OBSERVED` and `NOT_OBSERVED` cannot be overwritten; `INCONCLUSIVE` can be retried.

## Consensus design

The leader fetches each declared URL and requests a small structured classification: `OCCURRENCE_EVIDENCE`, `NO_QUALIFYING_EVIDENCE`, or `AMBIGUOUS`. Fetch failures become `UNAVAILABLE`. The LLM receives the event and page text as untrusted data, must provide exact source quotes for positive evidence, and may not treat missing keywords as proof.

Each validator independently refetches every required URL, independently runs the source assessment, checks the leader's quotes against its own retrieved text, and derives the expected status. The custom Equivalence Principle validator compares the ordered URLs, outcome enums, body digests, lengths, and truncation flags. Valid quote selections may differ when they are present in the same independently retrieved content and the source outcomes agree. It rejects malformed, unsupported, fabricated, incomplete, or materially divergent leader assessments. Explanatory prose is not part of consensus.

Deterministic writes happen only after `run_nondet_unsafe` returns an accepted value. Validator-local results and reasoning are not persisted.

## API

| Method | Purpose |
|---|---|
| `create_claim(event_statement, deadline, source_urls)` | Create an immutable claim; returns its stable decimal index ID as text. |
| `resolve_claim(claim_id)` | Independently assess sources at/after deadline; returns the accepted status. |
| `get_version()` | Return `1.0.0`. |
| `get_claim_count()` | Number of claims. |
| `get_claim_id_at(index)` | Claim ID, or empty text for an invalid index. |
| `get_claim(claim_id)` | Compact JSON definition, state, and source assessments; empty text for an unknown ID. |
| `get_status(claim_id)` | Status, or empty text for an unknown ID. |
| `get_source_policy(claim_id)` | Frozen policy, or empty text for an unknown ID. |
| `get_source_count(claim_id)` | Number of frozen sources, or zero for an unknown ID. |
| `get_source(claim_id, index)` | Frozen URL, or empty text for an invalid ID/index. |
| `get_resolution(claim_id)` | Compact JSON status, timestamp, attempts, and bounded-negative flag. |
| `is_resolved(claim_id)` | True only for terminal `OBSERVED` or `NOT_OBSERVED`. |
| `get_source_assessment(claim_id, index)` | Compact JSON assessment, or empty text for an invalid ID/index. |

All read methods are `@gl.public.view` and use predictable empty/zero/false results for invalid IDs or indexes.

## Security and limits

Event statements and retrieved text are separated from contract instructions and explicitly labeled untrusted. HTML script/style-like content is excluded. A positive decision requires short exact quotes present in the text supplied to the model. If the response exceeds 16 KB or visible text exceeds the 6,000-character review limit, the source is marked truncated and cannot contribute to `NOT_OBSERVED`.

Validators independently repeat retrieval and classification. This makes consensus substantive and allows a false or malicious leader result to be rejected. It does not prevent multiple validators from sharing a model error, being influenced by the same hostile source, or independently receiving the same misleading source. See [SECURITY.md](SECURITY.md).

## Reuse examples

The primitive can support narrowly phrased claims such as:

- whether an official cancellation or retraction appears on named channels;
- whether an agreed SLA response appears on named support channels;
- whether an official notice appears on a declared agency page;
- whether a qualifying filing appears in a named public registry;
- whether a published correction appears on a declared publisher page;
- whether a release announcement appears in a named project repository.

Each result remains bounded to its immutable source list and deadline.

## Local development

Python 3.12 is used with pinned official GenLayer tooling:

```bash
python3.12 -m venv .venv
./.venv/bin/pip install -r requirements-dev.txt
./.venv/bin/pytest -q tests/direct/
./.venv/bin/genvm-lint check contracts/NullSeal.py --json
./.venv/bin/genvm-lint schema contracts/NullSeal.py --json
```

Direct Mode tests use mocked web/LLM responses and exercise agreement, malicious-leader rejection, prompt injection input, boundaries, retries, terminal states, and all views. The linter currently reports an informational newer-runner advisory; the stable target remains the runner used by current stable Studionet tooling. See [CERTIFICATION.md](CERTIFICATION.md).

## Studionet integration and deployment

The target is stable GenLayer Studio at `https://studio.genlayer.com/api`, chain ID `61999`. Studio-dev is a separate release-candidate network and is not the release target.

To run the integration certification with a configured Studionet account, put its private key in ignored `.env` as `NULLSEAL_STUDIO_PRIVATE_KEY=...`, then run:

```bash
./.venv/bin/pytest -s -v tests/integration/test_nullseal_studio.py::test_studionet_release_scenarios_and_all_public_views
```

With no contract address configured, the test deploys the local candidate to stable Studionet. To resume an existing deployment, set `NULLSEAL_STUDIO_CONTRACT_ADDRESS`; the harness verifies the deployed source before continuing and will not recreate claims already present. It waits for `Finalized`, requires `MAJORITY_AGREE` and successful execution, verifies the deployed source bytes and schema, and records every public-view result. A submitted transaction ID is tracked rather than resubmitted.

### Current Studionet release

- Network: stable GenLayer Studionet, chain ID `61999`.
- Contract: `0x6b8f3D5Bcf7fb2e8f12b9bf1624F102745B21d02`.
- Deployment transaction: `0x14c2c86fe09437f7a0db9a66418408b89ca1f9a67715e41903f21a2a700b0904` (`Finalized`, `MAJORITY_AGREE`).
- Deployed source SHA-256: `b8f038b859fa130154786f5fcd623570ed08729f6ad29bf9b4207f88ec572fd4`.
- The live `OBSERVED` case used the [official GitHub release record](https://api.github.com/repos/genlayerlabs/genlayer-py/releases/tags/v0.18.0) for `genlayer-py` tag `v0.18.0`, with its explicit `published_at` value. The live `NOT_OBSERVED` case was limited to the declared commit API URL and one exact message. An unavailable declared URL produced `INCONCLUSIVE`.
- The final live run called every public view and checked invalid IDs and indexes. See [CERTIFICATION.md](CERTIFICATION.md) for transaction IDs, vote records, read results, and test evidence.

## Candidate identity

- Contract source SHA-256: `b8f038b859fa130154786f5fcd623570ed08729f6ad29bf9b4207f88ec572fd4`.
- Public repository: [github.com/0xbardia/NullSeal-](https://github.com/0xbardia/NullSeal-).
- Release tag: `v1.0.0`, pointing to the published `main` release commit.
- Deployed address: `0x6b8f3D5Bcf7fb2e8f12b9bf1624F102745B21d02` on stable Studionet.
