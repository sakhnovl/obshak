import logging
import os
import re

from dotenv import load_dotenv
from google import genai
from google.genai import types

from database.db import db

load_dotenv()

logger = logging.getLogger(__name__)


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
        instruction = (
            "Return only the final user-facing answer. "
            "Do not include reasoning, analysis, hidden thinking, bullet-point deliberation, "
            "or service notes. Respond as a normal chat message."
        )
        return types.Content(
            role="user",
            parts=[types.Part.from_text(text=f"{instruction}\n\nUser message:\n{current_message}")],
        )

    def build_generation_config(self):
        return types.GenerateContentConfig(
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True
            )
        )

    def sanitize_response(self, response_text):
        text = response_text.strip()
        if not text:
            return text

        text = re.sub(r"<think>.*?</think>", "", text, flags=re.IGNORECASE | re.DOTALL).strip()
        if not text:
            return text

        bullet_markers = ("*", "-", "•")
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
        final_paragraph = paragraphs[-1] if paragraphs else text

        def extract_final_line(chunk):
            chunk_lines = [line.strip() for line in chunk.splitlines() if line.strip()]
            if not chunk_lines:
                return chunk.strip()

            for line in reversed(chunk_lines):
                if not any(line.startswith(marker) for marker in bullet_markers):
                    return line

            return chunk_lines[-1]

        if len(paragraphs) > 1:
            analysis_like = any(
                any(line.lstrip().startswith(marker) for line in part.splitlines() for marker in bullet_markers)
                for part in paragraphs[:-1]
            )
            if analysis_like:
                return extract_final_line(final_paragraph)

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if len(lines) > 1 and any(
            line.startswith(marker) for line in lines[:-1] for marker in bullet_markers
        ):
            return extract_final_line(text)

        return text

    async def get_response(self, user_id, current_message, history):
        await self._ensure_initialized()
        contents = [*self.format_history(history), self.build_prompt(current_message)]
        config = self.build_generation_config()
        last_error = None

        for key_index, client in enumerate(self.clients):
            for model_index, model_name in enumerate(self.model_names):
                try:
                    response = await client.aio.models.generate_content(
                        model=model_name,
                        contents=contents,
                        config=config,
                    )
                    return self.sanitize_response(response.text or "")
                except Exception as exc:
                    last_error = exc
                    has_key_fallback = key_index < len(self.clients) - 1
                    has_model_fallback = model_index < len(self.model_names) - 1

                    if has_key_fallback or has_model_fallback:
                        logger.warning(
                            "Gemini key %d, model '%s' failed, trying next: %s",
                            key_index, model_name, exc,
                        )
                    else:
                        logger.error(
                            "Gemini key %d, model '%s' failed with no fallback left: %s",
                            key_index, model_name, exc,
                        )

        if last_error is None:
            raise RuntimeError("No Gemini models configured")

        raise last_error


def get_ai_agent():
    return GeminiAI()
