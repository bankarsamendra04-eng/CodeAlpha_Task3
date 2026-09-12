import { useState, useEffect, useRef } from "react"
import AdminDashboard from "./AdminDashboard"

const SUGGESTED_PROMPTS = [
  "Peaceful piano music for meditation at 70 BPM",
  "Melancholic acoustic guitar melody with gentle picking",
  "Uplifting and energetic classical piano piece at 128 BPM",
  "Dark mysterious violin solo with expressive vibrato",
  "Romantic and dreamy piano waltz in a quiet night",
]

const INSTRUMENTS = [
  { label: "Default (Auto / From Prompt)", value: "" },
  { label: "Acoustic Grand Piano", value: "piano" },
  { label: "Electric Piano", value: "electric piano" },
  { label: "Harpsichord", value: "harpsichord" },
  { label: "Acoustic Guitar", value: "acoustic guitar" },
  { label: "Electric Guitar", value: "electric guitar" },
  { label: "Violin", value: "violin" },
  { label: "Cello (Violoncello)", value: "violoncello" },
  { label: "Flute", value: "flute" },
  { label: "Clarinet", value: "clarinet" },
  { label: "Trumpet", value: "trumpet" },
  { label: "Pipe Organ", value: "pipe organ" },
  { label: "Marimba", value: "marimba" },
]

const MOODS = [
  { label: "Default (Auto / From Prompt)", value: "" },
  { label: "Peaceful", value: "peaceful" },
  { label: "Calm", value: "calm" },
  { label: "Melancholic", value: "melancholic" },
  { label: "Energetic", value: "energetic" },
  { label: "Uplifting", value: "uplifting" },
  { label: "Dramatic", value: "dramatic" },
  { label: "Mysterious", value: "mysterious" },
  { label: "Romantic", value: "romantic" },
  { label: "Joyful", value: "joyful" },
  { label: "Dark", value: "dark" },
]

const KEYS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
const SCALES = [
  { label: "Major", value: "major" },
  { label: "Minor", value: "minor" },
]

function App() {
  const [prompt, setPrompt] = useState("Peaceful piano music for meditation at 70 BPM")
  const [showAdvanced, setShowAdvanced] = useState(false)

  // Advanced Controls state
  const [mood, setMood] = useState("")
  const [instrument, setInstrument] = useState("")
  const [tempo, setTempo] = useState("")
  const [duration, setDuration] = useState("60")
  const [complexity, setComplexity] = useState("medium")
  const [musicalKey, setMusicalKey] = useState("C")
  const [scale, setScale] = useState("major")
  const [temperature, setTemperature] = useState("0.85")
  const [seed, setSeed] = useState("")

  // Pipeline state
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)
  const [activeStep, setActiveStep] = useState(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [audioCurrentTime, setAudioCurrentTime] = useState(0)
  const [audioDuration, setAudioDuration] = useState(0)
  const [isAudioLoading, setIsAudioLoading] = useState(false)
  const [audioError, setAudioError] = useState(null)
  const [activePlayingId, setActivePlayingId] = useState(null)
  const [healthStatus, setHealthStatus] = useState("checking")
  const [volume, setVolume] = useState(0.85)
  const [isMuted, setIsMuted] = useState(false)
  const [prevVolume, setPrevVolume] = useState(0.85)
  const audioRef = useRef(null)
  const autoPlayTimerRef = useRef(null)

  // Clean up autoPlayTimer on unmount
  useEffect(() => {
    return () => {
      if (autoPlayTimerRef.current) {
        clearTimeout(autoPlayTimerRef.current)
      }
    }
  }, [])

  // Synchronize volume and mute with audio element
  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.volume = isMuted ? 0 : volume
      audioRef.current.muted = isMuted
    }
  }, [volume, isMuted])

  // Auth & View state
  const [token, setToken] = useState(() => localStorage.getItem("aimusic_token") || "")
  const [currentUser, setCurrentUser] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem("aimusic_user")) || null
    } catch {
      return null
    }
  })
  // Track initial authentication verification on startup/refresh
  const [isVerifyingAuth, setIsVerifyingAuth] = useState(() => Boolean(localStorage.getItem("aimusic_token")))
  const [currentView, setCurrentView] = useState(() => {
    const savedToken = localStorage.getItem("aimusic_token")
    if (!savedToken) return "login"
    try {
      const savedUser = JSON.parse(localStorage.getItem("aimusic_user"))
      if (savedUser?.role === "ADMIN") return "admin"
      return "studio"
    } catch {
      return "login"
    }
  })
  const [showAuthModal, setShowAuthModal] = useState(false)
  const [authMode, setAuthMode] = useState("login") // 'login' or 'register'
  const [authUsername, setAuthUsername] = useState("")
  const [authEmail, setAuthEmail] = useState("")
  const [authPassword, setAuthPassword] = useState("")
  const [authConfirmPassword, setAuthConfirmPassword] = useState("")
  const [authError, setAuthError] = useState(null)
  const [authLoading, setAuthLoading] = useState(false)

  // Feedback state for current result
  const [feedbackRating, setFeedbackRating] = useState(5)
  const [feedbackComment, setFeedbackComment] = useState("")
  const [feedbackSubmitted, setFeedbackSubmitted] = useState(false)
  const [feedbackSubmitting, setFeedbackSubmitting] = useState(false)

  // Responsible AI modal state
  const [showResponsibleAiModal, setShowResponsibleAiModal] = useState(false)

  // SaaS Plans & Subscription state
  const [showPlansModal, setShowPlansModal] = useState(false)
  const [plans, setPlans] = useState([])
  const [subscriptionUsage, setSubscriptionUsage] = useState(null)
  const [planSwitching, setPlanSwitching] = useState(false)

  // History state
  const [history, setHistory] = useState([])
  const [loadingHistory, setLoadingHistory] = useState(false)

  // Robust error message parser ensuring strings, Pydantic 422 lists, and network errors never display as [object Object]
  const parseAuthErrorMessage = (errorData, defaultMessage = "Authentication failed.", status = null) => {
    if (status === 0 || !status && errorData instanceof TypeError) {
      return "Backend server is unavailable. Please check that the server is running."
    }
    if (!errorData) return defaultMessage
    if (typeof errorData === "string") return errorData

    // Handle FastAPI detail field
    const detail = errorData.detail
    if (typeof detail === "string" && detail.trim().length > 0) {
      return detail
    }
    if (Array.isArray(detail)) {
      // Pydantic validation error array
      const messages = detail
        .map((item) => {
          if (typeof item === "string") return item
          if (item && typeof item === "object") {
            const field = Array.isArray(item.loc) && item.loc.length > 0
              ? item.loc[item.loc.length - 1]
              : null
            const fieldPrefix = field && field !== "body" ? `${field}: ` : ""
            return `${fieldPrefix}${item.msg || "Invalid format"}`
          }
          return null
        })
        .filter(Boolean)
      if (messages.length > 0) {
        return messages.join("; ")
      }
    }

    if (errorData.message && typeof errorData.message === "string") {
      return errorData.message
    }
    return defaultMessage
  }

  // Auth actions
  const handleLogin = async (e) => {
    if (e) e.preventDefault()
    if (authLoading) return // Prevent accidental multiple submissions

    setAuthError(null)

    const cleanUsername = authUsername.trim()
    if (!cleanUsername) {
      setAuthError("Please enter your email address or username.")
      return
    }

    if (!authPassword) {
      setAuthError("Please enter your password.")
      return
    }

    setAuthLoading(true)
    try {
      let res
      try {
        res = await fetch("/api/auth/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            username: cleanUsername,
            password: authPassword,
          }),
        })
      } catch (netErr) {
        throw new Error("Backend server is unavailable. Please check that the server is online and try again.")
      }

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}))
        const errorMsg = parseAuthErrorMessage(errData, "Invalid username or password.", res.status)
        throw new Error(errorMsg)
      }
      const data = await res.json()
      setToken(data.access_token)
      setCurrentUser(data.user)
      localStorage.setItem("aimusic_token", data.access_token)
      localStorage.setItem("aimusic_user", JSON.stringify(data.user))
      setShowAuthModal(false)
      setAuthPassword("")
      if (data.user.role === "ADMIN") {
        setCurrentView("admin")
      } else {
        setCurrentView("studio")
      }
      try {
        window.history.replaceState(null, "", window.location.pathname)
      } catch {
        // Fallback if replaceState is unsupported
      }
    } catch (err) {
      setAuthError(err.message || "An unexpected error occurred during sign in.")
    } finally {
      setAuthLoading(false)
    }
  }

  const handleRegister = async (e) => {
    if (e) e.preventDefault()
    setAuthError(null)

    // Client-side validations
    const cleanUsername = authUsername.trim()
    const cleanEmail = authEmail.trim().toLowerCase()

    if (!cleanUsername || cleanUsername.length < 3) {
      setAuthError("Username or name must be at least 3 characters long.")
      return
    }

    const emailRegex = /^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$/
    if (!cleanEmail || !emailRegex.test(cleanEmail) || cleanEmail.includes("..")) {
      setAuthError("Please provide a valid email address (e.g. user@example.com).")
      return
    }

    if (!authPassword || authPassword.length < 6) {
      setAuthError("Password must be at least 6 characters long.")
      return
    }

    if (authPassword !== authConfirmPassword) {
      setAuthError("Passwords do not match. Please ensure both passwords match.")
      return
    }

    setAuthLoading(true)
    try {
      let res
      try {
        res = await fetch("/api/auth/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            username: cleanUsername,
            email: cleanEmail,
            password: authPassword,
            confirm_password: authConfirmPassword,
          }),
        })
      } catch (netErr) {
        throw new Error("Backend server is unavailable. Please ensure the backend is running.")
      }

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}))
        const errorMsg = parseAuthErrorMessage(errData, "Registration failed.", res.status)
        throw new Error(errorMsg)
      }
      const data = await res.json()
      setToken(data.access_token)
      setCurrentUser(data.user)
      localStorage.setItem("aimusic_token", data.access_token)
      localStorage.setItem("aimusic_user", JSON.stringify(data.user))
      setShowAuthModal(false)
      setAuthPassword("")
      setAuthConfirmPassword("")
      setCurrentView("studio")
      try {
        window.history.replaceState(null, "", window.location.pathname)
      } catch {
        // Fallback
      }
    } catch (err) {
      setAuthError(err.message || "An unexpected error occurred during account creation.")
    } finally {
      setAuthLoading(false)
    }
  }

  const handleLogout = () => {
    setToken("")
    setCurrentUser(null)
    localStorage.removeItem("aimusic_token")
    localStorage.removeItem("aimusic_user")
    setAuthMode("login")
    setAuthUsername("")
    setAuthPassword("")
    setAuthConfirmPassword("")
    setAuthError(null)
    setCurrentView("login")
    setShowAuthModal(false)
    try {
      window.history.replaceState(null, "", window.location.pathname)
    } catch {
      // Fallback
    }
  }

  // Fetch generation history from backend
  const fetchHistory = async () => {
    try {
      setLoadingHistory(true)
      const headers = token ? { Authorization: `Bearer ${token}` } : {}
      const res = await fetch("/api/generations?limit=6", { headers })
      if (res.status === 401 && token) {
        // Token expired while using app
        handleLogout()
        return
      }
      if (res.ok) {
        const data = await res.json()
        setHistory(data.items || [])
      }
    } catch (e) {
      console.error("Failed to fetch generation history:", e)
    } finally {
      setLoadingHistory(false)
    }
  }

  const [feedbackIsLiked, setFeedbackIsLiked] = useState(true)

  const handleSendFeedback = async () => {
    if (!result?.generation_id || feedbackSubmitting) return
    setFeedbackSubmitting(true)
    try {
      const headers = { "Content-Type": "application/json" }
      if (token) headers["Authorization"] = `Bearer ${token}`
      const res = await fetch("/api/feedback", {
        method: "POST",
        headers,
        body: JSON.stringify({
          generation_id: result.generation_id,
          rating: feedbackRating,
          is_liked: feedbackIsLiked,
          comment: feedbackComment.trim() || undefined,
        }),
      })
      if (res.ok) {
        setFeedbackSubmitted(true)
      }
    } catch (e) {
      console.error("Failed to submit feedback:", e)
    } finally {
      setFeedbackSubmitting(false)
    }
  }

  const fetchPlans = async () => {
    try {
      const res = await fetch("/api/plans")
      if (res.ok) {
        const data = await res.json()
        setPlans(data.plans || [])
      }
    } catch (e) {
      console.error("Failed to fetch plans:", e)
    }
  }

  const fetchSubscription = async () => {
    if (!token) return
    try {
      const res = await fetch("/api/subscription/me", {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (res.status === 401) {
        // Token expired while querying subscription
        handleLogout()
        return
      }
      if (res.ok) {
        const data = await res.json()
        setSubscriptionUsage(data)
      }
    } catch (e) {
      console.error("Failed to fetch subscription:", e)
    }
  }

  const handleSwitchTier = async (targetTier) => {
    if (!currentUser || !token) {
      setShowPlansModal(false)
      setAuthMode("register")
      setShowAuthModal(true)
      return
    }
    setPlanSwitching(true)
    try {
      const res = await fetch("/api/subscription/tier", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ tier: targetTier }),
      })
      if (res.ok) {
        const data = await res.json()
        const updated = { ...currentUser, subscription_tier: data.current_tier }
        setCurrentUser(updated)
        localStorage.setItem("aimusic_user", JSON.stringify(updated))
        await fetchSubscription()
      }
    } catch (e) {
      console.error("Failed to switch tier:", e)
    } finally {
      setPlanSwitching(false)
    }
  }

  // Verify session integrity with backend on startup or refresh
  useEffect(() => {
    const verifySession = async () => {
      const storedToken = localStorage.getItem("aimusic_token")
      if (!storedToken) {
        setToken("")
        setCurrentUser(null)
        setCurrentView("login")
        setIsVerifyingAuth(false)
        return
      }

      try {
        const res = await fetch("/api/auth/me", {
          headers: { Authorization: `Bearer ${storedToken}` },
        })
        if (res.ok) {
          const verifiedUser = await res.json()
          setToken(storedToken)
          setCurrentUser(verifiedUser)
          localStorage.setItem("aimusic_user", JSON.stringify(verifiedUser))
          setCurrentView((prev) => {
            if (verifiedUser.role === "ADMIN") {
              return prev === "studio" ? "studio" : "admin"
            }
            return "studio"
          })
        } else {
          // Token expired, revoked, or invalid on backend
          localStorage.removeItem("aimusic_token")
          localStorage.removeItem("aimusic_user")
          setToken("")
          setCurrentUser(null)
          setCurrentView("login")
        }
      } catch (err) {
        console.warn("Session verification network check:", err)
        // If server is unreachable but we have cached user, keep login view or show offline
        setIsVerifyingAuth(false)
      } finally {
        setIsVerifyingAuth(false)
      }
    }

    verifySession()
  }, [])

  // Check backend health & fetch history and plans on mount
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const res = await fetch("/health")
        if (res.ok) {
          const data = await res.json()
          setHealthStatus(data.status === "healthy" ? "online" : "degraded")
        } else {
          setHealthStatus("offline")
        }
      } catch (e) {
        setHealthStatus("offline")
      }
    }
    checkHealth()
    if (token) {
      fetchHistory()
      fetchPlans()
      fetchSubscription()
    }
  }, [token])

  // Helper to format seconds into mm:ss
  const formatTime = (secs) => {
    if (isNaN(secs) || secs < 0 || !isFinite(secs)) return "0:00"
    const m = Math.floor(secs / 60)
    const s = Math.floor(secs % 60)
    return `${m}:${s < 10 ? "0" : ""}${s}`
  }

  // Helper to extract clean display title
  const getSongTitle = (composition) => {
    if (!composition) return "AI Composition"
    const p = composition.metadata?.prompt || composition.prompt
    if (p && p.trim() && p !== "Manual Advanced Controls") {
      return p
    }
    const inst = (composition.metadata?.instrument || composition.instrument || "Piano").toUpperCase()
    const key = composition.metadata?.key || composition.musical_key || "C"
    const sc = (composition.metadata?.scale || composition.scale || "Major").toUpperCase()
    return `${inst} Solo in ${key} ${sc}`
  }

  // Audio play/pause/resume toggle
  const togglePlay = () => {
    if (!audioRef.current) return
    if (isPlaying) {
      audioRef.current.pause()
      setIsPlaying(false)
    } else {
      setAudioError(null)
      setIsAudioLoading(true)
      const promise = audioRef.current.play()
      if (promise !== undefined) {
        promise
          .then(() => {
            setIsPlaying(true)
            setIsAudioLoading(false)
          })
          .catch((err) => {
            console.warn("Playback error:", err)
            setIsPlaying(false)
            setIsAudioLoading(false)
            if (err.name !== "AbortError") {
              setAudioError("Unable to play audio. File may be missing or buffering.")
            }
          })
      }
    }
  }

  // Seek handler for slider
  const handleSeek = (e) => {
    const newTime = parseFloat(e.target.value)
    setAudioCurrentTime(newTime)
    if (audioRef.current) {
      audioRef.current.currentTime = newTime
    }
  }

  // Volume slider handler
  const handleVolumeChange = (e) => {
    const newVol = parseFloat(e.target.value)
    setVolume(newVol)
    if (newVol === 0) {
      setIsMuted(true)
    } else if (isMuted) {
      setIsMuted(false)
    }
    if (audioRef.current) {
      audioRef.current.volume = newVol
      audioRef.current.muted = newVol === 0
    }
  }

  // Mute / Unmute toggle
  const toggleMute = () => {
    if (isMuted) {
      const restored = prevVolume > 0 ? prevVolume : 0.85
      setIsMuted(false)
      setVolume(restored)
      if (audioRef.current) {
        audioRef.current.muted = false
        audioRef.current.volume = restored
      }
    } else {
      setPrevVolume(volume > 0 ? volume : 0.85)
      setIsMuted(true)
      if (audioRef.current) {
        audioRef.current.muted = true
      }
    }
  }

  const getVolumeIcon = () => {
    if (isMuted || volume === 0) return "🔇"
    if (volume < 0.5) return "🔉"
    return "🔊"
  }

  const handleRetryPlayback = () => {
    setAudioError(null)
    setIsAudioLoading(true)
    if (audioRef.current) {
      audioRef.current.load()
      const p = audioRef.current.play()
      if (p !== undefined) {
        p.then(() => {
          setIsPlaying(true)
          setIsAudioLoading(false)
        }).catch((err) => {
          setIsPlaying(false)
          setIsAudioLoading(false)
          setAudioError("Playback retry failed. Audio file may not be available.")
        })
      }
    }
  }

  // Handle generation
  const handleGenerate = async (e) => {
    if (e) e.preventDefault()
    const trimmedPrompt = prompt.trim()

    // Must provide either prompt or at least one advanced control
    const hasControls = Boolean(mood || instrument || tempo || seed)
    if (!trimmedPrompt && !hasControls) {
      setError("Please describe the music or configure the advanced musical controls.")
      return
    }

    // Stop current playback
    if (audioRef.current) {
      audioRef.current.pause()
    }
    setIsPlaying(false)
    setAudioCurrentTime(0)
    setAudioError(null)

    setIsLoading(true)
    setError(null)
    setActiveStep(trimmedPrompt ? "Analyzing prompt with Groq..." : "Applying musical controls...")

    try {
      const stepTimer1 = setTimeout(() => {
        setActiveStep("Predicting musical sequences with MAESTRO LSTM model...")
      }, 1200)

      const stepTimer2 = setTimeout(() => {
        setActiveStep("Assembling music21 score & generating MIDI...")
      }, 8000)

      const payload = {
        prompt: trimmedPrompt || undefined,
        render_audio: true,
        mood: mood || undefined,
        instrument: instrument || undefined,
        tempo: tempo ? parseFloat(tempo) : undefined,
        duration_seconds: duration ? parseInt(duration, 10) : undefined,
        complexity: complexity || undefined,
        key: musicalKey || undefined,
        scale: scale || undefined,
        temperature: temperature ? parseFloat(temperature) : undefined,
        random_seed: seed ? parseInt(seed, 10) : undefined,
      }

      const headers = { "Content-Type": "application/json" }
      if (token) headers["Authorization"] = `Bearer ${token}`

      const response = await fetch("/api/music/generate", {
        method: "POST",
        headers,
        body: JSON.stringify(payload),
      })

      clearTimeout(stepTimer1)
      clearTimeout(stepTimer2)

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}))
        throw new Error(errData.detail || `Server returned error (${response.status})`)
      }

      const data = await response.json()
      setResult(data)
      setActivePlayingId(data.generation_id)
      setIsPlaying(false)
      setFeedbackSubmitted(false)
      setFeedbackComment("")
      setFeedbackRating(5)
      // Refresh history list immediately
      fetchHistory()
    } catch (err) {
      setError(err.message || "An unexpected error occurred during generation.")
    } finally {
      setIsLoading(false)
      setActiveStep(null)
    }
  }

  // Helper to attach authorization token for private user media streaming & downloads
  const getAuthenticatedMediaUrl = (rawUrl) => {
    if (!rawUrl) return ""
    if (!token) return rawUrl
    const sep = rawUrl.includes("?") ? "&" : "?"
    return `${rawUrl}${sep}token=${encodeURIComponent(token)}`
  }

  // Load a record from history into the player view and immediately start playback
  const handleLoadHistoryItem = (item) => {
    // 1. Pause and stop previous audio playback
    if (audioRef.current) {
      audioRef.current.pause()
    }
    setIsPlaying(false)
    setAudioCurrentTime(0)
    setAudioError(null)
    setIsAudioLoading(true)

    // Resolve real playable audio URL
    let resolvedAudioFile = item.audio_file
    if (!resolvedAudioFile && item.midi_file) {
      const stem = item.midi_file.filename.replace(/\.midi?$/i, "")
      const wavName = `${stem}.wav`
      resolvedAudioFile = {
        filename: wavName,
        download_url: `/api/music/download/audio/${wavName}`,
        file_type: "audio",
        size_bytes: 0,
      }
    } else if (!resolvedAudioFile && item.generation_id) {
      const inst = (item.instrument || "piano").replace(/\s+/g, "_")
      const wavName = `${item.generation_id}_${inst}.wav`
      resolvedAudioFile = {
        filename: wavName,
        download_url: `/api/music/download/audio/${wavName}`,
        file_type: "audio",
        size_bytes: 0,
      }
    }

    setActivePlayingId(item.generation_id)

    setResult({
      success: true,
      generation_id: item.generation_id,
      metadata: {
        prompt: item.prompt || "Manual Advanced Controls",
        interpreted_parameters: item.interpreted_parameters || {},
        user_overrides_applied: item.user_overrides || {},
        prompt_parser: item.prompt_parser,
        temperature_used: item.temperature,
        num_events_generated: item.num_events_generated,
        duration_quarter_lengths: item.duration_quarter_lengths,
        notes_count: item.num_events_generated,
        chords_count: 0,
        rests_count: 0,
        tempo_bpm: item.tempo_bpm,
        instrument: item.instrument,
        key: item.musical_key,
        scale: item.scale,
      },
      midi_file: item.midi_file,
      audio_file: resolvedAudioFile,
      audio_status: item.audio_status || "rendered",
      message: `Loaded historical composition (${item.generation_id}) from database.`,
    })

    if (item.prompt) {
      setPrompt(item.prompt)
    }

    // Scroll to player view if supported
    if (typeof window.scrollTo === "function") {
      try {
        window.scrollTo({ top: 380, behavior: "smooth" })
      } catch {
        // Fallback for jsdom
      }
    }

    // Clear any pending playback timers
    if (autoPlayTimerRef.current) {
      clearTimeout(autoPlayTimerRef.current)
      autoPlayTimerRef.current = null
    }

    // Direct synchronous audio play if audio element is already mounted
    if (audioRef.current && resolvedAudioFile) {
      audioRef.current.src = getAuthenticatedMediaUrl(resolvedAudioFile.download_url)
      audioRef.current.currentTime = 0
      audioRef.current.load()
      const playPromise = audioRef.current.play()
      if (playPromise !== undefined) {
        playPromise
          .then(() => {
            setIsPlaying(true)
            setIsAudioLoading(false)
          })
          .catch((err) => {
            console.warn("Direct play caught:", err)
            setIsPlaying(false)
            setIsAudioLoading(false)
            if (err.name !== "AbortError") {
              setAudioError("Click Play ▶ to begin playback.")
            }
          })
      }
    } else {
      // Fallback timer when element mounts on next frame
      autoPlayTimerRef.current = setTimeout(() => {
        if (audioRef.current && resolvedAudioFile) {
          audioRef.current.src = getAuthenticatedMediaUrl(resolvedAudioFile.download_url)
          audioRef.current.load()
          audioRef.current.play().then(() => {
            setIsPlaying(true)
            setIsAudioLoading(false)
          }).catch((err) => {
            console.warn("Auto-play deferred:", err)
            setIsAudioLoading(false)
            if (err && err.name !== "AbortError") {
              setAudioError("Click Play ▶ to begin playback.")
            }
          })
        } else {
          setIsAudioLoading(false)
        }
      }, 100)
    }
  }

  // Reset form and controls
  const handleClear = () => {
    setPrompt("")
    setMood("")
    setInstrument("")
    setTempo("")
    setDuration("60")
    setComplexity("medium")
    setMusicalKey("C")
    setScale("major")
    setTemperature("0.85")
    setSeed("")
    setResult(null)
    setError(null)
    setIsPlaying(false)
    if (audioRef.current) {
      audioRef.current.pause()
    }
  }

  // 1. Initial Authentication Verification Loading State
  if (isVerifyingAuth) {
    return (
      <div className="auth-loading-screen">
        <div className="spinner" style={{ width: "36px", height: "36px" }} />
        <p>Verifying secure session...</p>
      </div>
    )
  }

  // 2. Unauthenticated Gatekeeper: Standalone Login / Register View
  if (currentView === "login" || !currentUser || !token) {
    return (
      <div className="auth-screen-container">
        <header className="auth-screen-nav">
          <div className="navbar-brand">
            <span className="brand-icon">🎵</span>
            <span className="brand-name">AI Music Studio</span>
            <span className="brand-version">v1.0 • LSTM + SQLite</span>
          </div>
          <div className="backend-pill">
            <span className={`status-dot ${healthStatus}`} />
            <span className="backend-text">
              {healthStatus === "online"
                ? "Backend & DB Online"
                : healthStatus === "checking"
                ? "Connecting..."
                : "Backend Offline"}
            </span>
          </div>
        </header>

        <main className="auth-screen-main">
          <div className="auth-card-standalone">
            <div className="auth-card-header">
              <span className="auth-card-badge">🔐 Secure Gateway</span>
              <h2 className="auth-card-title">Welcome to AI Music Studio</h2>
              <p className="auth-card-subtitle">
                {authMode === "login"
                  ? "Sign in with your User or Admin credentials to access your studio workspace."
                  : "Create a new studio creator account to compose and save original AI music."}
              </p>
            </div>

            <div className="auth-card-tabs">
              <button
                type="button"
                className={`auth-card-tab ${authMode === "login" ? "active" : ""}`}
                onClick={() => {
                  setAuthMode("login")
                  setAuthError(null)
                }}
              >
                Sign In
              </button>
              <button
                type="button"
                className={`auth-card-tab ${authMode === "register" ? "active" : ""}`}
                onClick={() => {
                  setAuthMode("register")
                  setAuthError(null)
                }}
              >
                Create Account
              </button>
            </div>

            <form
              onSubmit={authMode === "login" ? handleLogin : handleRegister}
              className="auth-form"
              noValidate
            >
              {authError && <div className="auth-error">{authError}</div>}

              <div>
                <label className="form-label">{authMode === "login" ? "Email or Username" : "Full Name / Username"}</label>
                <input
                  type="text"
                  required
                  className="auth-input"
                  placeholder={authMode === "login" ? "Email address or username" : "e.g. Wolfgang Amadeus"}
                  value={authUsername}
                  onChange={(e) => setAuthUsername(e.target.value)}
                />
              </div>

              {authMode === "register" && (
                <div>
                  <label className="form-label">Email Address</label>
                  <input
                    type="email"
                    required
                    className="auth-input"
                    placeholder="e.g. artist@aimusicstudio.io"
                    value={authEmail}
                    onChange={(e) => setAuthEmail(e.target.value)}
                  />
                </div>
              )}

              <div>
                <label className="form-label">Password</label>
                <input
                  type="password"
                  required
                  className="auth-input"
                  placeholder="••••••••"
                  value={authPassword}
                  onChange={(e) => setAuthPassword(e.target.value)}
                />
              </div>

              {authMode === "register" && (
                <div>
                  <label className="form-label">Confirm Password</label>
                  <input
                    type="password"
                    required
                    className="auth-input"
                    placeholder="••••••••"
                    value={authConfirmPassword}
                    onChange={(e) => setAuthConfirmPassword(e.target.value)}
                  />
                </div>
              )}

              <div style={{ marginTop: "0.5rem" }}>
                <button
                  type="submit"
                  className="btn btn-primary"
                  style={{ width: "100%", justifyContent: "center", padding: "0.85rem" }}
                  disabled={authLoading}
                >
                  {authLoading
                    ? "Authenticating..."
                    : authMode === "login"
                    ? "Sign In to Studio ▶"
                    : "Create Account & Enter Studio ▶"}
                </button>
              </div>
            </form>
          </div>
        </main>
      </div>
    )
  }

  // 3. Admin Protected View
  if (currentView === "admin") {
    if (currentUser?.role !== "ADMIN") {
      // Non-admin attempting to view admin panel: route back to studio
      setCurrentView("studio")
      return null
    }
    return (
      <div className="studio-app">
        <AdminDashboard
          token={token}
          currentUser={currentUser}
          onBackToStudio={() => setCurrentView("studio")}
          onLogout={handleLogout}
        />
      </div>
    )
  }

  return (
    <div className="studio-app">
      {/* Top Header */}
      <header className="navbar">
        <div className="navbar-brand">
          <span className="brand-icon">🎵</span>
          <span className="brand-name">AI Music Studio</span>
          <span className="brand-version">v1.0 • LSTM + SQLite</span>
        </div>

        <div className="navbar-actions">
          <button
            className="btn btn-outline-sm btn-plans-nav"
            onClick={() => setShowPlansModal(true)}
            title="Explore SaaS Subscription Plans & Pricing"
          >
            💎 Plans & Pricing
          </button>

          {currentUser ? (
            <div className="user-profile-widget">
              <span className="user-greeting">
                {currentUser.role === "ADMIN" && <span className="role-tag">ADMIN</span>}
                <span className={`tier-tag ${currentUser.subscription_tier || "FREE"}`}>
                  {currentUser.subscription_tier || "FREE"}
                </span>
                {currentUser.username}
                {subscriptionUsage?.generations && (
                  <span style={{ fontSize: "0.72rem", color: "var(--cyan)", marginLeft: "0.4rem", fontWeight: 700 }}>
                    ({subscriptionUsage.generations.used}/{subscriptionUsage.generations.unlimited ? "∞" : subscriptionUsage.generations.limit})
                  </span>
                )}
              </span>
              {currentUser.role === "ADMIN" && (
                <button
                  className="btn btn-outline-sm btn-admin-nav"
                  onClick={() => setCurrentView("admin")}
                  title="Open Admin Dashboard"
                >
                  🛡️ Admin Dashboard
                </button>
              )}
              <button className="btn btn-outline-sm" onClick={handleLogout}>
                Logout
              </button>
            </div>
          ) : (
            <div className="auth-buttons">
              <button
                className="btn btn-outline-sm btn-admin-nav"
                onClick={() => {
                  setAuthMode("login")
                  setShowAuthModal(true)
                }}
              >
                🛡️ Admin / Sign In
              </button>
            </div>
          )}

          <div className="backend-pill">
            <span className={`status-dot ${healthStatus}`} />
            <span className="backend-text">
              {healthStatus === "online"
                ? "Backend & DB Online"
                : healthStatus === "checking"
                ? "Connecting..."
                : "Backend Offline"}
            </span>
          </div>
        </div>
      </header>

      <main className="main-content">
        {/* Hero Section */}
        <section className="hero">
          <div className="badge">Symbolic AI Music Generation</div>
          <h1 className="hero-title">Create Original Music with AI</h1>
          <p className="hero-subtitle">
            Transform natural-language descriptions or fine-tune explicit controls to compose
            expressive polyphonic music with our trained MAESTRO LSTM model.
          </p>
        </section>

        {/* Studio Panel */}
        <div className="studio-card">
          <form onSubmit={handleGenerate} className="prompt-form">
            {/* Mode A: Natural Language Description */}
            <div className="form-group">
              <div className="label-row">
                <label htmlFor="music-prompt" className="form-label">
                  Describe your music (Option A)
                </label>
                <span className="label-tip">Natural Language or Presets</span>
              </div>
              <textarea
                id="music-prompt"
                rows="3"
                className="prompt-textarea"
                placeholder="e.g. Peaceful piano music for meditation at 70 BPM"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                disabled={isLoading}
              />
            </div>

            {/* Quick Suggestion Pills */}
            <div className="suggestions-container">
              <span className="suggestions-label">Try an example:</span>
              <div className="suggestion-pills">
                {SUGGESTED_PROMPTS.map((sample, idx) => (
                  <button
                    key={idx}
                    type="button"
                    className="pill-btn"
                    onClick={() => setPrompt(sample)}
                    disabled={isLoading}
                  >
                    {sample}
                  </button>
                ))}
              </div>
            </div>

            {/* Advanced Controls Toggle */}
            <div className="advanced-toggle-row">
              <button
                type="button"
                className={`advanced-toggle-btn ${showAdvanced ? "active" : ""}`}
                onClick={() => setShowAdvanced(!showAdvanced)}
              >
                <span>🎛️</span>
                <span>Advanced Music Controls (Option B)</span>
                <span className="toggle-chevron">{showAdvanced ? "▲" : "▼"}</span>
              </button>
              <span className="advanced-hint">
                Explicit selections override prompt suggestions
              </span>
            </div>

            {/* Mode B: Advanced Controls Panel */}
            {showAdvanced && (
              <div className="advanced-panel">
                <div className="controls-grid">
                  {/* Instrument */}
                  <div className="control-item">
                    <label className="control-label">Instrument</label>
                    <select
                      className="control-select"
                      value={instrument}
                      onChange={(e) => setInstrument(e.target.value)}
                      disabled={isLoading}
                    >
                      {INSTRUMENTS.map((inst, i) => (
                        <option key={i} value={inst.value}>
                          {inst.label}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Mood */}
                  <div className="control-item">
                    <label className="control-label">Mood</label>
                    <select
                      className="control-select"
                      value={mood}
                      onChange={(e) => setMood(e.target.value)}
                      disabled={isLoading}
                    >
                      {MOODS.map((m, i) => (
                        <option key={i} value={m.value}>
                          {m.label}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Tempo (BPM) */}
                  <div className="control-item">
                    <div className="control-label-row">
                      <label className="control-label">Tempo (BPM)</label>
                      <span className="control-value-display">
                        {tempo ? `${tempo} BPM` : "Auto"}
                      </span>
                    </div>
                    <input
                      type="range"
                      min="40"
                      max="220"
                      step="5"
                      value={tempo || 100}
                      onChange={(e) => setTempo(e.target.value)}
                      className="control-slider"
                      disabled={isLoading}
                    />
                    <div className="slider-ticks">
                      <span>40 (Largo)</span>
                      <span>120 (Moderato)</span>
                      <span>220 (Presto)</span>
                    </div>
                  </div>

                  {/* Duration */}
                  <div className="control-item">
                    <div className="control-label-row">
                      <label className="control-label">Duration</label>
                      <span className="control-value-display">{duration}s</span>
                    </div>
                    <input
                      type="range"
                      min="15"
                      max="240"
                      step="15"
                      value={duration}
                      onChange={(e) => setDuration(e.target.value)}
                      className="control-slider"
                      disabled={isLoading}
                    />
                    <div className="slider-ticks">
                      <span>15s</span>
                      <span>60s</span>
                      <span>240s</span>
                    </div>
                  </div>

                  {/* Key & Scale */}
                  <div className="control-item">
                    <label className="control-label">Key & Scale</label>
                    <div className="key-scale-row">
                      <select
                        className="control-select key-select"
                        value={musicalKey}
                        onChange={(e) => setMusicalKey(e.target.value)}
                        disabled={isLoading}
                      >
                        {KEYS.map((k) => (
                          <option key={k} value={k}>
                            Key of {k}
                          </option>
                        ))}
                      </select>

                      <select
                        className="control-select scale-select"
                        value={scale}
                        onChange={(e) => setScale(e.target.value)}
                        disabled={isLoading}
                      >
                        {SCALES.map((s) => (
                          <option key={s.value} value={s.value}>
                            {s.label}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>

                  {/* Complexity */}
                  <div className="control-item">
                    <label className="control-label">Complexity / Density</label>
                    <div className="segmented-control">
                      {["low", "medium", "high"].map((lvl) => (
                        <button
                          key={lvl}
                          type="button"
                          className={`segment-btn ${complexity === lvl ? "active" : ""}`}
                          onClick={() => setComplexity(lvl)}
                          disabled={isLoading}
                        >
                          {lvl.charAt(0).toUpperCase() + lvl.slice(1)}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Creativity (Temperature) */}
                  <div className="control-item">
                    <div className="control-label-row">
                      <label className="control-label">Creativity (Temperature)</label>
                      <span className="control-value-display">{temperature}</span>
                    </div>
                    <input
                      type="range"
                      min="0.2"
                      max="1.6"
                      step="0.05"
                      value={temperature}
                      onChange={(e) => setTemperature(e.target.value)}
                      className="control-slider"
                      disabled={isLoading}
                    />
                    <div className="slider-ticks">
                      <span>0.2 (Predictable)</span>
                      <span>0.85 (Balanced)</span>
                      <span>1.6 (Inventive)</span>
                    </div>
                  </div>

                  {/* Random Seed */}
                  <div className="control-item">
                    <label className="control-label">Random Seed (Optional)</label>
                    <input
                      type="number"
                      placeholder="e.g. 42 (blank for random)"
                      value={seed}
                      onChange={(e) => setSeed(e.target.value)}
                      className="control-input"
                      disabled={isLoading}
                    />
                  </div>
                </div>
              </div>
            )}

            {/* Action Buttons */}
            <div className="form-actions">
              <button
                type="submit"
                className="btn btn-primary"
                disabled={isLoading || (!prompt.trim() && !mood && !instrument && !tempo)}
              >
                {isLoading ? (
                  <>
                    <span className="spinner" />
                    Generating Music...
                  </>
                ) : (
                  <>
                    <span>✨</span> Generate Music
                  </>
                )}
              </button>

              <button
                type="button"
                className="btn btn-secondary"
                onClick={handleClear}
                disabled={isLoading || (!prompt && !result && !mood && !instrument && !tempo)}
              >
                Clear / Reset
              </button>
            </div>
          </form>

          {/* Loading Progress State */}
          {isLoading && (
            <div className="loading-state">
              <div className="pulse-bars">
                <span className="bar" />
                <span className="bar" />
                <span className="bar" />
                <span className="bar" />
                <span className="bar" />
              </div>
              <p className="loading-step-text">{activeStep || "Generating..."}</p>
              <p className="loading-hint">
                Predicting autoregressive note tokens on 15M parameter LSTM...
              </p>
            </div>
          )}

          {/* Error Banner */}
          {error && (
            <div className="error-banner">
              <span className="error-icon">⚠️</span>
              <div className="error-body">
                <strong>Generation Failed</strong>
                <p>{error}</p>
              </div>
              <button
                type="button"
                className="btn-close"
                onClick={() => setError(null)}
              >
                ×
              </button>
            </div>
          )}

          {/* Generation Result Player & Parameters */}
          {result && !isLoading && (
            <div className="result-section">
              <div className="result-header">
                <div className="result-title-group">
                  <span className="music-note-icon">🎶</span>
                  <div>
                    <h2 className="result-title">Generated Music</h2>
                    <p className="result-id">ID: {result.generation_id}</p>
                  </div>
                </div>

                <button
                  type="button"
                  className="btn btn-outline"
                  onClick={handleGenerate}
                  disabled={isLoading}
                >
                  🔄 Regenerate
                </button>
              </div>

              {/* Music Player Bar */}
              <div className="player-card">
                {result.audio_file ? (
                  <>
                    <audio
                      ref={audioRef}
                      src={getAuthenticatedMediaUrl(result.audio_file.download_url)}
                      onTimeUpdate={() => {
                        if (audioRef.current) {
                          setAudioCurrentTime(audioRef.current.currentTime)
                        }
                      }}
                      onLoadedMetadata={() => {
                        if (audioRef.current) {
                          setAudioDuration(audioRef.current.duration || 0)
                          setIsAudioLoading(false)
                        }
                      }}
                      onWaiting={() => setIsAudioLoading(true)}
                      onCanPlay={() => setIsAudioLoading(false)}
                      onEnded={() => {
                        setIsPlaying(false)
                        setAudioCurrentTime(0)
                      }}
                      onError={(e) => {
                        console.warn("Audio element error:", e)
                        setIsPlaying(false)
                        setIsAudioLoading(false)
                        setAudioError("Unable to stream audio file. Try refreshing or re-rendering.")
                      }}
                    />
                    <button
                      type="button"
                      className="play-btn"
                      onClick={togglePlay}
                      aria-label={isPlaying ? "Pause audio" : "Play audio"}
                      disabled={isAudioLoading}
                      title={isPlaying ? "Pause" : "Play"}
                    >
                      {isAudioLoading ? (
                        <span className="player-loading-spinner">⏳</span>
                      ) : isPlaying ? (
                        "⏸"
                      ) : (
                        "▶"
                      )}
                    </button>
                    <div className="player-controls">
                      {/* Now Playing Header Bar */}
                      <div className="player-header-badge-row">
                        <span className={`now-playing-pill ${isPlaying ? "active-playing" : "active-paused"}`}>
                          {isPlaying ? (
                            <>
                              <span className="now-playing-equalizer">
                                <span className="eq-bar" />
                                <span className="eq-bar" />
                                <span className="eq-bar" />
                              </span>
                              <span>NOW PLAYING</span>
                            </>
                          ) : (
                            <>
                              <span>⏸</span>
                              <span>PAUSED</span>
                            </>
                          )}
                        </span>
                        <span className="now-playing-id" title={`Generation ID: ${result.generation_id}`}>
                          Track: #{result.generation_id.slice(0, 10)}
                        </span>
                      </div>

                      {/* Song Title and Attributes */}
                      <div className="track-info">
                        <h4 className="track-name" title={getSongTitle(result)}>
                          {getSongTitle(result)}
                        </h4>
                        <div className="track-sub">
                          <span>{result.metadata.interpreted_parameters?.instrument?.toUpperCase() || result.metadata.instrument?.toUpperCase() || "PIANO"} SOLO</span>
                          <span>•</span>
                          <span>{result.metadata.key || "C"} {(result.metadata.scale || "major").toUpperCase()}</span>
                          <span>•</span>
                          <span>{result.metadata.tempo_bpm || 80} BPM</span>
                          <span>•</span>
                          <span>{result.metadata.interpreted_parameters?.mood || result.metadata.mood || "Peaceful"}</span>
                        </div>
                      </div>

                      {/* Seeker bar and timestamp */}
                      <div className="player-progress-bar">
                        <span className="player-time">{formatTime(audioCurrentTime)}</span>
                        <input
                          type="range"
                          className="player-seek-slider"
                          min="0"
                          max={audioDuration > 0 ? audioDuration : 1}
                          step="0.1"
                          value={audioCurrentTime}
                          onChange={handleSeek}
                          aria-label="Seek track"
                          style={{
                            background: `linear-gradient(to right, var(--cyan) ${audioDuration > 0 ? (audioCurrentTime / audioDuration) * 100 : 0}%, var(--border) ${audioDuration > 0 ? (audioCurrentTime / audioDuration) * 100 : 0}%)`
                          }}
                        />
                        <span className="player-time">{formatTime(audioDuration)}</span>
                      </div>

                      {/* Volume & Audio Controls Row */}
                      <div className="player-bottom-controls">
                        <div className="volume-control-group">
                          <button
                            type="button"
                            className="mute-btn"
                            onClick={toggleMute}
                            aria-label={isMuted ? "Unmute audio" : "Mute audio"}
                            title={isMuted ? "Unmute" : "Mute"}
                          >
                            {getVolumeIcon()}
                          </button>
                          <input
                            type="range"
                            className="player-volume-slider"
                            min="0"
                            max="1"
                            step="0.01"
                            value={isMuted ? 0 : volume}
                            onChange={handleVolumeChange}
                            aria-label="Volume control"
                            style={{
                              background: `linear-gradient(to right, var(--primary) ${isMuted ? 0 : volume * 100}%, var(--border) ${isMuted ? 0 : volume * 100}%)`
                            }}
                          />
                          <span className="volume-percent">{isMuted ? "0%" : `${Math.round(volume * 100)}%`}</span>
                        </div>
                      </div>

                      {/* Playback Error Banner with Retry */}
                      {audioError && (
                        <div className="player-error-banner">
                          <span className="player-error-text">⚠️ {audioError}</span>
                          <button
                            type="button"
                            className="btn-player-retry"
                            onClick={handleRetryPlayback}
                          >
                            Retry 🔄
                          </button>
                        </div>
                      )}
                    </div>
                  </>
                ) : (
                  <div className="player-fallback">
                    <span className="info-icon">ℹ️</span>
                    <div>
                      <strong>MIDI Generated Successfully</strong>
                      <p className="fallback-note">
                        Audio synthesis is in MIDI mode. Download the Standard MIDI file below to play with any software synth, DAW, or media player.
                      </p>
                    </div>
                  </div>
                )}
              </div>

              {/* Download Buttons */}
              <div className="download-actions">
                {result.midi_file && (
                  <a
                    href={getAuthenticatedMediaUrl(result.midi_file.download_url)}
                    download={result.midi_file.filename}
                    className="btn btn-download-midi"
                  >
                    <span>🎹</span> Download MIDI ({Math.round((result.midi_file.size_bytes || 0) / 1024 * 10) / 10 || 1} KB)
                  </a>
                )}

                {result.audio_file ? (
                  <a
                    href={getAuthenticatedMediaUrl(result.audio_file.download_url)}
                    download={result.audio_file.filename}
                    className="btn btn-download-audio"
                  >
                    <span>🔊</span> Download WAV Audio
                  </a>
                ) : (
                  <button
                    type="button"
                    className="btn btn-download-disabled"
                    disabled
                    title="Configure FluidSynth & SoundFont to enable direct WAV download"
                  >
                    <span>🔇</span> Audio WAV (Renderer Unset)
                  </button>
                )}
              </div>

              {/* Generation Parameters Display */}
              <div className="parameters-panel">
                <div className="parameters-header-row">
                  <h3 className="parameters-heading">Interpreted & Applied Parameters</h3>
                  {Object.keys(result.metadata.user_overrides_applied || {}).length > 0 && (
                    <span className="overrides-badge">
                      {Object.keys(result.metadata.user_overrides_applied).length} Controls Overridden
                    </span>
                  )}
                </div>

                <div className="parameters-grid">
                  <div className="param-item">
                    <span className="param-label">Mood</span>
                    <span className="param-val">{result.metadata.interpreted_parameters.mood}</span>
                  </div>
                  <div className="param-item">
                    <span className="param-label">Instrument</span>
                    <span className="param-val">{result.metadata.interpreted_parameters.instrument}</span>
                  </div>
                  <div className="param-item">
                    <span className="param-label">Tempo</span>
                    <span className="param-val">{result.metadata.tempo_bpm} BPM</span>
                  </div>
                  <div className="param-item">
                    <span className="param-label">Key & Scale</span>
                    <span className="param-val">{result.metadata.key} {result.metadata.scale}</span>
                  </div>
                  <div className="param-item">
                    <span className="param-label">Complexity</span>
                    <span className="param-val">{result.metadata.interpreted_parameters.complexity}</span>
                  </div>
                  <div className="param-item">
                    <span className="param-label">Creativity (Temp)</span>
                    <span className="param-val">{result.metadata.temperature_used}</span>
                  </div>
                  <div className="param-item">
                    <span className="param-label">Events Generated</span>
                    <span className="param-val">{result.metadata.num_events_generated}</span>
                  </div>
                  <div className="param-item">
                    <span className="param-label">Notes / Chords</span>
                    <span className="param-val">{result.metadata.notes_count} N / {result.metadata.chords_count} C</span>
                  </div>
                </div>
              </div>

              {/* Visible AI-Generated Music Disclosure */}
              <div className="ai-disclosure-banner">
                <div className="ai-disclosure-header">
                  <span className="ai-disclosure-icon">🤖</span>
                  <strong>AI-Generated Music Disclosure</strong>
                  <span className="ai-disclosure-badge">MAESTRO v3.0.0 Neural LSTM</span>
                </div>
                <p className="ai-disclosure-body">
                  This musical piece was composed algorithmically using an artificial intelligence neural network (LSTM).
                  It is not performed by human musicians, does not replicate any living artist, and carries no government endorsement.
                  AI-generated music is <strong>not automatically guaranteed to be copyright-free</strong>. Users bear sole responsibility
                  for rights clearance, provenance verification, and proper disclosure before commercial release.
                </p>
                <div className="ai-disclosure-footer">
                  <button
                    type="button"
                    className="ai-disclosure-link-btn"
                    onClick={() => setShowResponsibleAiModal(true)}
                  >
                    📖 View Responsible AI & Provenance Policy
                  </button>
                </div>
              </div>

              {/* User Feedback Widget */}
              <div className="feedback-card">
                <div className="feedback-header">
                  <div>
                    <span className="feedback-title">Rate this Generation:</span>
                    <span className="feedback-disclaimer"> (Collected for future model evaluation & improvement)</span>
                  </div>
                  <div className="feedback-actions-top">
                    <div className="like-dislike-group">
                      <button
                        type="button"
                        className={`btn-thumb ${feedbackIsLiked ? "active" : ""}`}
                        onClick={() => {
                          setFeedbackIsLiked(true)
                          if (feedbackRating < 4) setFeedbackRating(5)
                        }}
                        disabled={feedbackSubmitted}
                        title="Like this composition"
                      >
                        👍 Like
                      </button>
                      <button
                        type="button"
                        className={`btn-thumb ${!feedbackIsLiked ? "active dislike" : ""}`}
                        onClick={() => {
                          setFeedbackIsLiked(false)
                          if (feedbackRating > 2) setFeedbackRating(2)
                        }}
                        disabled={feedbackSubmitted}
                        title="Dislike this composition"
                      >
                        👎 Dislike
                      </button>
                    </div>

                    <div className="star-rating">
                      {[1, 2, 3, 4, 5].map((star) => (
                        <button
                          key={star}
                          type="button"
                          className={`star-btn ${star <= feedbackRating ? "active" : ""}`}
                          onClick={() => {
                            setFeedbackRating(star)
                            setFeedbackIsLiked(star >= 3)
                          }}
                          disabled={feedbackSubmitted}
                          title={`${star} Star${star > 1 ? "s" : ""}`}
                        >
                          ★
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
                {feedbackSubmitted ? (
                  <p className="feedback-success-msg">
                    ✨ Thank you! Your feedback has been recorded for future model evaluation.
                  </p>
                ) : (
                  <div className="feedback-comment-row">
                    <input
                      type="text"
                      className="feedback-input"
                      placeholder="Optional text feedback (e.g., phrasing, harmonic rhythm, dynamics)..."
                      value={feedbackComment}
                      onChange={(e) => setFeedbackComment(e.target.value)}
                    />
                    <button
                      type="button"
                      className="btn btn-outline-sm"
                      onClick={handleSendFeedback}
                      disabled={feedbackSubmitting}
                    >
                      {feedbackSubmitting ? "Submitting..." : "Submit Feedback"}
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Generation History Ledger */}
          <div className="history-section">
            <div className="history-header">
              <div className="history-title-group">
                <span className="history-icon">📜</span>
                <h3 className="history-title">Recent Studio Creations</h3>
              </div>
              <button
                type="button"
                className="btn btn-outline-sm"
                onClick={fetchHistory}
                disabled={loadingHistory}
              >
                {loadingHistory ? "Refreshing..." : "🔄 Refresh"}
              </button>
            </div>

            {history.length === 0 ? (
              <p className="history-empty">No compositions recorded in database yet.</p>
            ) : (
              <div className="history-list">
                {history.map((item) => {
                  const isThisActive = activePlayingId === item.generation_id
                  let buttonLabel = "Load & Play ▶"
                  if (isThisActive) {
                    if (isAudioLoading) {
                      buttonLabel = "Loading..."
                    } else if (isPlaying) {
                      buttonLabel = "Pause ⏸"
                    } else {
                      buttonLabel = "Play ▶"
                    }
                  }

                  return (
                    <div
                      key={item.id || item.generation_id}
                      className={`history-item ${isThisActive ? "history-item-active" : ""}`}
                    >
                      <div className="history-item-main">
                        <div className="history-prompt-row">
                          {isThisActive && (
                            <span
                              className={`history-live-dot ${isPlaying ? "playing" : "paused"}`}
                              title={isPlaying ? "Currently playing" : "Loaded in player"}
                            >
                              {isPlaying ? "▶" : "⏸"}
                            </span>
                          )}
                          <span className="history-prompt">
                            {item.prompt || "Advanced Manual Controls"}
                          </span>
                        </div>
                        <div className="history-meta">
                          <span className="history-badge">{item.instrument}</span>
                          <span>{item.tempo_bpm} BPM</span>
                          <span>Key {item.musical_key} {item.scale}</span>
                          <span>{new Date(item.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
                          {isThisActive && (
                            <span className="history-playing-indicator">
                              {isPlaying ? "Now Playing" : "Loaded"}
                            </span>
                          )}
                        </div>
                      </div>
                      <button
                        type="button"
                        className={`history-load-btn ${isThisActive && isPlaying ? "active-playing" : isThisActive ? "active-paused" : ""}`}
                        onClick={() => {
                          if (isThisActive) {
                            togglePlay()
                          } else {
                            handleLoadHistoryItem(item)
                          }
                        }}
                        disabled={isThisActive && isAudioLoading}
                        title={isThisActive ? (isPlaying ? "Pause playback" : "Resume playback") : "Load and play this track"}
                      >
                        {buttonLabel}
                      </button>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="footer">
        <p>AI Music Studio • Symbolic Deep Learning paired with Groq Natural Language Interpretation</p>
        <div className="footer-disclosure">
          <span>
            ℹ️ <strong>AI Transparency Notice:</strong> All audio and MIDI outputs are generated algorithmically.
            No claim of automatic copyright-free status or government endorsement.{" "}
            <button
              type="button"
              className="footer-policy-link"
              onClick={() => setShowResponsibleAiModal(true)}
            >
              Responsible AI & Provenance Policy
            </button>
          </span>
        </div>
      </footer>

      {/* Authentication Modal */}
      {showAuthModal && (
        <div className="modal-overlay" onClick={() => setShowAuthModal(false)}>
          <div className="auth-modal" onClick={(e) => e.stopPropagation()}>
            <div className="auth-tabs">
              <button
                type="button"
                className={`auth-tab ${authMode === "login" ? "active" : ""}`}
                onClick={() => {
                  setAuthMode("login")
                  setAuthError(null)
                }}
              >
                Sign In
              </button>
              <button
                type="button"
                className={`auth-tab ${authMode === "register" ? "active" : ""}`}
                onClick={() => {
                  setAuthMode("register")
                  setAuthError(null)
                }}
              >
                Create Account
              </button>
            </div>

            <form
              onSubmit={authMode === "login" ? handleLogin : handleRegister}
              className="auth-form"
              noValidate
            >
              {authError && <div className="auth-error">{authError}</div>}

              <div>
                <label className="form-label">{authMode === "login" ? "Email or Username" : "Full Name / Username"}</label>
                <input
                  type="text"
                  required
                  className="auth-input"
                  placeholder={authMode === "login" ? "Email address or username" : "e.g. Wolfgang Amadeus"}
                  value={authUsername}
                  onChange={(e) => setAuthUsername(e.target.value)}
                />
              </div>

              {authMode === "register" && (
                <div>
                  <label className="form-label">Email Address</label>
                  <input
                    type="email"
                    required
                    className="auth-input"
                    placeholder="e.g. artist@aimusicstudio.io"
                    value={authEmail}
                    onChange={(e) => setAuthEmail(e.target.value)}
                  />
                </div>
              )}

              <div>
                <label className="form-label">Password</label>
                <input
                  type="password"
                  required
                  className="auth-input"
                  placeholder="••••••••"
                  value={authPassword}
                  onChange={(e) => setAuthPassword(e.target.value)}
                />
              </div>

              {authMode === "register" && (
                <div>
                  <label className="form-label">Confirm Password</label>
                  <input
                    type="password"
                    required
                    className="auth-input"
                    placeholder="••••••••"
                    value={authConfirmPassword}
                    onChange={(e) => setAuthConfirmPassword(e.target.value)}
                  />
                </div>
              )}

              <div className="auth-modal-actions">
                <button
                  type="button"
                  className="btn btn-outline"
                  onClick={() => setShowAuthModal(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={authLoading}
                >
                  {authLoading
                    ? "Authenticating..."
                    : authMode === "login"
                    ? "Sign In"
                    : "Create Account"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Responsible AI & Dataset Provenance Modal */}
      {showResponsibleAiModal && (
        <div className="modal-overlay" onClick={() => setShowResponsibleAiModal(false)}>
          <div className="responsible-ai-modal" onClick={(e) => e.stopPropagation()}>
            <div className="responsible-ai-header">
              <div className="responsible-ai-title">
                <span style={{ fontSize: "1.5rem" }}>🤖</span>
                <div>
                  <h3>Responsible AI & Dataset Provenance</h3>
                  <p className="responsible-ai-subtitle">AI Music Studio Ethical Standards & Terms of Use</p>
                </div>
              </div>
              <button
                type="button"
                className="modal-close-btn"
                onClick={() => setShowResponsibleAiModal(false)}
                title="Close"
              >
                ✕
              </button>
            </div>

            <div className="responsible-ai-content">
              <section className="rai-section">
                <h4>1. Dataset Provenance & Attribution</h4>
                <p>
                  Trained exclusively on symbolic MIDI from the <strong>MAESTRO (MIDI and Audio Edited for Synchronous Tracks and Organization) Dataset v3.0.0</strong>,
                  curated by Google Magenta and the Minnesota International Piano-e-Competition. Licensed under <strong>Creative Commons Attribution 4.0 (CC BY 4.0)</strong>.
                  Consists of live classical piano competition performances largely drawn from public domain masterworks.
                </p>
              </section>

              <section className="rai-section">
                <h4>2. Model Architecture & Operational Scope</h4>
                <p>
                  The music generation engine is a 2-layer Long Short-Term Memory (LSTM) recurrent neural network that predicts discrete musical events (notes, chords, rests, durations).
                  Natural-language prompts are translated into musical parameters (tempo, mood, key, complexity) via Groq / Llama-3. Groq does not generate the musical tokens.
                </p>
              </section>

              <section className="rai-section">
                <h4>3. Technical Limitations</h4>
                <ul>
                  <li><strong>Classical Polyphony Bias:</strong> Strong harmonic tendency toward solo classical piano textures.</li>
                  <li><strong>Context Horizon:</strong> Operates over a 50-token sequential context window; not designed for long-range multi-movement symphonic continuity.</li>
                  <li><strong>No Vocal/Speech Synthesis:</strong> Generates purely symbolic MIDI performance data and synthesized instrumental WAV audio.</li>
                </ul>
              </section>

              <section className="rai-section">
                <h4>4. Mandatory AI Disclosure</h4>
                <p>
                  Any public performance, broadcast, or commercial release of audio created with this system must clearly disclose
                  that the composition or arrangement was produced using artificial intelligence. Never present machine outputs as unassisted human performance.
                </p>
              </section>

              <section className="rai-section">
                <h4>5. Strict Policy: No Artist Impersonation & No False Attribution</h4>
                <p>
                  Impersonating living musical artists, claiming unauthorized collaboration or endorsement, or attributing AI-generated works
                  to third-party creators is strictly prohibited.
                </p>
              </section>

              <section className="rai-section">
                <h4>6. Copyright Notice & User Responsibility</h4>
                <p>
                  AI Music Studio makes <strong>no claim and gives no warranty that generated music is automatically copyright-free</strong>.
                  In many legal jurisdictions, purely machine-generated artifacts are ineligible for copyright protection. Users bear sole responsibility
                  for verifying originality and conducting melodic clearance before commercial release or synchronization licensing.
                </p>
              </section>

              <section className="rai-section">
                <h4>7. Disclaimers</h4>
                <p>
                  This application has <strong>not</strong> been certified, approved, or endorsed by any government entity or regulatory body.
                  This policy does not constitute formal legal advice. Consult an intellectual property attorney for specific copyright guidance.
                </p>
              </section>
            </div>

            <div className="responsible-ai-actions">
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => setShowResponsibleAiModal(false)}
              >
                Understood & Acknowledged
              </button>
            </div>
          </div>
        </div>
      )}

      {/* SaaS Subscription Plans Modal */}
      {showPlansModal && (
        <div className="modal-overlay" onClick={() => setShowPlansModal(false)}>
          <div className="plans-modal" onClick={(e) => e.stopPropagation()}>
            <div className="plans-modal-header">
              <h3><span>💎</span> AI Music Studio — Plans & Pricing</h3>
              <button
                type="button"
                className="modal-close-btn"
                onClick={() => setShowPlansModal(false)}
                title="Close"
              >
                ✕
              </button>
            </div>

            <div className="plans-modal-body">
              <div style={{ textAlign: "center", marginBottom: "1.5rem" }}>
                <p style={{ color: "var(--text-sub)", fontSize: "0.9rem", margin: "0 auto", maxWidth: "600px" }}>
                  Empower your musical workflow with flexible, transparent subscription plans tailored for creators, studios, schools, and developers.
                </p>
                {currentUser && (
                  <div style={{ marginTop: "0.5rem", fontSize: "0.85rem", color: "var(--cyan)" }}>
                    Currently Active Plan: <strong>{currentUser.subscription_tier || "FREE"}</strong>
                  </div>
                )}
              </div>

              <div className="plans-grid">
                {(plans.length > 0 ? plans : [
                  {
                    tier: "FREE",
                    name: "Free",
                    tagline: "Explore AI Composition",
                    monthly_price_usd: 0,
                    is_popular: false,
                    highlights: ["15 generations/month", "Up to 60s per track", "Direct MIDI download", "Basic NLU", "50 MB storage"],
                    limits: { max_generations_per_month: 15, max_duration_seconds: 60, can_render_audio: true, can_download_audio: false, api_access_allowed: false }
                  },
                  {
                    tier: "CREATOR",
                    name: "Creator",
                    tagline: "For Independent Artists & Producers",
                    monthly_price_usd: 19,
                    is_popular: true,
                    highlights: ["200 generations/month", "Up to 90s per track", "WAV audio downloads", "Advanced Controls", "1 GB storage"],
                    limits: { max_generations_per_month: 200, max_duration_seconds: 90, can_render_audio: true, can_download_audio: true, api_access_allowed: false }
                  },
                  {
                    tier: "PRO",
                    name: "Pro",
                    tagline: "For Professional Game & Film Composers",
                    monthly_price_usd: 49,
                    is_popular: false,
                    highlights: ["1,000 generations/month", "Up to 240s (4 min)", "Project & album management", "REST API (1k calls/day)", "10 GB storage"],
                    limits: { max_generations_per_month: 1000, max_duration_seconds: 240, can_render_audio: true, can_download_audio: true, api_access_allowed: true }
                  },
                  {
                    tier: "EDUCATION",
                    name: "Education",
                    tagline: "For Music Schools & Universities",
                    monthly_price_usd: 15,
                    is_popular: false,
                    highlights: ["500 generations/seat", "Up to 120s per track", "Theory & token analytics", "Classroom sub-accounts", "5 GB storage"],
                    limits: { max_generations_per_month: 500, max_duration_seconds: 120, can_render_audio: true, can_download_audio: true, api_access_allowed: true }
                  },
                  {
                    tier: "ENTERPRISE",
                    name: "Enterprise",
                    tagline: "Custom Infrastructure & Unlimited Scale",
                    monthly_price_usd: null,
                    is_popular: false,
                    highlights: ["Unlimited generations", "Up to 600s (10 min)", "Private cloud deployment", "Custom-tuned model weights", "Dedicated SLA"],
                    limits: { max_generations_per_month: -1, max_duration_seconds: 600, can_render_audio: true, can_download_audio: true, api_access_allowed: true }
                  }
                ]).map((p) => {
                  const isCurrent = currentUser?.subscription_tier?.toUpperCase() === p.tier.toUpperCase() || (!currentUser?.subscription_tier && p.tier === "FREE")
                  return (
                    <div key={p.tier} className={`plan-card ${isCurrent ? "current" : ""} ${p.is_popular ? "popular" : ""}`}>
                      {p.is_popular && <div className="popular-badge">Popular</div>}
                      <div className="plan-name-row">
                        <h4 className="plan-title">{p.name}</h4>
                      </div>
                      <div className="plan-price-block">
                        <span className="plan-price">
                          {p.monthly_price_usd !== null ? `$${p.monthly_price_usd}` : "Custom"}
                        </span>
                        {p.monthly_price_usd !== null && <span className="plan-period"> / mo</span>}
                      </div>
                      <div className="plan-tagline">{p.tagline}</div>

                      <div className="plan-limits-box">
                        <div className="plan-limit-row">
                          <span>Generations:</span>
                          <span className="limit-val">{p.limits?.max_generations_per_month === -1 ? "Unlimited" : `${p.limits?.max_generations_per_month || 15}/mo`}</span>
                        </div>
                        <div className="plan-limit-row">
                          <span>Max Length:</span>
                          <span className="limit-val">{p.limits?.max_duration_seconds || 60}s</span>
                        </div>
                        <div className="plan-limit-row">
                          <span>Audio WAV:</span>
                          <span className="limit-val">{p.limits?.can_render_audio ? "Enabled" : "MIDI Only"}</span>
                        </div>
                        <div className="plan-limit-row">
                          <span>API Access:</span>
                          <span className="limit-val">{p.limits?.api_access_allowed ? "Yes" : "No"}</span>
                        </div>
                      </div>

                      <ul className="plan-features-list">
                        {(p.highlights || []).map((h, i) => (
                          <li key={i}>
                            <span className="check-icon">✓</span>
                            <span>{h}</span>
                          </li>
                        ))}
                      </ul>

                      <button
                        type="button"
                        className={`plan-cta-btn ${isCurrent ? "active-plan" : p.is_popular ? "popular-btn" : ""}`}
                        disabled={isCurrent || planSwitching}
                        onClick={() => handleSwitchTier(p.tier)}
                      >
                        {isCurrent ? "Active Plan" : planSwitching ? "Updating..." : `Switch to ${p.name}`}
                      </button>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default App