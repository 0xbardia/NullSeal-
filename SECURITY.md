# NullSeal Security Review

## Scope and threat model

This review covers `contracts/NullSeal.py`, its prompts, persistent state, source policy, and current Direct Mode tests. It considers hostile event text and webpages, fabricated leader output, validator rubber-stamping, missing or changing sources, malformed results, repeated writes, deadline errors, oversized inputs, and bounded-negative wording.

## Findings

| Severity | Open | Finding and handling |
|---|---:|---|
| P0 | 0 | No known catastrophic issue in the reviewed candidate. |
| P1 | 0 | No known high-severity issue in the reviewed candidate. |
| P2 | 7 | Known limits below; none is represented as a global absence guarantee. |

### P2 limitations

1. **Bounded evidence only.** A source list can be incomplete, stale, or wrong. `NOT_OBSERVED` says only that no qualifying evidence was observed in every declared source under the implemented review limits.
2. **Common-mode model error.** Validators refetch and independently classify, so they can reject a bad leader. Validators can still share a model weakness or be misled by the same source.
3. **Source drift reduces liveness.** The validator requires exact body digest and length equality. Even harmless changes between requests cause disagreement and retry/rotation.
4. **Redirect provenance is limited by the current Web API.** The stable response surface used here exposes status and body but not a verified final URL. The stored provenance identifies the declared URL; it cannot attest to each redirect hop.
5. **No JavaScript rendering.** V1 assesses returned static text. Pages that require client-side rendering can be unavailable or incomplete and must not yield `NOT_OBSERVED` when their content is empty or truncated.
6. **Bounded text review.** The fetched body is capped to a 16 KB prefix for parsing, and the LLM input to 6,000 visible characters. Any such truncation blocks a negative certificate. Large responses may still incur fetch-side work before the returned body is capped.
7. **Prompt injection is not eliminated.** Instructions in event/page data are explicitly untrusted, exact quotes are required, and validators independently assess them. Prompt wording and consensus do not guarantee that every model will resist the same hostile text.

## Controls verified

- Source universe and policy are frozen at claim creation. URLs are HTTPS hostnames, bounded, normalized, and duplicate-checked; IP literals, credentials, local names, whitespace, and non-HTTPS sources are rejected.
- Negative status requires every declared source to be available, readable, untruncated, and classified `NO_QUALIFYING_EVIDENCE`.
- Empty bodies, HTTP failures, malformed responses, ambiguous timing, and truncated content cannot become `NOT_OBSERVED`.
- `OBSERVED` requires both event and timing quotes present in the exact reviewed text.
- Validators refetch and rerun the classification. They compare source outcomes and content digests, then verify the leader's quotes against their independently retrieved text; different valid quote selections do not cause disagreement. Direct Mode tests show rejection of false `OBSERVED`, false `NOT_OBSERVED`, fake coverage, wrong source order, post-deadline claims, malformed leader output, fabricated quotes, and changed source content.
- State mutation occurs after the accepted nondeterministic result. Invalid writes leave state unchanged; terminal results cannot be changed; `INCONCLUSIVE` retries use the same source list.
- Claim, source, event, URL, source-body processing, quote, and prompt sizes are bounded. The claim count is capped at 256 per instance.
- The contract stores source hashes and compact quoted evidence, not entire webpages or validator reasoning.

## Security posture

No P0/P1 issue is known in the candidate. The P2 limits above remain part of the product semantics and must remain visible in documentation. A source policy must use stable, attributable pages appropriate to the event; users must not interpret a bounded `NOT_OBSERVED` result as universal non-occurrence.
