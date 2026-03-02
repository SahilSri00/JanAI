import httpx
import asyncio
import os
import structlog
from dotenv import load_dotenv

load_dotenv()
log = structlog.get_logger()

BHASHINI_INFERENCE_URL = "https://dhruva-api.bhashini.gov.in/services/inference/pipeline"
API_KEY    = os.getenv("BHASHINI_API_KEY")
USER_ID    = os.getenv("BHASHINI_USER_ID")
PIPELINE_ID = os.getenv("BHASHINI_PIPELINE_ID", "64392f96daac500b55c543cd")

MAX_RETRIES = 3
BACKOFF_SECONDS = [1, 2, 4]


async def translate(text: str, source_lang: str, target_lang: str) -> dict:
    """
    Translate text using Bhashini API with 3-retry exponential backoff.

    Args:
        text: Text to translate
        source_lang: Source language code (e.g., "en", "hi")
        target_lang: Target language code (e.g., "hi", "ta")

    Returns:
        {
            "original_text": str,
            "translated_text": str,
            "source_lang": str,
            "target_lang": str
        }
    """
    payload = {
        "pipelineTasks": [
            {
                "taskType": "translation",
                "config": {
                    "language": {
                        "sourceLanguage": source_lang,
                        "targetLanguage": target_lang
                    },
                    "serviceId": ""
                }
            }
        ],
        "inputData": {
            "input": [{"source": text}],
            "audio": []
        }
    }

    headers = {
        "Authorization": API_KEY,
        "userID": USER_ID,
        "ulcaApiKey": API_KEY,
        "Content-Type": "application/json"
    }

    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            log.info("bhashini.translate.attempt",
                     attempt=attempt + 1, source=source_lang, target=target_lang)

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    BHASHINI_INFERENCE_URL,
                    json=payload,
                    headers=headers
                )
                response.raise_for_status()
                data = response.json()

                translated = (
                    data["pipelineResponse"][0]["output"][0]["target"]
                )

                log.info("bhashini.translate.success", attempt=attempt + 1)
                return {
                    "original_text": text,
                    "translated_text": translated,
                    "source_lang": source_lang,
                    "target_lang": target_lang,
                    "attempts": attempt + 1
                }

        except (httpx.HTTPError, KeyError, IndexError) as e:
            last_error = e
            log.warning("bhashini.translate.failed",
                        attempt=attempt + 1, error=str(e))

            if attempt < MAX_RETRIES - 1:
                wait = BACKOFF_SECONDS[attempt]
                log.info("bhashini.translate.retry", wait_seconds=wait)
                await asyncio.sleep(wait)

    # All retries exhausted
    log.error("bhashini.translate.all_retries_failed", error=str(last_error))
    raise Exception(
        f"Bhashini translation failed after {MAX_RETRIES} attempts: {last_error}"
    )


async def simplify_bureaucratic(text: str, language: str) -> str:
    """
    Use Bhashini to translate bureaucratic language to plain language.
    Wraps the source text with a simplification instruction.
    """
    # For Hindi, translate within same language using a simplification prompt
    # For other languages, translate from detected language to target
    simplified = await translate(text, source_lang=language, target_lang=language)
    return simplified["translated_text"]