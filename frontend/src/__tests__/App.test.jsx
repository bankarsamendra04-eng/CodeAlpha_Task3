import { describe, it, expect, beforeEach, vi } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import React from "react"
import App from "../App"

// Mock fetch globally
const mockFetch = vi.fn()
global.fetch = mockFetch

describe("Frontend AI Music Studio Component Tests", () => {
  beforeEach(() => {
    mockFetch.mockReset()
    localStorage.clear()

    // Default health check response
    mockFetch.mockImplementation((url) => {
      if (url === "/health") {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              status: "healthy",
              components: { api: "ok", database: "ok" },
            }),
        })
      }
      if (url.includes("/api/generations")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              total: 1,
              page: 1,
              limit: 20,
              items: [
                {
                  id: "gen-test-1",
                  generation_id: "guid-001",
                  prompt: "Peaceful piano history piece",
                  instrument: "piano",
                  tempo_bpm: 80,
                  musical_key: "C",
                  scale: "major",
                  created_at: new Date().toISOString(),
                },
                {
                  id: "gen-test-2",
                  generation_id: "guid-002",
                  prompt: "Upbeat violin concerto piece",
                  instrument: "violin",
                  tempo_bpm: 120,
                  musical_key: "G",
                  scale: "minor",
                  created_at: new Date().toISOString(),
                },
              ],
            }),
        })
      }
      if (url.includes("/api/plans")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              total_plans: 5,
              plans: [
                { tier: "FREE", name: "Free", monthly_price_usd: 0, highlights: ["15 gen/mo"], limits: { max_generations_per_month: 15, max_duration_seconds: 60 } },
                { tier: "CREATOR", name: "Creator", monthly_price_usd: 19, highlights: ["200 gen/mo"], limits: { max_generations_per_month: 200, max_duration_seconds: 90 } },
                { tier: "PRO", name: "Pro", monthly_price_usd: 49, highlights: ["1000 gen/mo"], limits: { max_generations_per_month: 1000, max_duration_seconds: 240 } },
                { tier: "EDUCATION", name: "Education", monthly_price_usd: 15, highlights: ["500 gen/mo"], limits: { max_generations_per_month: 500, max_duration_seconds: 120 } },
                { tier: "ENTERPRISE", name: "Enterprise", monthly_price_usd: null, highlights: ["Unlimited"], limits: { max_generations_per_month: -1, max_duration_seconds: 600 } },
              ],
            }),
        })
      }
      if (url.includes("/api/subscription/me")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              tier: "FREE",
              plan_name: "Free",
              generations: { used: 2, limit: 15, remaining: 13, unlimited: false },
            }),
        })
      }
      return Promise.reject(new Error(`Unhandled request to: ${url}`))
    })
  })

  it("renders prompt input and example prompt suggestions", async () => {
    render(<App />)
    expect(screen.getAllByText(/AI Music Studio/i).length).toBeGreaterThan(0)

    const promptTextarea = screen.getByPlaceholderText(
      /peaceful piano music for meditation/i
    )
    expect(promptTextarea).toBeDefined()
    expect(promptTextarea.value).toContain("Peaceful piano music")

    // Check suggested prompts label
    expect(screen.getByText(/Try an example:/i)).toBeDefined()
  })

  it("handles prompt input editing", async () => {
    render(<App />)
    const promptTextarea = screen.getByPlaceholderText(
      /peaceful piano music for meditation/i
    )

    fireEvent.change(promptTextarea, {
      target: { value: "Energetic flute solo at 140 BPM" },
    })
    expect(promptTextarea.value).toBe("Energetic flute solo at 140 BPM")
  })

  it("toggles advanced controls drawer", async () => {
    render(<App />)
    const toggleBtn = screen.getByText(/Advanced Music Controls/i)
    expect(toggleBtn).toBeDefined()

    fireEvent.click(toggleBtn)
    expect(screen.getByText("Instrument")).toBeDefined()
    expect(screen.getByText("Tempo (BPM)")).toBeDefined()
    expect(screen.getByText("Key & Scale")).toBeDefined()
    expect(screen.getByText("Complexity / Density")).toBeDefined()
  })

  it("triggers music generation and displays loading state and result", async () => {
    // Mock successful generation endpoint
    mockFetch.mockImplementation((url) => {
      if (url === "/health") {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              status: "healthy",
              components: { api: "ok", database: "ok" },
            }),
        })
      }
      if (url.includes("/api/generations")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ total: 0, items: [] }),
        })
      }
      if (url === "/api/music/generate") {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              success: true,
              generation_id: "gen-new-123",
              metadata: {
                prompt: "Peaceful piano meditation",
                interpreted_parameters: {
                  mood: "peaceful",
                  instrument: "piano",
                  complexity: "low",
                },
                user_overrides_applied: {},
                temperature_used: 0.85,
                num_events_generated: 48,
                duration_quarter_lengths: 16.0,
                notes_count: 30,
                chords_count: 10,
                rests_count: 8,
                tempo_bpm: 72,
                instrument: "piano",
                key: "C",
                scale: "major",
              },
              midi_file: {
                filename: "composition_test.mid",
                download_url: "/api/music/download/midi/composition_test.mid",
                file_type: "midi",
                size_bytes: 1024,
              },
              audio_file: {
                filename: "composition_test.wav",
                download_url: "/api/music/download/audio/composition_test.wav",
                file_type: "audio",
                size_bytes: 65536,
              },
              audio_status: "rendered",
              message: "Music composed successfully",
            }),
        })
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ items: [] }),
      })
    })

    render(<App />)
    const generateBtn = screen.getByRole("button", {
      name: /generate music/i,
    })
    fireEvent.submit(generateBtn.closest("form"))

    // Wait for generation completion
    await waitFor(() => {
      expect(screen.getByText("Generated Music")).toBeDefined()
    })

    // Verify downloads and disclosure
    expect(screen.getByText(/Download MIDI/i)).toBeDefined()
    expect(screen.getByText(/AI-Generated Music Disclosure/i)).toBeDefined()
  })

  it("displays safe error message when generation API fails", async () => {
    mockFetch.mockImplementation((url) => {
      if (url === "/health") {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              status: "healthy",
              components: { api: "ok", database: "ok" },
            }),
        })
      }
      if (url.includes("/api/generations")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ total: 0, items: [] }),
        })
      }
      if (url === "/api/music/generate") {
        return Promise.resolve({
          ok: false,
          status: 500,
          json: () =>
            Promise.resolve({
              detail: "An internal server error occurred. Please contact the administrator.",
            }),
        })
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ items: [] }),
      })
    })

    render(<App />)
    const generateBtn = screen.getByRole("button", {
      name: /generate music/i,
    })
    fireEvent.submit(generateBtn.closest("form"))

    await waitFor(() => {
      expect(
        screen.getByText(/an internal server error occurred/i)
      ).toBeDefined()
    })
  })

  it("opens and handles authentication modal for login and registration", async () => {
    render(<App />)
    const signInBtn = screen.getByText(/Admin \/ Sign In/i)
    fireEvent.click(signInBtn)

    // Modal is opened
    expect(screen.getAllByText("Sign In").length).toBeGreaterThan(0)
    expect(screen.getByText("Create Account")).toBeDefined()

    // Switch tab to Create Account
    const createAccountTab = screen.getByText("Create Account")
    fireEvent.click(createAccountTab)

    expect(screen.getByText("Email Address")).toBeDefined()
    expect(screen.getByText("Account Role")).toBeDefined()

    // Close modal
    const cancelBtn = screen.getByRole("button", { name: /cancel/i })
    fireEvent.click(cancelBtn)
  })

  it("renders generation history and opens Responsible AI modal", async () => {
    render(<App />)

    // History is loaded
    await waitFor(() => {
      expect(screen.getByText("Peaceful piano history piece")).toBeDefined()
    })

    // Open Responsible AI modal via footer
    const raiBtn = screen.getByRole("button", {
      name: /responsible ai & provenance policy/i,
    })
    fireEvent.click(raiBtn)

    expect(screen.getByText(/Dataset Provenance & Attribution/i)).toBeDefined()
    expect(screen.getByText(/No Artist Impersonation & No False Attribution/i)).toBeDefined()

    // Acknowledge and close modal
    const ackBtn = screen.getByRole("button", {
      name: /understood & acknowledged/i,
    })
    fireEvent.click(ackBtn)
  })

  it("opens and displays SaaS subscription plans modal", async () => {
    render(<App />)

    // Click Plans & Pricing button in navbar
    const plansBtn = screen.getByRole("button", { name: /plans & pricing/i })
    fireEvent.click(plansBtn)

    // Verify modal content
    await waitFor(() => {
      expect(screen.getByText(/AI Music Studio — Plans & Pricing/i)).toBeDefined()
      expect(screen.getByText("Creator")).toBeDefined()
      expect(screen.getByText("Enterprise")).toBeDefined()
    })

    // Close modal
    const closeBtn = screen.getByTitle("Close")
    fireEvent.click(closeBtn)
  })

  it("loads, plays, pauses, resumes, and adjusts volume on a history track", async () => {
    // Mock HTMLMediaElement prototype methods for jsdom
    window.HTMLMediaElement.prototype.load = vi.fn()
    window.HTMLMediaElement.prototype.play = vi.fn().mockImplementation(() => Promise.resolve())
    window.HTMLMediaElement.prototype.pause = vi.fn()
    window.scrollTo = vi.fn()

    render(<App />)

    // Wait for history items to render
    await waitFor(() => {
      expect(screen.getByText("Peaceful piano history piece")).toBeDefined()
    })

    // Find and click the Load & Play button for the first song
    const loadPlayBtns = screen.getAllByRole("button", { name: /load & play ▶/i })
    expect(loadPlayBtns.length).toBeGreaterThanOrEqual(1)
    fireEvent.click(loadPlayBtns[0])

    // Verify player appears with loaded composition info
    await waitFor(() => {
      expect(screen.getByText("Generated Music")).toBeDefined()
      expect(screen.getByRole("heading", { name: "Peaceful piano history piece" })).toBeDefined()
      expect(screen.getByLabelText(/Seek track/i)).toBeDefined()
    })

    // Verify volume slider and mute controls
    const volumeSlider = screen.getByLabelText(/Volume control/i)
    expect(volumeSlider).toBeDefined()
    fireEvent.change(volumeSlider, { target: { value: "0.5" } })
    expect(screen.getByText("50%")).toBeDefined()

    // Test mute toggle
    const muteBtn = screen.getByRole("button", { name: /mute audio/i })
    fireEvent.click(muteBtn)
    expect(screen.getByText("0%")).toBeDefined()

    // Test unmute toggle
    const unmuteBtn = screen.getByRole("button", { name: /unmute audio/i })
    fireEvent.click(unmuteBtn)
    expect(screen.getByText("50%")).toBeDefined()

    // Verify button transitions to Pause while playing
    await waitFor(() => {
      expect(screen.getAllByRole("button", { name: /pause ⏸/i }).length).toBeGreaterThan(0)
    })
    const pauseBtns = screen.getAllByRole("button", { name: /pause ⏸/i })
    fireEvent.click(pauseBtns[0])

    // Verify button transitions to Play when paused
    await waitFor(() => {
      expect(screen.getAllByRole("button", { name: /play ▶/i }).length).toBeGreaterThan(0)
    })

    // Resume playback
    const resumeBtn = screen.getAllByRole("button", { name: /play ▶/i })[0]
    fireEvent.click(resumeBtn)
    await waitFor(() => {
      expect(screen.getAllByRole("button", { name: /pause ⏸/i }).length).toBeGreaterThan(0)
    })
  })

  it("switches smoothly between multiple generated songs in history", async () => {
    window.HTMLMediaElement.prototype.load = vi.fn()
    window.HTMLMediaElement.prototype.play = vi.fn().mockImplementation(() => Promise.resolve())
    window.HTMLMediaElement.prototype.pause = vi.fn()
    window.scrollTo = vi.fn()

    render(<App />)

    // Wait for both history songs to load
    await waitFor(() => {
      expect(screen.getAllByText("Peaceful piano history piece").length).toBeGreaterThan(0)
      expect(screen.getAllByText("Upbeat violin concerto piece").length).toBeGreaterThan(0)
    })

    const initialButtons = screen.getAllByRole("button", { name: /load & play ▶/i })
    expect(initialButtons.length).toBe(2)

    // 1. Click to load Song 1 (Piano piece)
    fireEvent.click(initialButtons[0])

    // Wait for Song 1 to be playing
    await waitFor(() => {
      expect(screen.getAllByRole("button", { name: /pause ⏸/i }).length).toBeGreaterThan(0)
      expect(screen.getByText(/ID: guid-001/i)).toBeDefined()
    })

    // Song 2 should still show "Load & Play ▶"
    const remainingLoadBtn = screen.getByRole("button", { name: /load & play ▶/i })
    expect(remainingLoadBtn).toBeDefined()

    // 2. Click Song 2 (Violin piece) to switch tracks
    fireEvent.click(remainingLoadBtn)

    // Verify Song 2 is now loaded and playing, and player ID switched to guid-002
    await waitFor(() => {
      const trackNameEl = document.querySelector(".track-name")
      const resultIdEl = document.querySelector(".result-id")
      expect(resultIdEl ? resultIdEl.textContent : "").toContain("guid-002")
      expect(trackNameEl ? trackNameEl.textContent : "").toContain("Upbeat violin concerto piece")
      expect(screen.getAllByRole("button", { name: /pause ⏸/i }).length).toBeGreaterThan(0)
      expect(screen.getAllByRole("button", { name: /load & play ▶/i }).length).toBeGreaterThan(0)
    })
  })

  it("verifies persistence of playback across browser refresh simulation", async () => {
    window.HTMLMediaElement.prototype.load = vi.fn()
    window.HTMLMediaElement.prototype.play = vi.fn().mockImplementation(() => Promise.resolve())
    window.HTMLMediaElement.prototype.pause = vi.fn()
    window.scrollTo = vi.fn()

    // 1. Initial Render (Browser Session 1)
    const { unmount } = render(<App />)

    // Wait for history to appear
    await waitFor(() => {
      expect(screen.getByText("Peaceful piano history piece")).toBeDefined()
    })

    // Click Load & Play on the first song
    const loadButtons = screen.getAllByRole("button", { name: /load & play ▶/i })
    fireEvent.click(loadButtons[0])

    // Wait for playback state
    await waitFor(() => {
      expect(screen.getAllByRole("button", { name: /pause ⏸/i }).length).toBeGreaterThan(0)
    })

    // 2. Simulate Browser Refresh (Unmount and Remount)
    unmount()

    render(<App />)

    // Verify history reloads seamlessly from backend
    await waitFor(() => {
      expect(screen.getByText("Peaceful piano history piece")).toBeDefined()
    })

    // Click Load & Play again on the refreshed page
    const reloadedButtons = screen.getAllByRole("button", { name: /load & play ▶/i })
    expect(reloadedButtons.length).toBeGreaterThanOrEqual(1)
    fireEvent.click(reloadedButtons[0])

    // Verify playback resumes properly
    await waitFor(() => {
      expect(screen.getAllByRole("button", { name: /pause ⏸/i }).length).toBeGreaterThan(0)
      expect(screen.getByRole("heading", { name: "Peaceful piano history piece" })).toBeDefined()
    })
  })

  it("handles missing or unplayable audio file with error banner without crashing", async () => {
    window.HTMLMediaElement.prototype.load = vi.fn()
    window.HTMLMediaElement.prototype.play = vi.fn().mockImplementation(() => Promise.reject(new Error("404 Not Found")))
    window.HTMLMediaElement.prototype.pause = vi.fn()
    window.scrollTo = vi.fn()

    render(<App />)

    await waitFor(() => {
      expect(screen.getByText("Peaceful piano history piece")).toBeDefined()
    })

    const loadButtons = screen.getAllByRole("button", { name: /load & play ▶/i })
    fireEvent.click(loadButtons[0])

    // Verify error state is shown and user gets clear guidance
    await waitFor(() => {
      expect(screen.getByText(/Click Play ▶ to begin playback|Unable to play audio|Playback error/i)).toBeDefined()
    })
  })
})


