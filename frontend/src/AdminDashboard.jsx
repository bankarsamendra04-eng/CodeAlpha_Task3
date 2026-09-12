import { useState, useEffect } from "react"

export default function AdminDashboard({ token, currentUser, onBackToStudio, onLogout }) {
  const [data, setData] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)
  const [activeTab, setActiveTab] = useState("overview") // 'overview', 'generations', 'errors', 'feedback', 'dataset'

  const fetchDashboardData = async () => {
    setIsLoading(true)
    setError(null)
    try {
      const res = await fetch("/api/admin/dashboard", {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })
      if (!res.ok) {
        if (res.status === 401 || res.status === 403) {
          throw new Error("Access Denied: Only ADMIN accounts can access this dashboard.")
        }
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || `Server returned error (${res.status})`)
      }
      const json = await res.json()
      setData(json)
    } catch (err) {
      setError(err.message || "Failed to load dashboard data.")
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchDashboardData()
  }, [token])

  if (isLoading) {
    return (
      <div className="admin-container">
        <div className="admin-loading">
          <div className="spinner" />
          <p>Querying real database records & system telemetry...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="admin-container">
        <div className="admin-error-box">
          <h2>🔒 Access Restricted</h2>
          <p>{error}</p>
          <div className="admin-error-actions">
            <button className="btn btn-primary" onClick={onBackToStudio}>
              Return to Studio
            </button>
            <button className="btn btn-outline" onClick={onLogout}>
              Switch / Log In as Admin
            </button>
          </div>
        </div>
      </div>
    )
  }

  if (!data) return null

  const {
    total_users,
    generations_stats,
    api_usage,
    model_info,
    dataset_status,
    recent_generations,
    feedback,
    avg_rating,
    total_feedback_count,
    likes_count,
    dislikes_count,
    common_feedback_words,
    system_errors,
    daily_trend,
    instrument_distribution,
  } = data

  const maxTrendGen = Math.max(...daily_trend.map((d) => d.generations), 1)

  return (
    <div className="admin-container">
      {/* Admin Top Navigation */}
      <header className="admin-header">
        <div className="admin-header-left">
          <button className="admin-back-btn" onClick={onBackToStudio} title="Return to Studio">
            ← Studio
          </button>
          <div>
            <h1 className="admin-title">
              <span className="admin-badge-icon">🛡️</span> Admin Dashboard
            </h1>
            <p className="admin-subtitle">
              Live operational metrics, MAESTRO dataset state, LSTM v1 telemetry & error monitoring.
            </p>
          </div>
        </div>

        <div className="admin-header-right">
          <span className="admin-user-pill">
            <span className="role-tag">ADMIN</span> {currentUser?.username || data.admin_user}
          </span>
          <button className="btn btn-outline-sm" onClick={fetchDashboardData} title="Refresh metrics">
            🔄 Refresh
          </button>
          <button className="btn btn-outline-sm btn-danger-outline" onClick={onLogout} title="Log Out">
            Logout
          </button>
        </div>
      </header>

      {/* Primary KPI Grid (11 Required Metrics) */}
      <section className="kpi-grid">
        {/* 1. Total Users */}
        <div className="kpi-card">
          <div className="kpi-icon">👥</div>
          <div className="kpi-content">
            <span className="kpi-label">Total Users</span>
            <span className="kpi-value">{total_users}</span>
            <span className="kpi-meta">Registered Creators</span>
          </div>
        </div>

        {/* 2. Total Generations */}
        <div className="kpi-card">
          <div className="kpi-icon">🎼</div>
          <div className="kpi-content">
            <span className="kpi-label">Total Generations</span>
            <span className="kpi-value">{generations_stats.total}</span>
            <span className="kpi-meta">All-Time Compositions</span>
          </div>
        </div>

        {/* 3. Generations Today */}
        <div className="kpi-card">
          <div className="kpi-icon">⚡</div>
          <div className="kpi-content">
            <span className="kpi-label">Generations Today</span>
            <span className="kpi-value">{generations_stats.today}</span>
            <span className="kpi-meta">Since 00:00 UTC</span>
          </div>
        </div>

        {/* 4. Successful Generations */}
        <div className="kpi-card highlight-success">
          <div className="kpi-icon">✅</div>
          <div className="kpi-content">
            <span className="kpi-label">Successful Generations</span>
            <span className="kpi-value">{generations_stats.successful}</span>
            <span className="kpi-meta success-text">
              {generations_stats.success_rate_percent}% Success Rate
            </span>
          </div>
        </div>

        {/* 5. Failed Generations */}
        <div className="kpi-card highlight-danger">
          <div className="kpi-icon">⚠️</div>
          <div className="kpi-content">
            <span className="kpi-label">Failed Generations</span>
            <span className="kpi-value">{generations_stats.failed}</span>
            <span className="kpi-meta danger-text">
              {system_errors.length} Recorded in Logs
            </span>
          </div>
        </div>

        {/* 6. API Usage */}
        <div className="kpi-card">
          <div className="kpi-icon">🌐</div>
          <div className="kpi-content">
            <span className="kpi-label">API Usage (Calls)</span>
            <span className="kpi-value">{api_usage.total_api_calls}</span>
            <span className="kpi-meta">Avg {api_usage.avg_latency_ms} ms</span>
          </div>
        </div>
      </section>

      {/* Model & Dataset Highlights (Metrics 7 & 8) */}
      <section className="tech-specs-grid">
        {/* 7. Model Version */}
        <div className="spec-card">
          <div className="spec-header">
            <h3>🤖 Model Version</h3>
            <span className="badge-tech">{model_info.version}</span>
          </div>
          <div className="spec-body">
            <div className="spec-row">
              <span className="spec-name">Architecture:</span>
              <span className="spec-val">{model_info.architecture}</span>
            </div>
            <div className="spec-row">
              <span className="spec-name">Model Checkpoint:</span>
              <span className="spec-val">{model_info.model_file} ({model_info.model_size_mb} MB)</span>
            </div>
            <div className="spec-row">
              <span className="spec-name">Vocabulary Size:</span>
              <span className="spec-val">{model_info.vocabulary_tokens} Unique Musical Tokens</span>
            </div>
            <div className="spec-row">
              <span className="spec-name">Sequence Window:</span>
              <span className="spec-val">{model_info.sequence_length} Events</span>
            </div>
            <div className="spec-row">
              <span className="spec-name">Status:</span>
              <span className="status-pill status-online">{model_info.training_status}</span>
            </div>
          </div>
        </div>

        {/* 8. Dataset Status */}
        <div className="spec-card">
          <div className="spec-header">
            <h3>🎹 Dataset Status</h3>
            <span className="badge-tech">{dataset_status.name}</span>
          </div>
          <div className="spec-body">
            <div className="spec-row">
              <span className="spec-name">Total MIDI Files:</span>
              <span className="spec-val">{dataset_status.total_midi_files.toLocaleString()} Files (100% Valid)</span>
            </div>
            <div className="spec-row">
              <span className="spec-name">Total Duration:</span>
              <span className="spec-val">{dataset_status.total_duration_hours} Hours</span>
            </div>
            <div className="spec-row">
              <span className="spec-name">Total Symbolic Notes:</span>
              <span className="spec-val">{dataset_status.total_notes.toLocaleString()} Notes ({dataset_status.total_chords.toLocaleString()} Chords)</span>
            </div>
            <div className="spec-row">
              <span className="spec-name">Splits:</span>
              <span className="spec-val">
                Train: {dataset_status.splits.train || 962} | Val: {dataset_status.splits.validation || 137} | Test: {dataset_status.splits.test || 177}
              </span>
            </div>
            <div className="spec-row">
              <span className="spec-name">Preprocessed Cache:</span>
              <span className="status-pill status-online">{dataset_status.processed_cache_status}</span>
            </div>
          </div>
        </div>
      </section>

      {/* Analytics & Charts Row */}
      <section className="charts-row">
        {/* Chart 1: 7-Day Generation Activity */}
        <div className="chart-card">
          <div className="chart-header">
            <h3>📈 7-Day Activity Trend</h3>
            <span className="chart-legend">
              <span className="dot dot-success" /> Success
              <span className="dot dot-danger" /> Failed
            </span>
          </div>
          <div className="bar-chart-container">
            {daily_trend.map((point, idx) => {
              const heightPct = Math.round((point.generations / maxTrendGen) * 100)
              return (
                <div key={idx} className="bar-column">
                  <div className="bar-track">
                    <div
                      className="bar-fill"
                      style={{ height: `${Math.max(heightPct, 6)}%` }}
                      title={`${point.date}: ${point.generations} generations (${point.success} success, ${point.failed} failed)`}
                    />
                  </div>
                  <span className="bar-label">{point.date}</span>
                  <span className="bar-count">{point.generations}</span>
                </div>
              )
            })}
          </div>
        </div>

        {/* Chart 2: Instrument Distribution */}
        <div className="chart-card">
          <div className="chart-header">
            <h3>🎻 Instrument Distribution</h3>
            <span className="chart-legend">Most Popular Selections</span>
          </div>
          <div className="dist-list">
            {instrument_distribution.length === 0 ? (
              <p className="empty-sub">No generation data recorded yet.</p>
            ) : (
              instrument_distribution.map((item, idx) => {
                const totalGens = generations_stats.total || 1
                const pct = Math.round((item.count / totalGens) * 100)
                return (
                  <div key={idx} className="dist-item">
                    <div className="dist-labels">
                      <span className="dist-name">{item.instrument}</span>
                      <span className="dist-count">{item.count} ({pct}%)</span>
                    </div>
                    <div className="dist-bar-track">
                      <div className="dist-bar-fill" style={{ width: `${Math.max(pct, 5)}%` }} />
                    </div>
                  </div>
                )
              })
            )}
          </div>
        </div>
      </section>

      {/* Detailed Tables Tabbed Navigation */}
      <section className="admin-tabs-section">
        <div className="admin-tabs">
          <button
            className={`admin-tab-btn ${activeTab === "overview" ? "active" : ""}`}
            onClick={() => setActiveTab("overview")}
          >
            🎵 Recent Generations ({recent_generations.length})
          </button>
          <button
            className={`admin-tab-btn ${activeTab === "errors" ? "active" : ""}`}
            onClick={() => setActiveTab("errors")}
          >
            ⚠️ System Errors ({system_errors.length})
          </button>
          <button
            className={`admin-tab-btn ${activeTab === "feedback" ? "active" : ""}`}
            onClick={() => setActiveTab("feedback")}
          >
            💬 User Feedback ({total_feedback_count})
          </button>
        </div>

        <div className="tab-content">
          {/* TAB 1: Recent Generations (Metric 9) */}
          {activeTab === "overview" && (
            <div className="admin-table-wrapper">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>User</th>
                    <th>Prompt / Mode</th>
                    <th>Instrument</th>
                    <th>Tempo</th>
                    <th>Status</th>
                    <th>Duration</th>
                    <th>Time (UTC)</th>
                  </tr>
                </thead>
                <tbody>
                  {recent_generations.length === 0 ? (
                    <tr>
                      <td colSpan="8" className="empty-cell">No generation records found.</td>
                    </tr>
                  ) : (
                    recent_generations.map((g) => (
                      <tr key={g.id}>
                        <td><code>{g.generation_id}</code></td>
                        <td><span className="user-tag">{g.username}</span></td>
                        <td className="prompt-cell" title={g.prompt || "Manual controls"}>
                          {g.prompt ? (g.prompt.length > 45 ? `${g.prompt.slice(0, 45)}...` : g.prompt) : "Manual Controls"}
                        </td>
                        <td><span className="badge-inst">{g.instrument}</span></td>
                        <td>{g.tempo_bpm} BPM</td>
                        <td>
                          <span className={`status-tag ${g.generation_status === "completed" ? "status-ok" : "status-err"}`}>
                            {g.generation_status}
                          </span>
                        </td>
                        <td>{g.generation_duration_ms} ms</td>
                        <td>{new Date(g.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}

          {/* TAB 2: System Errors (Metric 11) */}
          {activeTab === "errors" && (
            <div className="admin-table-wrapper">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Generation ID</th>
                    <th>Prompt</th>
                    <th>Exception / Error Information</th>
                    <th>Timestamp</th>
                  </tr>
                </thead>
                <tbody>
                  {system_errors.length === 0 ? (
                    <tr>
                      <td colSpan="4" className="empty-cell success-text">
                        🎉 Zero system errors detected! All generations completed cleanly.
                      </td>
                    </tr>
                  ) : (
                    system_errors.map((e, idx) => (
                      <tr key={idx}>
                        <td><code>{e.generation_id}</code></td>
                        <td>{e.prompt || "Manual Controls"}</td>
                        <td className="error-text"><code>{e.error_info}</code></td>
                        <td>{new Date(e.created_at).toLocaleString()}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}

          {/* TAB 3: User Feedback (STEP 24 Metrics) */}
          {activeTab === "feedback" && (
            <div className="feedback-section">
              {/* Feedback Metrics Bar */}
              <div className="feedback-summary-bar">
                <div className="fb-stat-item">
                  <span className="fb-stat-label">Average Rating</span>
                  <span className="fb-stat-val star-gold">
                    {avg_rating ? `${avg_rating} / 5.0 ⭐` : "No ratings yet"}
                  </span>
                </div>
                <div className="fb-stat-item">
                  <span className="fb-stat-label">Total Submissions</span>
                  <span className="fb-stat-val">{total_feedback_count}</span>
                </div>
                <div className="fb-stat-item">
                  <span className="fb-stat-label">Likes</span>
                  <span className="fb-stat-val success-text">👍 {likes_count || 0}</span>
                </div>
                <div className="fb-stat-item">
                  <span className="fb-stat-label">Dislikes</span>
                  <span className="fb-stat-val danger-text">👎 {dislikes_count || 0}</span>
                </div>
              </div>

              {/* Notice that feedback does not auto-retrain */}
              <div className="feedback-eval-notice">
                <span className="info-icon">ℹ️</span>
                <span>
                  <strong>Model Evaluation & Future Training:</strong> User ratings and reviews are stored for qualitative benchmarking and dataset curation. Feedback is not applied dynamically or automatically to retrain the active LSTM model.
                </span>
              </div>

              {/* Common Feedback Text / Keywords */}
              <div className="common-words-panel">
                <h4>💬 Common Feedback Topics & Keywords:</h4>
                <div className="common-word-tags">
                  {!common_feedback_words || common_feedback_words.length === 0 ? (
                    <span className="no-words">Awaiting text feedback submissions...</span>
                  ) : (
                    common_feedback_words.map((cw, idx) => (
                      <span key={idx} className="word-pill">
                        {cw.word} <span className="word-count">({cw.count})</span>
                      </span>
                    ))
                  )}
                </div>
              </div>

              <div className="admin-table-wrapper">
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>Generation</th>
                      <th>User</th>
                      <th>Rating / Sentiment</th>
                      <th>User Comment / Text Feedback</th>
                      <th>Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {feedback.length === 0 ? (
                      <tr>
                        <td colSpan="5" className="empty-cell">No user feedback submissions yet.</td>
                      </tr>
                    ) : (
                      feedback.map((f) => (
                        <tr key={f.id}>
                          <td><code>{f.generation_id}</code></td>
                          <td><span className="user-tag">{f.username}</span></td>
                          <td>
                            {f.rating ? (
                              <span className="star-display">
                                {"★".repeat(f.rating) + "☆".repeat(5 - f.rating)} ({f.rating}/5)
                              </span>
                            ) : (
                              f.is_liked ? "👍 Liked" : "👎 Disliked"
                            )}
                          </td>
                          <td className="comment-cell">{f.comment || "—"}</td>
                          <td>{new Date(f.created_at).toLocaleDateString()}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </section>
    </div>
  )
}
