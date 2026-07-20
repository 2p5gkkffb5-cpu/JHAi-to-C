from jhai_to_c.contracts.common import ContractModel


def prompt_input_with_feedback(
    input_data: ContractModel,
    feedback: str | None,
) -> dict:
    payload = input_data.model_dump(mode="json")
    if feedback:
        payload["user_feedback"] = feedback
    return payload
