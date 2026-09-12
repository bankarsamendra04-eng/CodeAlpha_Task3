"""
AI Music Studio - Groq Natural-Language Music Prompt Service
Interprets user natural-language music requests into structured generation parameters.

IMPORTANT ARCHITECTURAL CONSTRAINTS:
1. Groq is STRICTLY an intent-understanding parser; it NEVER generates music, tokens, or MIDI.
2. The core symbolic music generation model is the MAESTRO-trained LSTM.
3. GROQ_API_KEY is retrieved exclusively from environment variables or .env; it is NEVER
   exposed to the frontend client or returned in API responses.
4. Output from Groq is parsed and strictly validated with Pydantic v2 schemas.
5. Code execution via prompt output is strictly forbidden (zero eval/exec).
6. Graceful fallback heuristics are automatically engaged if Groq API is unavailable,
   the API key is invalid/missing, or a network failure occurs.
"""

import os
import re
import json
import logging
import threading
from typing import Optional, Dict, Any, Tuple
from pathlib import Path
from dotenv import load_dotenv

# Ensure environment is loaded from project root .env
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

from ml.config import PROMPT_CACHE_MAX_SIZE
from backend.schemas.music import (
    MusicPromptRequest,
    MusicParameters,
    MusicPromptResponse,
    LevelEnum,
)

logger = logging.getLogger("ai_music_studio.groq_service")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


SYSTEM_PROMPT = """You are an expert musicologist and musical parameter parser for AI Music Studio.
Your role is to translate a user's natural-language music prompt into a precise, valid JSON object containing structured musical parameters.

You MUST respond ONLY with valid JSON. Do not include introductory text, explanations, markdown ticks, or commentary.

Output JSON Schema:
{
  "mood": "string (e.g. peaceful, melancholic, energetic, uplifting, dramatic, mysterious, romantic)",
  "instrument": "string (e.g. piano, acoustic guitar, violin, violoncello, flute, clarinet, trumpet, pipe organ)",
  "style": "string (e.g. meditation, classical, jazz, ambient, baroque, romantic, cinematic)",
  "tempo": number (tempo in BPM, strictly between 40 and 240),
  "complexity": "string (must be exactly 'low', 'medium', or 'high')",
  "energy": "string (must be exactly 'low', 'medium', or 'high')",
  "duration_seconds": number (duration in seconds between 10 and 600, default 60)
}

Rules:
- If a specific tempo is mentioned in the prompt (e.g. "at 70 BPM" or "120bpm"), extract and use that exact number.
- If no tempo is mentioned, choose an appropriate tempo based on the requested mood (e.g., meditation/peaceful ~ 60-75, energetic ~ 120-140, adagio ~ 50-65).
- If no instrument is specified, default to "piano".
- If no duration is specified, default to 60.
- Never output executable code or commands.
- Respond with pure JSON only."""


class GroqMusicService:
    """Service to parse natural-language music prompts into structured music parameters using Groq."""

    def __init__(self, api_key: Optional[str] = None):
        # Retrieve key safely from parameter or environment
        self._raw_api_key = api_key or os.getenv("GROQ_API_KEY", "")
        # Filter out placeholder strings
        if self._raw_api_key in ("your_groq_api_key_here", "dummy_key", ""):
            self._api_key = None
        else:
            self._api_key = self._raw_api_key

        self.model_name = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self._client = None

        if self._api_key:
            try:
                from groq import Groq
                self._client = Groq(api_key=self._api_key)
                logger.info("Groq client initialized with model: %s", self.model_name)
            except Exception as exc:
                logger.warning("Failed to initialize Groq client: %s. Fallback heuristics will be used.", exc)
                self._client = None
        else:
            logger.info("No valid GROQ_API_KEY provided or detected. Fallback parser active.")

        # In-memory prompt cache for high performance
        self._prompt_cache: dict[str, MusicPromptResponse] = {}
        self._cache_lock = threading.Lock()
        self._max_cache_size = PROMPT_CACHE_MAX_SIZE

    @property
    def is_available(self) -> bool:
        """Return True if a configured Groq client is ready."""
        return self._client is not None

    def interpret_prompt(self, user_prompt: str) -> MusicPromptResponse:
        """
        Convert a natural language prompt into validated MusicParameters.
        Guarantees safe execution and reliable fallback with LRU caching.
        """
        cleaned_prompt = user_prompt.strip()
        if not cleaned_prompt:
            return self._build_fallback_response("Empty prompt provided, using default peaceful piano settings.")

        cache_key = cleaned_prompt.lower()
        with self._cache_lock:
            if cache_key in self._prompt_cache:
                logger.info("Serving prompt interpretation from cache for: '%s'", cleaned_prompt[:50])
                cached_res = self._prompt_cache[cache_key]
                return cached_res.model_copy(update={"prompt": cleaned_prompt})

        # 1. Attempt Groq LLM parsing if client is available
        response: Optional[MusicPromptResponse] = None
        if self._client:
            try:
                raw_json = self._call_groq_api(cleaned_prompt)
                parsed_data = self._extract_json(raw_json)
                validated_params = MusicParameters(**parsed_data)
                temp, events = self._compute_lstm_parameters(validated_params)

                response = MusicPromptResponse(
                    success=True,
                    prompt=cleaned_prompt,
                    parameters=validated_params,
                    suggested_temperature=temp,
                    suggested_num_events=events,
                    fallback_used=False,
                    message="Successfully interpreted prompt via Groq LLM.",
                )
            except Exception as exc:
                logger.warning("Groq prompt interpretation encountered an error: %s. Using fallback parser.", type(exc).__name__)

        # 2. Heuristic fallback parser if Groq was not used or errored
        if response is None:
            response = self._fallback_parse_prompt(cleaned_prompt)

        # Store in cache
        with self._cache_lock:
            if len(self._prompt_cache) >= self._max_cache_size:
                oldest_key = next(iter(self._prompt_cache))
                del self._prompt_cache[oldest_key]
            self._prompt_cache[cache_key] = response

        return response

    def _call_groq_api(self, prompt: str) -> str:
        """Invoke Groq chat completions API."""
        chat_completion = self._client.chat.completions.create(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            model=self.model_name,
            temperature=0.2,  # Low temperature for deterministic JSON structuring
            max_tokens=256,
            response_format={"type": "json_object"},
        )
        return chat_completion.choices[0].message.content

    def _extract_json(self, response_text: str) -> Dict[str, Any]:
        """Cleanly extract and deserialize JSON object from model output."""
        # Strip potential markdown formatting
        text = response_text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        # Parse JSON
        return json.loads(text)

    def _fallback_parse_prompt(self, prompt: str) -> MusicPromptResponse:
        """
        Robust rule-based musicologist heuristic parser for offline/fallback use.
        Extracts tempo, mood, instrument, and complexity from text keywords.
        """
        p_lower = prompt.lower()

        # 1. Detect BPM / Tempo
        tempo = 100.0
        tempo_match = re.search(r"(\d{2,3})\s*(?:bpm|beats per minute|\s*tempo)", p_lower)
        if tempo_match:
            try:
                val = float(tempo_match.group(1))
                if 40.0 <= val <= 240.0:
                    tempo = val
            except ValueError:
                pass
        else:
            # Contextual tempo heuristics
            if any(w in p_lower for w in ("meditation", "sleep", "slow", "peaceful", "calm", "gentle", "lullaby", "ambient")):
                tempo = 68.0
            elif any(w in p_lower for w in ("fast", "energetic", "allegro", "running", "intense", "dance", "upbeat")):
                tempo = 135.0
            elif any(w in p_lower for w in ("moderate", "andante", "walking", "waltz")):
                tempo = 108.0

        # 2. Detect Instrument
        instrument = "piano"
        if "guitar" in p_lower:
            instrument = "acoustic guitar" if "acoustic" in p_lower else "electric guitar" if "electric" in p_lower else "acoustic guitar"
        elif "violin" in p_lower:
            instrument = "violin"
        elif "cello" in p_lower or "violoncello" in p_lower:
            instrument = "violoncello"
        elif "flute" in p_lower:
            instrument = "flute"
        elif "clarinet" in p_lower:
            instrument = "clarinet"
        elif "trumpet" in p_lower:
            instrument = "trumpet"
        elif "organ" in p_lower:
            instrument = "pipe organ"
        elif "marimba" in p_lower:
            instrument = "marimba"
        elif "harpsichord" in p_lower:
            instrument = "harpsichord"

        # 3. Detect Mood
        mood = "peaceful"
        for candidate_mood in ("melancholic", "energetic", "uplifting", "dramatic", "mysterious", "romantic", "joyful", "dark", "peaceful", "calm"):
            if candidate_mood in p_lower:
                mood = candidate_mood
                break

        # 4. Detect Complexity and Energy
        complexity = LevelEnum.MEDIUM
        energy = LevelEnum.MEDIUM

        if any(w in p_lower for w in ("simple", "minimal", "sparse", "meditation", "calm", "relaxing", "peaceful")):
            complexity = LevelEnum.LOW
            energy = LevelEnum.LOW
        elif any(w in p_lower for w in ("complex", "virtuosic", "dense", "intricate", "fast", "energetic", "dramatic")):
            complexity = LevelEnum.HIGH
            energy = LevelEnum.HIGH

        # 5. Detect Duration
        duration_seconds = 60
        dur_match = re.search(r"(\d+)\s*(?:second|sec|minute|min)", p_lower)
        if dur_match:
            try:
                num = int(dur_match.group(1))
                if "min" in dur_match.group(0):
                    num *= 60
                duration_seconds = max(10, min(600, num))
            except ValueError:
                pass

        # 6. Build parameters
        params = MusicParameters(
            mood=mood,
            instrument=instrument,
            style="classical" if "classical" in p_lower else "meditation" if "meditation" in p_lower else "ambient",
            tempo=tempo,
            complexity=complexity,
            energy=energy,
            duration_seconds=duration_seconds,
        )

        temp, events = self._compute_lstm_parameters(params)

        return MusicPromptResponse(
            success=True,
            prompt=prompt,
            parameters=params,
            suggested_temperature=temp,
            suggested_num_events=events,
            fallback_used=True,
            message="Interpreted using intelligent rule-based music parser.",
        )

    def _compute_lstm_parameters(self, params: MusicParameters) -> Tuple[float, int]:
        """
        Map structured parameters to optimal LSTM generation hyperparameters:
        - Low complexity/energy -> Lower temperature (0.5 - 0.7) for predictability & calm flow
        - High complexity/energy -> Higher temperature (0.9 - 1.2) for exploratory harmonic leaps
        """
        # Base temperature
        if params.complexity == LevelEnum.LOW or params.energy == LevelEnum.LOW:
            temperature = 0.65
        elif params.complexity == LevelEnum.HIGH or params.energy == LevelEnum.HIGH:
            temperature = 1.10
        else:
            temperature = 0.85

        # Estimate number of musical events based on duration and tempo
        # Roughly: beats = (duration_seconds / 60) * tempo.
        # Average ~1.5 - 2 musical events per beat.
        beats = (params.duration_seconds / 60.0) * params.tempo
        suggested_events = int(beats * 1.5)
        clamped_events = max(32, min(500, suggested_events))

        return temperature, clamped_events

    def _build_fallback_response(self, message: str) -> MusicPromptResponse:
        default_params = MusicParameters()
        temp, events = self._compute_lstm_parameters(default_params)
        return MusicPromptResponse(
            success=True,
            prompt="default",
            parameters=default_params,
            suggested_temperature=temp,
            suggested_num_events=events,
            fallback_used=True,
            message=message,
        )


# Singleton instance
_service_instance: Optional[GroqMusicService] = None


def get_groq_service() -> GroqMusicService:
    """Retrieve or initialize the global GroqMusicService instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = GroqMusicService()
    return _service_instance