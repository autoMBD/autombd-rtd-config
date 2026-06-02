# tests/unit/test_module_providers.py
from rtd_config.intent import Intent
from rtd_config.modules.uart import UartProvider


def test_uart_plan_declares_dependencies_without_owning_other_modules():
    intent = Intent.from_dict({
        "module": "uart",
        "action": "set",
        "payload": {
            "hw": "LPUART_0",
            "mode": "interrupt",
            "baud": 115200,
            "pins": {"tx": "PTA15", "rx": "PTA16"},
        },
    })
    plan = UartProvider().plan(intent)
    payload = plan.to_dict()
    owners = {item["owner"] for item in payload["changes"]}
    assert "uart" in owners
    assert "platform" in owners
    assert "port" in owners
    assert "mcu" in owners
