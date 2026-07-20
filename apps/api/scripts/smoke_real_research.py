import asyncio
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

API_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = API_ROOT.parents[1]
sys.path.insert(0, str(API_ROOT / "src"))

from jhai_to_c.config import Settings  # noqa: E402
from jhai_to_c.providers.interfaces import ResearchQuery  # noqa: E402
from jhai_to_c.providers.real import BochaResearchProvider  # noqa: E402


async def main() -> None:
    settings = Settings(_env_file=PROJECT_ROOT / ".env")
    if settings.research_provider != "bocha" or settings.research_api_key is None:
        raise SystemExit("RESEARCH_PROVIDER=bocha and RESEARCH_API_KEY are required")

    provider = BochaResearchProvider(
        api_key=settings.research_api_key.get_secret_value(),
        base_url=settings.research_api_base_url,
        request_timeout_seconds=settings.research_request_timeout_seconds,
        max_results=settings.research_max_results,
        max_retries=settings.research_max_retries,
        retry_base_delay_seconds=settings.research_retry_base_delay_seconds,
    )
    result = await provider.search(
        queries=[ResearchQuery(query="2026年中国短视频内容营销趋势")]
    )
    print(
        json.dumps(
            {
                "provider": result.provider,
                "is_mock": result.is_mock,
                "source_count": len(result.sources),
                "sources": [
                    {
                        "title": source.title,
                        "domain": urlsplit(source.url or "").netloc,
                    }
                    for source in result.sources[:3]
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
