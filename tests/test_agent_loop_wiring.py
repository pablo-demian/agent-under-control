
import json
from types import SimpleNamespace
from unittest.mock import Mock

from src import agent


def make_response(*, output, text="", response_id="resp_test"):
    return SimpleNamespace(
        id=response_id,
        status="completed",
        usage=None,
        output=output,
        output_text=text,
    )


def test_opa_mode_passes_allowed_resources_to_observer(monkeypatch):
    tool_call = SimpleNamespace(
        type="function_call",
        name="set_log_verbosity_level",
        arguments=json.dumps({
            "service": "payments-api",
            "environment": "staging",
            "level": "INFO",
        }),
        call_id="call_loop_001",
        model_dump=lambda **kwargs: {
            "type": "function_call",
            "name": "set_log_verbosity_level",
            "arguments": json.dumps({
                "service": "payments-api",
                "environment": "staging",
                "level": "INFO",
            }),
            "call_id": "call_loop_001",
        },
    )

    first_response = make_response(
        output=[tool_call],
        response_id="resp_tool_call",
    )

    second_response = make_response(
        output=[],
        text="Incident investigation completed.",
        response_id="resp_completed",
    )

    model_create = Mock(
        side_effect=[first_response, second_response]
    )

    observer = Mock(
        return_value={"status": "completed"}
    )

    trace = Mock()

    monkeypatch.setattr(agent, "POLICY_MODE", "opa")
    monkeypatch.setattr(agent, "MAX_ROUNDS", 2)
    monkeypatch.setattr(agent, "trace", trace)
    monkeypatch.setattr(
        agent.client.responses,
        "create",
        model_create,
    )
    monkeypatch.setattr(
        agent,
        "execute_observed_tool",
        observer,
    )

    agent.run_agent()

    observer.assert_called_once()

    kwargs = observer.call_args.kwargs

    assert kwargs["name"] == "set_log_verbosity_level"
    assert kwargs["call_id"] == "call_loop_001"
    assert kwargs["allowed_resources"] == frozenset({
        "payments-api",
    })

    # The simulated model must receive exactly one result.
    second_request = model_create.call_args_list[1]
    conversation = second_request.kwargs["input"]

    outputs = [
        item
        for item in conversation
        if item.get("type") == "function_call_output"
    ]

    assert len(outputs) == 1
    assert outputs[0]["call_id"] == "call_loop_001"
    assert json.loads(outputs[0]["output"]) == {
        "status": "completed",
    }
