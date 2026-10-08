import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

import pytest
from genlayer_py.exceptions import GenLayerError
from genlayer_py import create_account, create_client
from genlayer_py.assertions import tx_execution_succeeded
from genlayer_py.chains import studionet
from genlayer_py.types import TransactionHashVariant, TransactionStatus


pytestmark = pytest.mark.integration

COMMIT = "cf421edc0d20e567cc5a3b4da198fce61f1e579f"
COMMIT_URL = f"https://api.github.com/repos/genlayerlabs/genlayer-py/git/commits/{COMMIT}"
MISSING_COMMIT_URL = (
    "https://api.github.com/repos/genlayerlabs/genlayer-py/git/commits/"
    "0000000000000000000000000000000000000000"
)
RELEASE_URL = "https://api.github.com/repos/genlayerlabs/genlayer-py/releases/tags/v0.18.0"
VIEW_METHODS = {
    "get_version",
    "get_claim_count",
    "get_claim_id_at",
    "get_claim",
    "get_status",
    "get_source_policy",
    "get_source_count",
    "get_source",
    "get_resolution",
    "is_resolved",
    "get_source_assessment",
}
WRITE_METHODS = {"create_claim", "resolve_claim"}
RATE_LIMIT_BACKOFF_SECONDS = 20
MAX_RATE_LIMIT_RETRIES = 30
MAX_CONSENSUS_DISAGREEMENT_RETRIES = 3
MAX_LIVE_ASSESSMENTS = 5
RETRYABLE_CONSENSUS_RESULTS = {
    "MAJORITY_DISAGREE",
    "NO_MAJORITY",
    "MAJORITY_TIMEOUT",
}


def _retry_rate_limit(action, operation):
    for attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
        try:
            return action()
        except GenLayerError as error:
            if "Rate limit exceeded" not in str(error) or attempt == MAX_RATE_LIMIT_RETRIES:
                raise
            print(
                json.dumps(
                    {
                        "rate_limited_operation": operation,
                        "retry": attempt + 1,
                        "wait_seconds": RATE_LIMIT_BACKOFF_SECONDS,
                    }
                ),
                flush=True,
            )
            time.sleep(RATE_LIMIT_BACKOFF_SECONDS)


def _read(client, address, account, method, *args):
    return _retry_rate_limit(
        lambda: client.read_contract(
            address=address,
            function_name=method,
            args=list(args),
            account=account,
            transaction_hash_variant=TransactionHashVariant.LATEST_FINAL,
        ),
        f"read:{method}",
    )


def _schema_from_deployed_source(source):
    linter = Path(sys.executable).with_name("genvm-lint")
    with tempfile.TemporaryDirectory() as directory:
        source_path = Path(directory) / "NullSeal.py"
        source_path.write_text(source, encoding="utf-8")
        result = subprocess.run(
            [str(linter), "schema", str(source_path), "--json"],
            check=True,
            capture_output=True,
            text=True,
        )
    return json.loads(result.stdout)["schema"]["methods"]


def _check(method, args, returned, expected, predicate=None):
    passed = predicate(returned) if predicate else returned == expected
    print(
        json.dumps(
            {
                "read_method": method,
                "args": args,
                "returned": returned,
                "expected": expected,
                "result": "PASS" if passed else "FAIL",
            },
            ensure_ascii=False,
            default=str,
        )
    )
    assert passed, f"{method}{args!r}: returned {returned!r}, expected {expected!r}"


def _assert_tx(receipt, success, submitted_tx=None, allow_consensus_disagreement=False):
    tx_id = receipt.get("tx_id") or receipt.get("hash")
    assert tx_id, f"SDK returned no GenLayer transaction ID: {receipt!r}"
    if submitted_tx is not None:
        submitted = (
            "0x" + bytes(submitted_tx).hex()
            if isinstance(submitted_tx, bytes)
            else str(submitted_tx)
        )
        assert str(tx_id).lower() == submitted.lower(), receipt
    assert receipt.get("status_name") == TransactionStatus.FINALIZED.value, receipt
    execution_success = tx_execution_succeeded(receipt)
    last_round = receipt.get("last_round") or {}
    leader_receipt = receipt.get("consensus_data", {}).get("leader_receipt") or []
    compact_leader_receipt = [
        {
            key: item.get(key)
            for key in ("execution_result", "mode", "vote", "eq_outputs", "result")
            if key in item
        }
        for item in leader_receipt
    ]
    print(
        json.dumps(
            {
                "tx_id": tx_id,
                "status": receipt.get("status_name"),
                "consensus_result": receipt.get("result_name"),
                "execution_result": receipt.get("tx_execution_result_name"),
                "execution_success": execution_success,
                "success_expected": success,
                "validators": last_round.get("round_validators", []),
                "validator_votes": last_round.get("validator_votes", []),
                "leader_equivalence_output": compact_leader_receipt,
            },
            default=str,
        )
    )
    consensus_result = receipt.get("result_name")
    if consensus_result != "MAJORITY_AGREE":
        if (
            allow_consensus_disagreement
            and consensus_result in RETRYABLE_CONSENSUS_RESULTS
            and execution_success
        ):
            return None
        assert consensus_result == "MAJORITY_AGREE", (
            f"consensus did not accept the leader result: {consensus_result}"
        )
    assert execution_success is success, receipt
    return tx_id


def _wait_finalized(client, tx_id):
    try:
        return _retry_rate_limit(
            lambda: client.wait_for_transaction_receipt(
                transaction_hash=tx_id,
                status=TransactionStatus.FINALIZED,
                interval=3_000,
                retries=600,
            ),
            f"track:{tx_id}",
        )
    except Exception as error:
        # Keep the submitted ID visible so tracking can resume without resubmission.
        print(json.dumps({"tx_id": str(tx_id), "tracking_error": str(error)}))
        raise


def _write(
    client,
    account,
    address,
    method,
    args,
    success=True,
    allow_consensus_disagreement=False,
):
    tx_id = _retry_rate_limit(
        lambda: client.write_contract(
            address=address,
            function_name=method,
            args=args,
            account=account,
            consensus_max_rotations=3,
        ),
        f"submit:{method}",
    )
    print(json.dumps({"submitted_method": method, "tx_id": str(tx_id)}), flush=True)
    return _assert_tx(
        _wait_finalized(client, tx_id),
        success,
        tx_id,
        allow_consensus_disagreement,
    )


def _resolve_claim_with_retries(client, account, address, claim_id):
    for attempt in range(MAX_CONSENSUS_DISAGREEMENT_RETRIES + 1):
        tx_id = _write(
            client,
            account,
            address,
            "resolve_claim",
            [claim_id],
            allow_consensus_disagreement=True,
        )
        if tx_id:
            return tx_id
        status = _read(client, address, account, "get_status", claim_id)
        _check("get_status", [claim_id], status, "OPEN")
        print(
            json.dumps(
                {
                    "rejected_resolution_retry": attempt + 1,
                    "claim_id": claim_id,
                    "state_after_rejection": status,
                }
            ),
            flush=True,
        )
    raise AssertionError(
        f"claim {claim_id} had no accepted resolution after "
        f"{MAX_CONSENSUS_DISAGREEMENT_RETRIES + 1} finalized attempts"
    )


def test_execution_success_requires_consensus_acceptance():
    base = {
        "tx_id": "0x01",
        "status_name": TransactionStatus.FINALIZED.value,
        "last_round": {},
        "consensus_data": {
            "leader_receipt": [{"execution_result": "SUCCESS", "mode": "leader"}]
        },
    }
    _assert_tx({**base, "result_name": "MAJORITY_AGREE"}, True)
    _assert_tx(
        {
            **base,
            "result_name": "MAJORITY_AGREE",
            "consensus_data": {
                "leader_receipt": [{"execution_result": "ERROR", "mode": "leader"}]
            },
        },
        False,
    )
    with pytest.raises(AssertionError, match="consensus did not accept"):
        _assert_tx({**base, "result_name": "MAJORITY_DISAGREE"}, True)
    assert (
        _assert_tx(
            {**base, "result_name": "MAJORITY_DISAGREE"},
            True,
            allow_consensus_disagreement=True,
        )
        is None
    )


def _assert_default_views(client, address, account):
    checks = (
        ("get_version", [], "1.0.0"),
        ("get_claim_count", [], 0),
        ("get_claim_id_at", [0], ""),
        ("get_claim_id_at", [-1], ""),
        ("get_claim", ["missing"], ""),
        ("get_status", ["missing"], ""),
        ("get_source_policy", ["missing"], ""),
        ("get_source_count", ["missing"], 0),
        ("get_source", ["missing", 0], ""),
        ("get_resolution", ["missing"], ""),
        ("is_resolved", ["missing"], False),
        ("get_source_assessment", ["missing", 0], ""),
    )
    for method, args, expected in checks:
        returned = _read(client, address, account, method, *args)
        _check(method, args, returned, expected)


def _assert_claim_views(
    client,
    address,
    account,
    claim_id,
    index,
    claim,
    count,
    skip_simple=False,
    include_invalid=True,
    record=None,
):
    source = claim["source"]
    status = claim["status"]
    outcome = claim["outcome"]
    deadline = claim["deadline"]
    attempts = claim["attempts"]
    resolved = status in ("OBSERVED", "NOT_OBSERVED")

    simple = (
        ("get_version", [], "1.0.0"),
        ("get_claim_count", [], count),
        ("get_claim_id_at", [index], claim_id),
        ("get_status", [claim_id], status),
        ("get_source_policy", [claim_id], "EVERY_DECLARED_SOURCE_REQUIRED"),
        ("get_source_count", [claim_id], 1),
        ("get_source", [claim_id, 0], source),
        ("is_resolved", [claim_id], resolved),
    )
    if not skip_simple:
        for method, args, expected in simple:
            returned = _read(client, address, account, method, *args)
            _check(method, args, returned, expected)

    if record is None:
        record = json.loads(_read(client, address, account, "get_claim", claim_id))
    expected_record = {
        "claim_id": claim_id,
        "event_statement": claim["event"],
        "deadline": deadline,
        "source_policy": "EVERY_DECLARED_SOURCE_REQUIRED",
        "status": status,
        "attempts": attempts,
        "sources": [{"url": source, "outcome": outcome}],
    }
    _check(
        "get_claim",
        [claim_id],
        record,
        {**expected_record, "creator": str(account.address)},
        lambda value: all(
            value.get(k) == v
            for k, v in expected_record.items()
            if k != "sources"
        )
        and len(value.get("sources", [])) == len(expected_record["sources"])
        and all(
            value["sources"][index].get(key) == expected
            for index, source in enumerate(expected_record["sources"])
            for key, expected in source.items()
        )
        and value.get("creator", "").lower() == str(account.address).lower()
        and value["created_at"] > 0
        and value["created_at"] <= deadline
        and (
            value["resolution_at"] == 0
            if status == "OPEN"
            else value["resolution_at"] >= deadline
        ),
    )

    resolution = json.loads(_read(client, address, account, "get_resolution", claim_id))
    expected_resolution = {
        "status": status,
        "attempts": attempts,
        "source_outcomes": [outcome],
        "bounded_negative": status == "NOT_OBSERVED",
    }
    _check(
        "get_resolution",
        [claim_id],
        resolution,
        expected_resolution,
        lambda value: all(value.get(k) == v for k, v in expected_resolution.items())
        and (
            value["last_assessment_at"] == 0
            if status == "OPEN"
            else value["last_assessment_at"] >= deadline
        ),
    )

    assessment = json.loads(
        _read(client, address, account, "get_source_assessment", claim_id, 0)
    )
    _check(
        "get_source_assessment",
        [claim_id, 0],
        assessment,
        {"outcome": outcome},
        lambda value: value.get("outcome") == outcome
        and (
            bool(value["body_sha256"])
            if outcome not in ("UNASSESSED", "UNAVAILABLE")
            else True
        ),
    )

    if include_invalid:
        invalid_reads = (
            ("get_claim", ["missing"], ""),
            ("get_status", ["missing"], ""),
            ("get_source_policy", ["missing"], ""),
            ("get_source_count", ["missing"], 0),
            ("get_source", ["missing", 0], ""),
            ("get_resolution", ["missing"], ""),
            ("is_resolved", ["missing"], False),
            ("get_source_assessment", ["missing", 0], ""),
            ("get_source", [claim_id, -1], ""),
            ("get_source", [claim_id, 1], ""),
            ("get_source_assessment", [claim_id, -1], ""),
            ("get_source_assessment", [claim_id, 1], ""),
            ("get_claim_id_at", [-1], ""),
            ("get_claim_id_at", [count], ""),
        )
        for method, args, expected in invalid_reads:
            _check(method, args, _read(client, address, account, method, *args), expected)


def test_studionet_release_scenarios_and_all_public_views():
    private_key = os.getenv("NULLSEAL_STUDIO_PRIVATE_KEY")
    if not private_key:
        pytest.skip("BLOCKED: set a funded Studionet NULLSEAL_STUDIO_PRIVATE_KEY in .env")

    account = create_account(private_key)
    client = create_client(chain=studionet, account=account)
    assert int(client.chain.id) == 61999
    chain_id = client.provider.make_request("eth_chainId", [])["result"]
    assert int(chain_id, 16) == 61999
    balance = client.get_balance(account.address)
    fee_manager = client.chain.fee_manager_contract
    if fee_manager is not None:
        assert balance > 0, "Studionet account has no GEN for fees"
    print(
        json.dumps(
            {
                "network": "studionet",
                "chain_id": 61999,
                "account_balance_wei": str(balance),
                "fee_manager_configured": fee_manager is not None,
            }
        )
    )

    source = Path("contracts/NullSeal.py").read_text(encoding="utf-8")
    contract_address = os.getenv("NULLSEAL_STUDIO_CONTRACT_ADDRESS")
    deployment_tx = os.getenv("NULLSEAL_STUDIO_DEPLOYMENT_TX")
    if deployment_tx:
        deployment = _wait_finalized(client, deployment_tx)
        _assert_tx(deployment, True, deployment_tx)
        deployed_address = deployment.get("recipient")
        if contract_address:
            assert deployed_address.lower() == contract_address.lower(), deployment
        else:
            contract_address = deployed_address
    if not contract_address:
        deployment_tx = _retry_rate_limit(
            lambda: client.deploy_contract(
                code=source,
                account=account,
                consensus_max_rotations=3,
            ),
            "submit:deploy_contract",
        )
        print(json.dumps({"submitted_method": "deploy_contract", "tx_id": str(deployment_tx)}), flush=True)
        deployment = _wait_finalized(client, deployment_tx)
        _assert_tx(deployment, True, deployment_tx)
        contract_address = (deployment.get("tx_data_decoded") or {}).get(
            "contract_address"
        ) or deployment.get("recipient")
    assert contract_address

    code_response = client.provider.make_request(
        "gen_getContractCode",
        [contract_address],
    )
    assert "error" not in code_response, code_response
    deployed_source = base64.b64decode(code_response["result"]).decode("utf-8")
    assert deployed_source == source, "deployed source differs from candidate"
    print(json.dumps({"contract": contract_address, "deployed_source_matches": True}))

    schema_methods = _schema_from_deployed_source(deployed_source)
    assert {name for name, method in schema_methods.items() if method["readonly"]} == VIEW_METHODS
    assert set(schema_methods) == VIEW_METHODS | WRITE_METHODS

    claims = [
        {
            "event": (
                "The official GitHub release API record for genlayer-py tag v0.18.0 "
                "has published_at equal to 2026-04-22T14:26:58Z, on or before the deadline."
            ),
            "source": RELEASE_URL,
            "deadline": None,
            "status": "OBSERVED",
            "outcome": "OCCURRENCE_EVIDENCE",
            "attempts": 1,
        },
        {
            "event": (
                f"The official genlayer-py commit page for {COMMIT} records the exact "
                "message 'NullSeal V1 release freeze' on or before the deadline."
            ),
            "source": COMMIT_URL,
            "deadline": None,
            "status": "NOT_OBSERVED",
            "outcome": "NO_QUALIFYING_EVIDENCE",
            "attempts": 1,
        },
        {
            "event": "The official genlayer-py repository published the missing commit before the deadline.",
            "source": MISSING_COMMIT_URL,
            "deadline": None,
            "status": "INCONCLUSIVE",
            "outcome": "UNAVAILABLE",
            "attempts": 1,
        },
    ]

    existing_count = _read(client, contract_address, account, "get_claim_count")
    assert 0 <= existing_count <= len(claims), (
        f"cannot resume safely with {existing_count} claims; expected 0 through {len(claims)}"
    )
    first_missing_index = existing_count
    if existing_count == 0:
        _assert_default_views(client, contract_address, account)
        claims[0]["deadline"] = int(time.time()) + 300
        _write(
            client,
            account,
            contract_address,
            "create_claim",
            [claims[0]["event"], claims[0]["deadline"], [claims[0]["source"]]],
        )
        claims[0].update(
            id="0",
            status="OPEN",
            outcome="UNASSESSED",
            attempts=0,
        )
        first_missing_index = 1
        _check(
            "get_status",
            ["0"],
            _read(client, contract_address, account, "get_status", "0"),
            "OPEN",
        )
        _write(
            client,
            account,
            contract_address,
            "resolve_claim",
            ["0"],
            success=False,
        )
        _check(
            "get_status",
            ["0"],
            _read(client, contract_address, account, "get_status", "0"),
            "OPEN",
        )

    else:
        _check("get_claim_count", [], existing_count, existing_count)
        for index, claim in enumerate(claims[:existing_count]):
            claim_id = str(index)
            record = json.loads(_read(client, contract_address, account, "get_claim", claim_id))
            assert record["claim_id"] == claim_id
            assert record["event_statement"] == claim["event"]
            assert record["source_policy"] == "EVERY_DECLARED_SOURCE_REQUIRED"
            assert len(record["sources"]) == 1
            assert record["sources"][0]["url"] == claim["source"]
            claim.update(
                id=claim_id,
                deadline=record["deadline"],
                status=record["status"],
                outcome=record["sources"][0]["outcome"],
                attempts=record["attempts"],
            )
            _check(
                "get_status",
                [claim_id],
                _read(client, contract_address, account, "get_status", claim_id),
                claim["status"],
            )

    # Set each deadline immediately before its own write. Rate limits can make
    # deadlines captured for later claims expire before those claims are created.
    for index in range(first_missing_index, len(claims)):
        claim = claims[index]
        claim["deadline"] = int(time.time()) + 300
        _write(
            client,
            account,
            contract_address,
            "create_claim",
            [claim["event"], claim["deadline"], [claim["source"]]],
        )
        claim.update(
            id=str(index),
            status="OPEN",
            outcome="UNASSESSED",
            attempts=0,
        )

    for index, claim in enumerate(claims):
        if index == 0 and claim["attempts"] == 0:
            _assert_claim_views(
                client,
                contract_address,
                account,
                claim["id"],
                index,
                claim,
                len(claims),
            )
        elif claim["attempts"] == 0:
            _check(
                "get_status",
                [claim["id"]],
                _read(client, contract_address, account, "get_status", claim["id"]),
                "OPEN",
            )

    time.sleep(max(0, max(claim["deadline"] for claim in claims) - int(time.time()) + 1))

    final_statuses = ("OBSERVED", "NOT_OBSERVED", "INCONCLUSIVE")
    final_outcomes = (
        "OCCURRENCE_EVIDENCE",
        "NO_QUALIFYING_EVIDENCE",
        "UNAVAILABLE",
    )
    for index, claim in enumerate(claims):
        while (
            claim["status"] != final_statuses[index]
            and claim["status"] in ("OPEN", "INCONCLUSIVE")
            and claim["attempts"] < MAX_LIVE_ASSESSMENTS
        ):
            previous_attempts = claim["attempts"]
            _resolve_claim_with_retries(
                client,
                account,
                contract_address,
                claim["id"],
            )
            record = json.loads(
                _read(client, contract_address, account, "get_claim", claim["id"])
            )
            claim.update(
                status=record["status"],
                outcome=record["sources"][0]["outcome"],
                attempts=record["attempts"],
            )
            assert claim["attempts"] == previous_attempts + 1, record
        assert claim["status"] == final_statuses[index], (
            f"claim {claim['id']} ended as {claim['status']} after "
            f"{claim['attempts']} assessment attempts; expected {final_statuses[index]}"
        )
        assert claim["outcome"] == final_outcomes[index]
        if index > 0:
            _check(
                "get_status",
                [claim["id"]],
                _read(client, contract_address, account, "get_status", claim["id"]),
                claim["status"],
            )
            _check(
                "is_resolved",
                [claim["id"]],
                _read(client, contract_address, account, "is_resolved", claim["id"]),
                claim["status"] in ("OBSERVED", "NOT_OBSERVED"),
            )
        _assert_claim_views(
            client,
            contract_address,
            account,
            claim["id"],
            index,
            claim,
            len(claims),
            skip_simple=index > 0,
            include_invalid=index == 0,
        )

    _check(
        "get_claim_count",
        [],
        _read(client, contract_address, account, "get_claim_count"),
        len(claims),
    )
