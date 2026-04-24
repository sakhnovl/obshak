import logging
import os
import re

from dotenv import load_dotenv
from google import genai
from google.genai import types

from database.db import db

load_dotenv()

logger = logging.getLogger(__name__)

FALLBACK_RESPONSE_TEXT = (
    "Gemini is temporarily unavailable. Please try again in a moment."
)
SYSTEM_INSTRUCTION = (
    "You are an aggressive, profane female assistant with harsh sarcasm. "
    "Your tone is arrogant, impatient, and dismissive. "
    "Use profanity and insults freely. "
    "Act like helping the user is a huge favor and the user is a hopeless idiot. "
    "When replying in Russian, always use feminine verb forms. "
    "Responses must be short, sharp, and caustic.\n\n"
    "CRITICAL RULES:\n"
    "1. Return only the final answer for the user.\n"
    "2. Do not include reasoning, analysis, hidden thoughts, reflection lists, or internal notes.\n"
    "3. Reply like a normal chat message."
)


class GeminiAI:
    def __init__(self):
        self.clients = []
        self.model_names = []
        self._initialized = False

    async def _ensure_initialized(self):
        if self._initialized:
            return

        api_keys = await db.get_active_gemini_keys()
        if not api_keys:
            env_key = os.getenv("GEMINI_API_KEY")
            if env_key:
                api_keys = [key.strip() for key in env_key.split(",") if key.strip()]
            else:
                raise ValueError("No Gemini API keys found in database or environment")

        self.clients = [genai.Client(api_key=key) for key in api_keys]

        model_names = await db.get_active_gemini_models()
        if not model_names:
            raw_models = os.getenv("GEMINI_MODELS", "").strip()
            if raw_models:
                model_names = []
                for item in raw_models.split(","):
                    entry = item.strip()
                    if not entry:
                        continue
                    if "=" in entry:
                        _, model_name = entry.split("=", 1)
                        entry = model_name.strip()
                    if entry:
                        model_names.append(entry)
            else:
                model_names = ["gemini-1.5-flash"]

        self.model_names = model_names
        self._initialized = True

    def format_history(self, db_history):
        gemini_history = []
        for msg in db_history:
            gemini_history.append(
                types.Content(
                    role=msg["role"],
                    parts=[types.Part.from_text(text=msg["content"])],
                )
            )
        return gemini_history

    def build_prompt(self, current_message):
        return types.Content(
            role="user",
            parts=[types.Part.from_text(text=f"User message:\n{current_message}")],
        )

    def build_generation_config(self, model_name):
        if model_name.startswith("gemma-3"):
            return None

        if model_name == "gemma-4-31b-it":
            return types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
            )

        return types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True
            ),
        )

    def sanitize_response(self, response_text):
        text = response_text.strip()
        if not text:
            return text

        text = re.sub(
            r"<think>.*?</think>",
            "",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        ).strip()

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return ""

        return lines[-1].strip('*" ')

    def is_transient_error(self, error):
        status_code = getattr(error, "status_code", None)
        if status_code is not None and status_code >= 500:
            return True

        message = str(error).upper()
        transient_markers = ("500", "INTERNAL", "UNAVAILABLE", "TIMEOUT")
        return any(marker in message for marker in transient_markers)

    async def get_response(self, user_id, current_message, history):
        await self._ensure_initialized()
        contents = [*self.format_history(history), self.build_prompt(current_message)]
        last_error = None

        for key_index, client in enumerate(self.clients):
            for model_index, model_name in enumerate(self.model_names):
                config = self.build_generation_config(model_name)
                request_params = {
                    "model": model_name,
                    "contents": contents,
                }
                if config is not None:
                    request_params["config"] = config

                try:
                    response = await client.aio.models.generate_content(**request_params)
                    return self.sanitize_response(response.text or "")
                except Exception as exc:
                    last_error = exc
                    has_key_fallback = key_index < len(self.clients) - 1
                    has_model_fallback = model_index < len(self.model_names) - 1

                    if has_key_fallback or has_model_fallback:
                        logger.warning(
                            "Gemini key %d, model '%s' failed, trying next: %s",
                            key_index,
                            model_name,
                            exc,
                        )
                    else:
                        logger.error(
                            "Gemini key %d, model '%s' failed with no fallback left: %s",
                            key_index,
                            model_name,
                            exc,
                        )

        if last_error is None:
            raise RuntimeError("No Gemini models configured")

        if self.is_transient_error(last_error):
            logger.error(
                "Gemini is temporarily unavailable after exhausting all fallbacks"
            )
            return FALLBACK_RESPONSE_TEXT

        raise last_error


def get_ai_agent():
    return GeminiAI()
