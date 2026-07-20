import asyncio
import json
import sys
from pathlib import Path

from pydantic import Field

API_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = API_ROOT.parents[1]
sys.path.insert(0, str(API_ROOT / "src"))

from jhai_to_c.config import Settings  # noqa: E402
from jhai_to_c.contracts.common import ContractModel  # noqa: E402
from jhai_to_c.providers.real import RealAgentModelProvider  # noqa: E402


class SmokeOutput(ContractModel):
    message: str = Field(min_length=1)
    ready: bool


async def main() -> None:
    settings = Settings(_env_file=PROJECT_ROOT / ".env")
    if settings.llm_api_key is None or not settings.llm_model:
        raise SystemExit("LLM_API_KEY and LLM_MODEL are required")

    provider = RealAgentModelProvider(
        api_key=settings.llm_api_key,
        base_url=settings.llm_api_base_url,
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
        max_retries=1,
        retry_base_delay_seconds=settings.llm_retry_base_delay_seconds,
    )
    result = await provider.generate_structured(
        system_prompt="你是 API 接入验收助手。严格按请求返回结果。",
        input_data={
            "task": "返回固定验收结果",
            "expected": {"message": "Gemini 3.1 Pro 已接入", "ready": True},
        },
        output_model=SmokeOutput,
    )
    print(
        json.dumps(
            {
                "provider": result.provider,
                "model": result.model,
                "output": result.output.model_dump(mode="json"),
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "duration_ms": result.duration_ms,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
