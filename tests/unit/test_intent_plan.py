# tests/unit/test_intent_plan.py
from rtd_config.intent import Intent
from rtd_config.plan import Plan, PlannedChange


def test_intent_loads_module_action_payload():
    intent = Intent.from_dict({
        "module": "uart",
        "action": "set",
        "payload": {"hw": "LPUART_0", "mode": "polling"},
    })
    assert intent.module == "uart"
    assert intent.action == "set"
    assert intent.payload["mode"] == "polling"


def test_plan_records_owned_changes():
    plan = Plan(changes=[
        PlannedChange(module="uart", owner="uart", path="/Uart", description="Set channel")
    ])
    assert plan.to_dict()["changes"][0]["owner"] == "uart"
