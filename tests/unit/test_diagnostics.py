# tests/unit/test_diagnostics.py
from rtd_config.diagnostics import Diagnostic, Result


def test_result_serializes_stable_json_shape():
    result = Result(
        status="blocked",
        command="plan",
        diagnostics=[
            Diagnostic(
                severity="blocker",
                code="missing_pin_mapping",
                module="port",
                message="Pin PTA15 is not available.",
                details={"pin": "PTA15"},
            )
        ],
    )
    payload = result.to_dict()
    assert payload["status"] == "blocked"
    assert payload["diagnostics"][0]["code"] == "missing_pin_mapping"
    assert payload["diagnostics"][0]["details"]["pin"] == "PTA15"
