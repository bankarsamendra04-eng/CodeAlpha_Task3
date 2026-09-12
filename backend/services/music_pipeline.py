"""
AI Music Studio - Complete End-to-End Music Generation Pipeline Service

Pipeline Execution Flow:
    1. User Input (Natural language prompt AND/OR explicit Advanced Controls)
          ↓
    2. Optional Groq Prompt Interpretation Service (if prompt provided)
          ↓
    3. Parameter Merging: Explicit User Controls strictly OVERRIDE Groq suggestions
          ↓
    4. Strict Backend Parameter Sanitization & Validation (Pydantic v2)
          ↓
    5. Trained MAESTRO LSTM Music Generator (Next-token prediction)
          ↓
    6. music21 Stream Assembly with Tempo, Instrument, Key, & Scale
          ↓
    7. MIDI Validation & Disk Export (output/midi/)
          ↓
    8. Optional WAV Audio Rendering via FluidSynth (output/audio/)
          ↓
    9. Safe Sanitized API Response (Zero internal path leakage)
"""

import os
import sys
import time
import uuid
import logging
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

# Ensure project root is available
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.config import (
    MIDI_OUTPUT_DIR,
    AUDIO_OUTPUT_DIR,
    MODEL_PATH,
    LSTM_MODEL_DIR,
)
from backend.database.models import User, Generation, GeneratedFile
from backend.schemas.music import (
    MusicGenerateRequest,
    MusicGenerateResponse,
    MusicParameters,
    GenerationMetadata,
    FileReference,
    LevelEnum,
)
from backend.services.groq_service import get_groq_service
from backend.services.usage_service import get_usage_service
from ml.generator import MusicGenerator
from ml.midi_generator import tokens_to_midi_file
from scripts.render_audio import convert_midi_to_wav

logger = logging.getLogger("ai_music_studio.pipeline")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


class MusicPipelineService:
    """Manages the full end-to-end AI music creation and rendering workflow."""

    def __init__(self):
        self.groq_service = get_groq_service()
        self._generator: Optional[MusicGenerator] = None

    def _get_generator(self) -> MusicGenerator:
        """Lazy-load or reuse the trained LSTM MusicGenerator."""
        if self._generator is None:
            best_model_path = LSTM_MODEL_DIR / "best_model.keras"
            model_file = "best_model.keras" if best_model_path.exists() else "model.keras"
            active_model = LSTM_MODEL_DIR / model_file
            if not active_model.exists():
                logger.error("LSTM Model file not found at: %s", active_model)
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="AI Music Generation Model is unavailable. Please verify model training has completed.",
                )

            try:
                logger.info("Initializing LSTM MusicGenerator using model: %s", active_model.name)
                self._generator = MusicGenerator(
                    model_dir=LSTM_MODEL_DIR,
                    model_filename=model_file,
                )
            except Exception as exc:
                logger.error("Failed to load LSTM model into memory: %s", exc)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to initialize music generation model. Please check model status with administrator.",
                )
        return self._generator

    def generate_music(
        self,
        request: MusicGenerateRequest,
        db: Optional[Session] = None,
        current_user: Optional[User] = None,
    ) -> MusicGenerateResponse:
        """
        Executes the full generation workflow merging natural-language interpretations
        with explicit user controls (explicit controls take absolute precedence),
        records the generation history in the database, and links to current_user if authenticated.
        """
        start_time_perf = time.time()
        raw_prompt = (request.prompt or "").strip()
        has_prompt = len(raw_prompt) >= 3

        # Must have either a valid prompt or at least one explicit advanced control
        has_controls = any(
            v is not None for v in (
                request.mood,
                request.instrument,
                request.tempo,
                request.duration_seconds,
                request.complexity,
                request.key,
                request.scale,
                request.temperature,
            )
        )

        if not has_prompt and not has_controls:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please provide either a music prompt or select advanced music controls.",
            )

        # SaaS Plan Limit & Quota Validation
        usage_service = get_usage_service()
        req_duration = request.duration_seconds if getattr(request, "duration_seconds", None) is not None else 60
        req_render_audio = bool(getattr(request, "render_audio", True))
        usage_service.validate_generation_request(
            user=current_user,
            requested_duration=req_duration,
            render_audio=req_render_audio,
            is_api=False,
            has_advanced_controls=has_controls,
            db=db,
            enforce_hard_limits=True,
        )

        gen_id = f"gen_{uuid.uuid4().hex[:12]}"
        logger.info("[%s] Initiating music generation (prompt: '%s', controls_provided: %s)", gen_id, raw_prompt, has_controls)

        # -------------------------------------------------------------
        # STEP 1: Parse Base Parameters from Prompt (or defaults)
        # -------------------------------------------------------------
        if has_prompt:
            try:
                prompt_res = self.groq_service.interpret_prompt(raw_prompt)
                base_params = prompt_res.parameters
                suggested_temp = prompt_res.suggested_temperature
                suggested_events = prompt_res.suggested_num_events
                parser_mode = "fallback_heuristics" if prompt_res.fallback_used else "groq_llm"
            except Exception as exc:
                logger.warning("[%s] Prompt interpretation failed (%s). Using defaults.", gen_id, exc)
                base_params = MusicParameters()
                suggested_temp = 0.85
                suggested_events = 64
                parser_mode = "default_fallback"
        else:
            base_params = MusicParameters()
            suggested_temp = 0.85
            suggested_events = 64
            parser_mode = "manual_controls_only"

        # -------------------------------------------------------------
        # STEP 2: Merge User Controls (Explicit Overrides Groq)
        # -------------------------------------------------------------
        overrides_applied: Dict[str, Any] = {}
        merged_dict = base_params.model_dump()

        if request.mood:
            merged_dict["mood"] = request.mood
            overrides_applied["mood"] = request.mood

        if request.instrument:
            merged_dict["instrument"] = request.instrument
            overrides_applied["instrument"] = request.instrument

        if request.tempo is not None:
            merged_dict["tempo"] = request.tempo
            overrides_applied["tempo"] = request.tempo

        if request.duration_seconds is not None:
            merged_dict["duration_seconds"] = request.duration_seconds
            overrides_applied["duration_seconds"] = request.duration_seconds

        if request.complexity is not None:
            merged_dict["complexity"] = request.complexity
            overrides_applied["complexity"] = request.complexity

        if request.key:
            merged_dict["key"] = request.key
            overrides_applied["key"] = request.key

        if request.scale:
            merged_dict["scale"] = request.scale
            overrides_applied["scale"] = request.scale

        # Validate merged parameters strictly
        final_music_params = MusicParameters(**merged_dict)

        # -------------------------------------------------------------
        # STEP 3: Resolve Hyperparameters (Temperature & Num Events)
        # -------------------------------------------------------------
        # Explicit temperature takes precedence
        if request.temperature is not None:
            temperature = float(request.temperature)
            overrides_applied["temperature"] = temperature
        else:
            temperature = suggested_temp

        temperature = max(0.1, min(2.0, round(temperature, 2)))

        # Explicit num events override or calculated based on duration & tempo
        if request.num_events_override is not None:
            num_events = int(request.num_events_override)
            overrides_applied["num_events"] = num_events
        else:
            # Recalculate based on final duration and tempo
            beats = (final_music_params.duration_seconds / 60.0) * final_music_params.tempo
            num_events = int(beats * 1.5)
            num_events = max(16, min(500, num_events))

        logger.info(
            "[%s] Final Merged Params: tempo=%.1f, inst=%s, key=%s %s, mood=%s, temp=%.2f, events=%d (Overrides: %s)",
            gen_id,
            final_music_params.tempo,
            final_music_params.instrument,
            final_music_params.key,
            final_music_params.scale,
            final_music_params.mood,
            temperature,
            num_events,
            list(overrides_applied.keys()),
        )

        # -------------------------------------------------------------
        # STEP 4: LSTM Music Generation
        # -------------------------------------------------------------
        generator = self._get_generator()
        try:
            logger.info(
                "[%s] Predicting %d musical tokens (temp=%.2f, seed=%s)...",
                gen_id,
                num_events,
                temperature,
                request.random_seed,
            )
            tokens = generator.generate(
                num_events=num_events,
                temperature=temperature,
                random_seed=request.random_seed,
            )
        except Exception as exc:
            logger.error("[%s] LSTM token generation failed: %s", gen_id, exc)
            if db is not None:
                try:
                    fail_rec = Generation(
                        generation_id=gen_id,
                        user_id=current_user.id if current_user else None,
                        prompt=raw_prompt or None,
                        prompt_parser=parser_mode,
                        interpreted_parameters=final_music_params.model_dump(),
                        user_overrides=overrides_applied,
                        model_version="lstm_v1",
                        tempo_bpm=final_music_params.tempo,
                        instrument=final_music_params.instrument,
                        musical_key=final_music_params.key,
                        scale=final_music_params.scale,
                        temperature=temperature,
                        generation_status="failed",
                        generation_duration_ms=int((time.time() - start_time_perf) * 1000),
                        error_info=f"LSTM inference error: {str(exc)}",
                    )
                    db.add(fail_rec)
                    db.commit()
                except Exception:
                    db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Symbolic music generator encountered an error during inference.",
            )

        # -------------------------------------------------------------
        # STEP 5 & 6: music21 Stream Assembly & MIDI Creation
        # -------------------------------------------------------------
        clean_inst_slug = final_music_params.instrument.replace(" ", "_")
        midi_filename = f"{gen_id}_{clean_inst_slug}.mid"
        midi_target_path = MIDI_OUTPUT_DIR / midi_filename

        try:
            exported_midi_path, midi_val = tokens_to_midi_file(
                tokens=tokens,
                output_path=midi_target_path,
                tempo_bpm=final_music_params.tempo,
                instrument_name=final_music_params.instrument,
                key=final_music_params.key,
                scale=final_music_params.scale,
                title=f"AI Studio - {final_music_params.mood.capitalize()} {final_music_params.style.capitalize()}",
            )
            midi_size = exported_midi_path.stat().st_size
            logger.info(
                "[%s] MIDI created successfully (%d bytes, %d notes, %d chords, %.2f quarters)",
                gen_id,
                midi_size,
                midi_val["total_notes"],
                midi_val["total_chords"],
                midi_val["duration_quarters"],
            )
        except Exception as exc:
            logger.error("[%s] MIDI file creation failed: %s", gen_id, exc)
            if db is not None:
                try:
                    fail_rec = Generation(
                        generation_id=gen_id,
                        user_id=current_user.id if current_user else None,
                        prompt=raw_prompt or None,
                        prompt_parser=parser_mode,
                        interpreted_parameters=final_music_params.model_dump(),
                        user_overrides=overrides_applied,
                        model_version="lstm_v1",
                        tempo_bpm=final_music_params.tempo,
                        instrument=final_music_params.instrument,
                        musical_key=final_music_params.key,
                        scale=final_music_params.scale,
                        temperature=temperature,
                        generation_status="failed",
                        generation_duration_ms=int((time.time() - start_time_perf) * 1000),
                        error_info=f"MIDI synthesis error: {str(exc)}",
                    )
                    db.add(fail_rec)
                    db.commit()
                except Exception:
                    db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to synthesize valid MIDI from generated music.",
            )

        midi_ref = FileReference(
            filename=midi_filename,
            download_url=f"/api/music/download/midi/{midi_filename}",
            file_type="midi",
            size_bytes=midi_size,
        )

        # -------------------------------------------------------------
        # STEP 7: Optional WAV Audio Synthesis via FluidSynth
        # -------------------------------------------------------------
        audio_ref: Optional[FileReference] = None
        audio_status = "skipped"

        if request.render_audio:
            wav_filename = f"{gen_id}_{clean_inst_slug}.wav"
            wav_target_path = AUDIO_OUTPUT_DIR / wav_filename

            logger.info("[%s] Attempting audio rendering via FluidSynth...", gen_id)
            try:
                audio_ok, out_wav_path, audio_info = convert_midi_to_wav(
                    midi_path=exported_midi_path,
                    output_wav_path=wav_target_path,
                )

                if audio_ok and out_wav_path and out_wav_path.exists():
                    audio_size = out_wav_path.stat().st_size
                    audio_status = "rendered"
                    audio_ref = FileReference(
                        filename=wav_filename,
                        download_url=f"/api/music/download/audio/{wav_filename}",
                        file_type="audio",
                        size_bytes=audio_size,
                    )
                    logger.info("[%s] Audio rendering succeeded (%d bytes)", gen_id, audio_size)
                else:
                    if audio_info.get("status") == "renderer_unavailable":
                        audio_status = "renderer_unavailable"
                        logger.info("[%s] Audio rendering unavailable (FluidSynth/SoundFont not configured).", gen_id)
                    else:
                        audio_status = "rendering_failed"
                        logger.warning("[%s] Audio synthesis failed: %s", gen_id, audio_info.get("error"))
            except Exception as exc:
                audio_status = "rendering_failed"
                logger.warning("[%s] Audio rendering raised unexpected error: %s", gen_id, exc)

        # -------------------------------------------------------------
        # STEP 8: Construct Sanitized Response & Persist to Database
        # -------------------------------------------------------------
        duration_ms = int((time.time() - start_time_perf) * 1000)

        metadata = GenerationMetadata(
            prompt=raw_prompt or "Manual advanced controls",
            interpreted_parameters=final_music_params,
            user_overrides_applied=overrides_applied,
            prompt_parser=parser_mode,
            temperature_used=temperature,
            num_events_generated=len(tokens),
            duration_quarter_lengths=midi_val["duration_quarters"],
            notes_count=midi_val["total_notes"],
            chords_count=midi_val["total_chords"],
            rests_count=midi_val["total_rests"],
            tempo_bpm=final_music_params.tempo,
            instrument=final_music_params.instrument,
            key=final_music_params.key,
            scale=final_music_params.scale,
        )

        success_msg = f"Music composed successfully ({len(tokens)} events, {metadata.duration_quarter_lengths:.1f} bars)."
        if audio_status == "renderer_unavailable":
            success_msg += " (Audio renderer unavailable; MIDI generated and ready for download)."

        # Save to Database if session is available
        if db is not None:
            try:
                gen_record = Generation(
                    generation_id=gen_id,
                    user_id=current_user.id if current_user else None,
                    prompt=raw_prompt or None,
                    prompt_parser=parser_mode,
                    interpreted_parameters=final_music_params.model_dump(),
                    user_overrides=overrides_applied,
                    model_version="lstm_v1",
                    tempo_bpm=final_music_params.tempo,
                    instrument=final_music_params.instrument,
                    musical_key=final_music_params.key,
                    scale=final_music_params.scale,
                    temperature=temperature,
                    random_seed=request.random_seed,
                    num_events_generated=len(tokens),
                    duration_quarter_lengths=midi_val["duration_quarters"],
                    generation_status="completed",
                    generation_duration_ms=duration_ms,
                    midi_file_name=midi_filename,
                    midi_file_url=midi_ref.download_url,
                    midi_size_bytes=midi_size,
                    audio_status=audio_status,
                    audio_file_name=audio_ref.filename if audio_ref else None,
                    audio_file_url=audio_ref.download_url if audio_ref else None,
                    audio_size_bytes=audio_ref.size_bytes if audio_ref else 0,
                )
                db.add(gen_record)
                db.flush()

                # Add file entries
                midi_file_record = GeneratedFile(
                    generation_id=gen_record.id,
                    file_type="midi",
                    filename=midi_filename,
                    download_url=midi_ref.download_url,
                    file_size_bytes=midi_size,
                    mime_type="audio/midi",
                )
                db.add(midi_file_record)

                if audio_ref:
                    audio_file_record = GeneratedFile(
                        generation_id=gen_record.id,
                        file_type="audio_wav",
                        filename=audio_ref.filename,
                        download_url=audio_ref.download_url,
                        file_size_bytes=audio_ref.size_bytes,
                        mime_type="audio/wav",
                    )
                    db.add(audio_file_record)

                db.commit()
                logger.info("[%s] Saved generation record to database (duration: %d ms)", gen_id, duration_ms)

                # Record SaaS usage counters
                total_storage = midi_size + (audio_ref.size_bytes if audio_ref else 0)
                usage_service.record_usage(
                    user=current_user,
                    duration_sec=midi_val.get("duration_seconds", float(final_music_params.duration_seconds)),
                    audio_rendered=(audio_ref is not None),
                    storage_bytes=total_storage,
                    is_api=False,
                    db=db,
                )
            except Exception as db_exc:
                db.rollback()
                logger.error("[%s] Failed to record generation in database: %s", gen_id, db_exc)

        return MusicGenerateResponse(
            success=True,
            generation_id=gen_id,
            metadata=metadata,
            midi_file=midi_ref,
            audio_file=audio_ref,
            audio_status=audio_status,
            message=success_msg,
        )


# Singleton pipeline instance
_pipeline_instance: Optional[MusicPipelineService] = None


def get_music_pipeline() -> MusicPipelineService:
    """Retrieve global MusicPipelineService instance."""
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = MusicPipelineService()
    return _pipeline_instance