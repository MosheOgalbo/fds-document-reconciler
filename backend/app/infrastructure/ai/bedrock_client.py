from __future__ import annotations

import json
import logging
import re
from typing import Any

import boto3

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _extract_json_text(raw: str) -> str:
    content = raw.strip()
    if "```json" in content:
        content = content.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in content:
        content = content.split("```", 1)[1].split("```", 1)[0]
    match = re.search(r"\{[\s\S]*\}", content)
    return match.group(0) if match else content


def _is_nova_model(model_id: str) -> bool:
    return "nova" in model_id.lower()


class BedrockGateway:
    def __init__(self):
        self._settings = get_settings()
        self._session = boto3.Session(
            aws_access_key_id=self._settings.aws_access_key,
            aws_secret_access_key=self._settings.aws_secret_access_key,
            region_name=self._settings.aws_region,
        )
        self._client = self._session.client("bedrock-runtime")

    def _resolve_chat_model(self, model_tier: str) -> str:
        if model_tier == "fast" and self._settings.small_generative_model:
            return self._settings.small_generative_model
        return self._settings.generation_model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        embeddings = []
        for text in texts:
            body = json.dumps({"inputText": text})
            response = self._client.invoke_model(
                modelId=self._settings.embedding_model,
                body=body,
            )
            response_body = json.loads(response.get("body").read())
            embeddings.append(response_body.get("embedding"))
        return embeddings

    def _invoke_chat(self, model_id: str, system_prompt: str, user_prompt: str, temperature: float) -> str:
        if _is_nova_model(model_id):
            body = json.dumps(
                {
                    "system": [{"text": system_prompt}],
                    "messages": [{"role": "user", "content": [{"text": user_prompt}]}],
                    "inferenceConfig": {"maxTokens": 4096, "temperature": temperature},
                }
            )
            response = self._client.invoke_model(modelId=model_id, body=body)
            response_body = json.loads(response.get("body").read())
            return response_body["output"]["message"]["content"][0]["text"]

        body = json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4096,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
                "temperature": temperature,
            }
        )
        response = self._client.invoke_model(modelId=model_id, body=body)
        response_body = json.loads(response.get("body").read())
        return response_body.get("content", [])[0].get("text")

    async def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any],
        schema_name: str = "response",
        temperature: float = 0.1,
        model_tier: str = "smart",
    ) -> dict[str, Any]:
        model_id = self._resolve_chat_model(model_tier)
        schema_hint = ""
        if json_schema:
            schema_hint = f"\n\nReturn ONLY valid JSON matching this schema:\n{json.dumps(json_schema)}"
        content = self._invoke_chat(model_id, system_prompt, f"{user_prompt}{schema_hint}", temperature)
        return json.loads(_extract_json_text(content))
