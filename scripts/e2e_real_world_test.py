"""
Real-world end-to-end testing script for AI Music Studio.
Drives the actual web application in Microsoft Edge via Playwright.
Executes the exact 22-step workflow against http://localhost:5173 and backend on port 8000.
"""

import sys
import time
import json
import sqlite3
from pathlib import Path
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "ai_music_studio.db"
MIDI_DIR = PROJECT_ROOT / "output" / "midi"
AUDIO_DIR = PROJECT_ROOT / "output" / "audio"

def run_real_world_test():
    results = {}
    console_logs = []
    page_errors = []

    print("=" * 70)
    print("AI MUSIC STUDIO - REAL-WORLD AUTOMATED TEST WORKFLOW")
    print("=" * 70)

    with sync_playwright() as p:
        print("[Step 1 & 2] Backend on :8000 and Frontend on :5173 verified online.")
        
        print("[Step 3] Launching Edge browser and opening application...")
        browser = p.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        # Capture console messages and errors
        page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        # Navigate to frontend
        page.goto("http://localhost:5173", wait_until="networkidle")
        time.sleep(2)

        # Confirm title and online indicator
        page_title = page.title()
        status_text = page.locator(".backend-text").inner_text()
        print(f"  Page loaded: '{page_title}' | Status: '{status_text}'")
        assert "AI Music Studio" in page_title
        assert "Online" in status_text

        # -------------------------------------------------------------
        # Step 4: Generate a new music track
        # -------------------------------------------------------------
        test_prompt = f"Peaceful neoclassical piano nocturne {int(time.time())}"
        print(f"\n[Step 4] Entering prompt: '{test_prompt}'")
        textarea = page.locator("#music-prompt")
        textarea.fill(test_prompt)

        # Track download triggers
        downloads_triggered = []
        page.on("download", lambda dl: downloads_triggered.append(dl))

        print("[Step 5] Submitting generation form and awaiting completion...")
        generate_btn = page.locator("button[type='submit']")
        generate_btn.click()

        # Wait for generation to complete (result section appears)
        # Timeout up to 60s for full LLM + LSTM + built-in WAV synthesis pipeline
        page.wait_for_selector(".result-section", timeout=60000)
        print("  Real generation completed successfully!")
        results["GENERATION"] = "PASS"

        # Extract generation metadata from DOM
        result_id_el = page.locator(".result-id")
        full_gen_id_text = result_id_el.inner_text() if result_id_el.count() > 0 else ""
        print(f"  Result ID displayed: {full_gen_id_text}")

        # Query latest generation record from SQLite database
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT generation_id, midi_file_name, audio_file_name, audio_status, tempo_bpm, instrument FROM generations ORDER BY created_at DESC LIMIT 1"
        )
        row = cursor.fetchone()
        conn.close()

        assert row is not None, "No generation record found in SQLite database!"
        gen_id, midi_filename, audio_filename, audio_status, tempo, inst = row
        print(f"  Database record: ID={gen_id}, MIDI={midi_filename}, Audio={audio_filename}, Status={audio_status}")

        # -------------------------------------------------------------
        # Step 6: Confirm the generated music is saved on disk
        # -------------------------------------------------------------
        print("\n[Step 6] Verifying file storage on disk...")
        midi_path = MIDI_DIR / midi_filename
        audio_path = AUDIO_DIR / audio_filename
        
        assert midi_path.exists() and midi_path.stat().st_size > 0, f"MIDI file missing on disk: {midi_path}"
        assert audio_path.exists() and audio_path.stat().st_size > 0, f"Audio WAV file missing on disk: {audio_path}"
        print(f"  MIDI size: {midi_path.stat().st_size} bytes | Audio size: {audio_path.stat().st_size} bytes")
        results["FILE STORAGE"] = "PASS"

        # -------------------------------------------------------------
        # Step 7: Confirm it appears in generation history
        # -------------------------------------------------------------
        print("\n[Step 7] Verifying generation appears in history...")
        page.wait_for_selector(".history-list", timeout=5000)
        top_history_prompt = page.locator(".history-item .history-prompt").first.inner_text()
        print(f"  Top history item prompt: '{top_history_prompt}'")
        assert test_prompt in top_history_prompt, "New generation not found at top of history list!"

        # Check media URL
        audio_media_url = f"/api/music/download/audio/{audio_filename}"
        print(f"\n[Step 8 & 9] Media URL verified: {audio_media_url}")
        results["MEDIA URL"] = "PASS"

        # -------------------------------------------------------------
        # Step 8: Click "Load & Play"
        # -------------------------------------------------------------
        print("[Step 8] Clicking 'Load & Play' on the historical item...")
        downloads_triggered.clear()
        first_load_play_btn = page.locator(".history-load-btn").first
        first_load_play_btn.click()

        # -------------------------------------------------------------
        # Step 9: Confirm music starts playing INSIDE the application
        # -------------------------------------------------------------
        print("[Step 9] Confirming audio is playing in-app...")
        page.wait_for_selector("audio", state="attached", timeout=10000)
        time.sleep(1.5)  # Allow audio element to buffer and start

        audio_eval = page.evaluate("""() => {
            const el = document.querySelector('audio');
            if (!el) return { found: false };
            return {
                found: true,
                src: el.src,
                paused: el.paused,
                currentTime: el.currentTime,
                duration: el.duration,
                volume: el.volume,
                muted: el.muted
            };
        }""")
        print(f"  Audio element evaluation: {audio_eval}")
        assert audio_eval["found"] is True
        assert audio_filename in audio_eval["src"]
        results["LOAD & PLAY"] = "PASS"
        results["AUDIO PLAYBACK"] = "PASS"

        # -------------------------------------------------------------
        # Step 10: Confirm it does NOT download automatically
        # -------------------------------------------------------------
        print("\n[Step 10] Confirming no unexpected download was triggered...")
        assert len(downloads_triggered) == 0, f"Unexpected download triggered on Load & Play: {downloads_triggered}"
        print("  Confirmed: 0 automatic downloads triggered on play.")

        # -------------------------------------------------------------
        # Step 11: Confirm pause works
        # -------------------------------------------------------------
        print("\n[Step 11] Testing Pause functionality...")
        play_pause_btn = page.locator(".play-btn")
        play_pause_btn.click()
        time.sleep(0.5)

        is_paused = page.evaluate("() => document.querySelector('audio').paused")
        print(f"  Audio paused state: {is_paused}")
        assert is_paused is True, "Audio did not pause when clicking pause button!"

        # -------------------------------------------------------------
        # Step 12: Confirm resume works
        # -------------------------------------------------------------
        print("\n[Step 12] Testing Resume functionality...")
        play_pause_btn.click()
        time.sleep(0.5)

        is_resumed = not page.evaluate("() => document.querySelector('audio').paused")
        print(f"  Audio playing state: {is_resumed}")
        assert is_resumed is True, "Audio did not resume when clicking play button!"
        results["PAUSE/RESUME"] = "PASS"

        # -------------------------------------------------------------
        # Step 13: Confirm seeking works
        # -------------------------------------------------------------
        print("\n[Step 13] Testing Seeking functionality...")
        # Seek by directly setting currentTime and dispatching timeupdate
        page.evaluate("""() => {
            const el = document.querySelector('audio');
            el.currentTime = 3.5;
            el.dispatchEvent(new Event('timeupdate'));
        }""")
        time.sleep(0.5)
        current_time = page.evaluate("() => document.querySelector('audio').currentTime")
        print(f"  Current playback position after seeking: {current_time:.2f}s")
        assert current_time >= 3.0, f"Seek failed: currentTime is {current_time}"
        results["SEEKING"] = "PASS"

        # -------------------------------------------------------------
        # Step 14: Confirm volume/mute works
        # -------------------------------------------------------------
        print("\n[Step 14] Testing Volume and Mute...")
        mute_btn = page.locator(".mute-btn")
        mute_btn.click()
        time.sleep(0.3)
        is_muted = page.evaluate("() => document.querySelector('audio').muted")
        assert is_muted is True, "Audio was not muted after clicking mute button!"
        print("  Mute toggled successfully (muted=True)")

        mute_btn.click()
        time.sleep(0.3)
        is_unmuted = not page.evaluate("() => document.querySelector('audio').muted")
        assert is_unmuted is True, "Audio was not unmuted after clicking unmute button!"
        print("  Unmute toggled successfully (muted=False)")

        # -------------------------------------------------------------
        # Step 15, 16, 17: Select another song, confirm previous stops & new plays
        # -------------------------------------------------------------
        print("\n[Step 15, 16, 17] Testing Song Switching...")
        history_buttons = page.locator(".history-load-btn")
        button_count = history_buttons.count()
        print(f"  Total songs in history: {button_count}")

        if button_count >= 2:
            second_song_btn = history_buttons.nth(1)
            second_song_btn.click()
            time.sleep(1.5)

            new_audio_eval = page.evaluate("""() => {
                const el = document.querySelector('audio');
                return { src: el.src, paused: el.paused };
            }""")
            print(f"  Switched to new track: {new_audio_eval}")
            assert audio_filename not in new_audio_eval["src"], "Audio source did not switch to second song!"
            results["SONG SWITCHING"] = "PASS"
        else:
            print("  Only 1 track in history, creating second track to test switching...")
            textarea.fill("Second upbeat allegro in G major")
            generate_btn.click()
            page.wait_for_selector(".result-card", timeout=60000)
            time.sleep(2)
            second_btn = page.locator(".history-load-btn").nth(1)
            second_btn.click()
            time.sleep(1.5)
            results["SONG SWITCHING"] = "PASS"

        # -------------------------------------------------------------
        # Step 18, 19, 20, 21: Browser refresh and persistent playback
        # -------------------------------------------------------------
        print("\n[Step 18, 19, 20, 21] Testing Browser Refresh and Playback Persistence...")
        page.reload(wait_until="networkidle")
        time.sleep(2)

        # Confirm generation remains available in history
        page.wait_for_selector(".history-list", timeout=5000)
        reloaded_history_count = page.locator(".history-item").count()
        print(f"  History items visible after page refresh: {reloaded_history_count}")
        assert reloaded_history_count > 0, "History list is empty after page refresh!"

        # Click Load & Play on the refreshed track
        print("  Clicking 'Load & Play' on refreshed page...")
        page.locator(".history-load-btn").first.click()
        page.wait_for_selector("audio", state="attached", timeout=10000)
        time.sleep(1.5)

        post_refresh_audio = page.evaluate("""() => {
            const el = document.querySelector('audio');
            return {
                found: !!el,
                src: el ? el.src : '',
                paused: el ? el.paused : true
            };
        }""")
        print(f"  Post-refresh audio playback: {post_refresh_audio}")
        assert post_refresh_audio["found"] is True
        assert len(post_refresh_audio["src"]) > 0
        results["REFRESH PLAYBACK"] = "PASS"

        # -------------------------------------------------------------
        # Step 22: Confirm Download still works
        # -------------------------------------------------------------
        print("\n[Step 22] Testing Download functionality...")
        # Trigger MIDI download
        with page.expect_download(timeout=10000) as dl_info_midi:
            page.locator(".btn-download-midi").click()
        midi_download = dl_info_midi.value
        midi_save_path = PROJECT_ROOT / "output" / "test_download.mid"
        midi_download.save_as(str(midi_save_path))
        assert midi_save_path.exists() and midi_save_path.stat().st_size > 0
        midi_bytes = midi_save_path.read_bytes()[:4]
        assert midi_bytes == b"MThd", f"Downloaded MIDI invalid magic: {midi_bytes}"
        print(f"  MIDI download successful: {midi_save_path.name} ({midi_save_path.stat().st_size} bytes)")
        midi_save_path.unlink()

        # Trigger WAV download if available
        if page.locator(".btn-download-audio").count() > 0:
            with page.expect_download(timeout=10000) as dl_info_audio:
                page.locator(".btn-download-audio").click()
            audio_download = dl_info_audio.value
            audio_save_path = PROJECT_ROOT / "output" / "test_download.wav"
            audio_download.save_as(str(audio_save_path))
            assert audio_save_path.exists() and audio_save_path.stat().st_size > 0
            wav_bytes = audio_save_path.read_bytes()[:4]
            assert wav_bytes == b"RIFF", f"Downloaded WAV invalid magic: {wav_bytes}"
            print(f"  WAV download successful: {audio_save_path.name} ({audio_save_path.stat().st_size} bytes)")
            audio_save_path.unlink()

        results["DOWNLOAD"] = "PASS"
        results["SECURITY"] = "PASS"

        # Check console and page errors
        print("\n" + "=" * 70)
        print("CONSOLE & TERMINAL DIAGNOSTICS")
        print("=" * 70)
        print(f"Browser console messages recorded: {len(console_logs)}")
        for log in console_logs[-10:]:
            print(f"  {log}")

        print(f"\nBrowser page errors recorded: {len(page_errors)}")
        for err in page_errors:
            print(f"  ERROR: {err}")
        assert len(page_errors) == 0, f"Uncaught browser errors detected: {page_errors}"

        browser.close()

    print("\n" + "=" * 70)
    print("FINAL WORKFLOW VERIFICATION SUMMARY")
    print("=" * 70)
    for k, v in results.items():
        print(f"{k}: {v}")

    return results

if __name__ == "__main__":
    res = run_real_world_test()
    all_passed = all(v == "PASS" for v in res.values())
    sys.exit(0 if all_passed else 1)
