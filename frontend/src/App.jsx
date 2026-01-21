import React, { useState, useEffect, useRef, useCallback } from 'react';

// ============ API Client ============
const API_BASE = 'https://trading-refinery-production.up.railway.app';

const api = {
  async get(endpoint) {
    const res = await fetch(`${API_BASE}/api${endpoint}`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },
  async post(endpoint, data = {}) {
    const res = await fetch(`${API_BASE}/api${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },
  async put(endpoint, data = {}) {
    const res = await fetch(`${API_BASE}/api${endpoint}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  }
};

// ============ WebSocket Hook ============
function useWebSocket(onMessage) {
  const wsRef = useRef(null);
  const reconnectRef = useRef(null);

  const connect = useCallback(() => {
    const wsUrl = API_BASE.replace('http', 'ws') + '/ws';
    wsRef.current = new WebSocket(wsUrl);

    wsRef.current.onopen = () => console.log('WS connected');
    wsRef.current.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        onMessage(msg);
      } catch {}
    };
    wsRef.current.onclose = () => {
      reconnectRef.current = setTimeout(connect, 3000);
    };
  }, [onMessage]);

  useEffect(() => {
    connect();
    return () => {
      if (wsRef.current) wsRef.current.close();
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
    };
  }, [connect]);

  return wsRef;
}

// ============ Components ============

function MetricCard({ label, value, unit = '', trend = null, highlight = false }) {
  return (
    <div className={`metric-card ${highlight ? 'highlight' : ''}`}>
      <div className="metric-label">{label}</div>
      <div className="metric-value">
        {value}
        {unit && <span className="metric-unit">{unit}</span>}
      </div>
      {trend !== null && (
        <div className={`metric-trend ${trend >= 0 ? 'positive' : 'negative'}`}>
          {trend >= 0 ? '↑' : '↓'} {Math.abs(trend).toFixed(1)}%
        </div>
      )}
    </div>
  );
}

function StatusBadge({ status }) {
  const colors = {
    running: '#00ff88',
    paused: '#ffaa00',
    stopped: '#666',
    error: '#ff4444'
  };
  return (
    <span className="status-badge" style={{ '--status-color': colors[status] || '#666' }}>
      <span className="status-dot" />
      {status}
    </span>
  );
}

function LogEntry({ event, data, timestamp }) {
  const icons = {
    iteration_started: '▶',
    iteration_complete: '✓',
    backtest_complete: '📊',
    analysis_complete: '🧠',
    phase: '→',
    error: '✗',
    cooldown: '⏱',
    loop_started: '🚀',
    loop_stopped: '⏹'
  };

  const formatData = () => {
    if (event === 'iteration_complete') {
      return `v${data.new_version} | Improvement: ${(data.improvement * 100).toFixed(2)}%`;
    }
    if (event === 'backtest_complete') {
      return `Sharpe: ${data.sharpe?.toFixed(3)} | DD: ${(data.max_drawdown * 100).toFixed(1)}%`;
    }
    if (event === 'analysis_complete') {
      return data.diagnosis?.substring(0, 60) + '...';
    }
    if (event === 'phase') {
      return data.phase;
    }
    if (event === 'cooldown') {
      return `Waiting ${data.seconds}s`;
    }
    return JSON.stringify(data).substring(0, 80);
  };

  return (
    <div className={`log-entry ${event}`}>
      <span className="log-icon">{icons[event] || '•'}</span>
      <span className="log-time">{timestamp}</span>
      <span className="log-event">{event.replace(/_/g, ' ')}</span>
      <span className="log-data">{formatData()}</span>
    </div>
  );
}

function IterationChart({ iterations }) {
  if (!iterations.length) return null;

  const data = iterations.slice().reverse();
  const maxSharpe = Math.max(...data.map(i => i.backtest_result?.sharpe_ratio || 0), 0.1);
  const minSharpe = Math.min(...data.map(i => i.backtest_result?.sharpe_ratio || 0), 0);
  const range = maxSharpe - minSharpe || 1;

  return (
    <div className="iteration-chart">
      <div className="chart-title">Sharpe Ratio Evolution</div>
      <div className="chart-container">
        <div className="chart-y-axis">
          <span>{maxSharpe.toFixed(2)}</span>
          <span>{((maxSharpe + minSharpe) / 2).toFixed(2)}</span>
          <span>{minSharpe.toFixed(2)}</span>
        </div>
        <div className="chart-bars">
          {data.map((iter, i) => {
            const sharpe = iter.backtest_result?.sharpe_ratio || 0;
            const height = ((sharpe - minSharpe) / range) * 100;
            const isImprovement = iter.improvement > 0;
            return (
              <div
                key={iter.id}
                className={`chart-bar ${isImprovement ? 'positive' : 'negative'}`}
                style={{ height: `${Math.max(height, 2)}%` }}
                title={`v${iter.version}: ${sharpe.toFixed(3)}`}
              >
                <span className="bar-label">v{iter.version}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function StrategySelector({ strategies, selected, onSelect, onNew }) {
  const [showNew, setShowNew] = useState(false);
  const [newName, setNewName] = useState('');
  const [newCode, setNewCode] = useState('');
  const [newProjectId, setNewProjectId] = useState('');

  const handleCreate = async () => {
    if (!newName || !newCode) return;
    await onNew(newName, newCode, newProjectId);
    setShowNew(false);
    setNewName('');
    setNewCode('');
    setNewProjectId('');
  };

  return (
    <div className="strategy-selector">
      <div className="selector-header">
        <h3>Strategies</h3>
        <button className="btn-icon" onClick={() => setShowNew(!showNew)}>+</button>
      </div>
      
      {showNew && (
        <div className="new-strategy-form">
          <input
            type="text"
            placeholder="Strategy name"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
          />
          <textarea
            placeholder="Paste QuantConnect Lean code..."
            value={newCode}
            onChange={(e) => setNewCode(e.target.value)}
          />
          <input
            type="text"
            placeholder="QuantConnect Project ID"
            value={newProjectId}
            onChange={(e) => setNewProjectId(e.target.value)}
          />
          <button className="btn-primary" onClick={handleCreate}>Create</button>
        </div>
      )}

      <div className="strategy-list">
        {strategies.map((s) => (
          <div
            key={s.id}
            className={`strategy-item ${selected?.id === s.id ? 'active' : ''}`}
            onClick={() => onSelect(s)}
          >
            <div className="strategy-name">{s.name}</div>
            <div className="strategy-meta">
              v{s.current_version} • Sharpe: {s.best_sharpe?.toFixed(3) || '—'}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ConfigPanel({ config, onUpdate }) {
  const [localConfig, setLocalConfig] = useState(config);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    setLocalConfig(config);
    setDirty(false);
  }, [config]);

  const handleChange = (key, value) => {
    setLocalConfig((c) => ({ ...c, [key]: value }));
    setDirty(true);
  };

  const handleSave = async () => {
    await onUpdate(localConfig);
    setDirty(false);
  };

  return (
    <div className="config-panel">
      <div className="config-header">
        <h3>Configuration</h3>
        {dirty && <button className="btn-small" onClick={handleSave}>Save</button>}
      </div>

      <div className="config-grid">
        <label>
          Max Iterations
          <input
            type="number"
            value={localConfig.max_iterations || ''}
            placeholder="Unlimited"
            onChange={(e) => handleChange('max_iterations', e.target.value ? parseInt(e.target.value) : null)}
          />
        </label>

        <label>
          Cooldown (sec)
          <input
            type="number"
            value={localConfig.backtest_cooldown || 60}
            onChange={(e) => handleChange('backtest_cooldown', parseInt(e.target.value))}
          />
        </label>

        <label>
          Focus Metric
          <select
            value={localConfig.focus_metric || 'sharpe'}
            onChange={(e) => handleChange('focus_metric', e.target.value)}
          >
            <option value="sharpe">Sharpe Ratio</option>
            <option value="drawdown">Max Drawdown</option>
            <option value="return">Total Return</option>
          </select>
        </label>

        <label>
          Improvement Threshold
          <input
            type="number"
            step="0.01"
            value={localConfig.improvement_threshold || 0.01}
            onChange={(e) => handleChange('improvement_threshold', parseFloat(e.target.value))}
          />
        </label>

        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={localConfig.auto_stop_on_plateau ?? true}
            onChange={(e) => handleChange('auto_stop_on_plateau', e.target.checked)}
          />
          Auto-stop on plateau
        </label>
      </div>
    </div>
  );
}

function CodeViewer({ code, title = 'Current Code' }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className={`code-viewer ${expanded ? 'expanded' : ''}`}>
      <div className="code-header" onClick={() => setExpanded(!expanded)}>
        <span>{title}</span>
        <span className="code-toggle">{expanded ? '▼' : '▶'}</span>
      </div>
      {expanded && (
        <pre className="code-content">
          <code>{code}</code>
        </pre>
      )}
    </div>
  );
}

// ============ Main App ============

export default function App() {
  const [strategies, setStrategies] = useState([]);
  const [selectedStrategy, setSelectedStrategy] = useState(null);
  const [iterations, setIterations] = useState([]);
  const [loopStatus, setLoopStatus] = useState({ status: 'stopped' });
  const [config, setConfig] = useState({});
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);

  // Load initial data
  useEffect(() => {
    const loadData = async () => {
      try {
        const [strats, cfg, status] = await Promise.all([
          api.get('/strategies'),
          api.get('/config'),
          api.get('/loop/status')
        ]);
        setStrategies(strats.strategies || []);
        setConfig(cfg.config || {});
        setLoopStatus(status);
      } catch (e) {
        console.error('Load error:', e);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, []);

  // Load iterations when strategy selected
  useEffect(() => {
    if (!selectedStrategy) return;
    api.get(`/iterations/${selectedStrategy.id}`).then((res) => {
      setIterations(res.iterations || []);
    });
  }, [selectedStrategy]);

  // WebSocket handler
  const handleWsMessage = useCallback((msg) => {
    const { event, data } = msg;
    const timestamp = new Date().toLocaleTimeString();
    
    setLogs((prev) => [{ event, data, timestamp }, ...prev].slice(0, 100));

    if (event === 'iteration_complete') {
      // Refresh iterations
      if (selectedStrategy) {
        api.get(`/iterations/${selectedStrategy.id}`).then((res) => {
          setIterations(res.iterations || []);
        });
      }
    }

    if (event === 'loop_started') {
      setLoopStatus((s) => ({ ...s, status: 'running' }));
    }
    if (event === 'loop_stopped') {
      setLoopStatus((s) => ({ ...s, status: 'stopped' }));
    }
  }, [selectedStrategy]);

  useWebSocket(handleWsMessage);

  // Actions
  const handleNewStrategy = async (name, code, qcProjectId) => {
    const res = await api.post('/strategies', { name, code, qc_project_id: qcProjectId });
    setStrategies((s) => [res.strategy, ...s]);
    setSelectedStrategy(res.strategy);
  };

  const handleStartLoop = async () => {
    if (!selectedStrategy) return;
    await api.post('/loop/start', {
      strategy_id: selectedStrategy.id,
      config
    });
    setLoopStatus({ status: 'running', current_strategy: selectedStrategy.id });
  };

  const handleStopLoop = async () => {
    await api.post('/loop/stop');
    setLoopStatus((s) => ({ ...s, status: 'stopped' }));
  };

  const handlePauseLoop = async () => {
    await api.post('/loop/pause');
    setLoopStatus((s) => ({ ...s, status: 'paused' }));
  };

  const handleResumeLoop = async () => {
    await api.post('/loop/resume');
    setLoopStatus((s) => ({ ...s, status: 'running' }));
  };

  const handleUpdateConfig = async (newConfig) => {
    const res = await api.put('/config', newConfig);
    setConfig(res.config);
  };

  // Latest metrics
  const latestIteration = iterations[0];
  const latestResult = latestIteration?.backtest_result;

  if (loading) {
    return (
      <div className="loading">
        <div className="loading-spinner" />
        <div>Initializing Trading Refinery...</div>
      </div>
    );
  }

  return (
    <div className="app">
      <header className="header">
        <div className="header-brand">
          <span className="brand-icon">◈</span>
          <span className="brand-name">Trading Refinery</span>
        </div>
        <div className="header-status">
          <StatusBadge status={loopStatus.status} />
          {loopStatus.current_iteration > 0 && (
            <span className="iteration-count">
              Iteration #{loopStatus.current_iteration}
            </span>
          )}
        </div>
        <div className="header-controls">
          {loopStatus.status === 'stopped' ? (
            <button 
              className="btn-start" 
              onClick={handleStartLoop}
              disabled={!selectedStrategy}
            >
              Start Loop
            </button>
          ) : loopStatus.status === 'running' ? (
            <>
              <button className="btn-pause" onClick={handlePauseLoop}>Pause</button>
              <button className="btn-stop" onClick={handleStopLoop}>Stop</button>
            </>
          ) : (
            <>
              <button className="btn-resume" onClick={handleResumeLoop}>Resume</button>
              <button className="btn-stop" onClick={handleStopLoop}>Stop</button>
            </>
          )}
        </div>
      </header>

      <div className="main-layout">
        <aside className="sidebar">
          <StrategySelector
            strategies={strategies}
            selected={selectedStrategy}
            onSelect={setSelectedStrategy}
            onNew={handleNewStrategy}
          />
          <ConfigPanel config={config} onUpdate={handleUpdateConfig} />
        </aside>

        <main className="content">
          {selectedStrategy ? (
            <>
              <section className="metrics-section">
                <h2>{selectedStrategy.name}</h2>
                <div className="metrics-grid">
                  <MetricCard
                    label="Sharpe Ratio"
                    value={latestResult?.sharpe_ratio?.toFixed(3) || '—'}
                    trend={latestIteration?.improvement ? latestIteration.improvement * 100 : null}
                    highlight
                  />
                  <MetricCard
                    label="Max Drawdown"
                    value={latestResult?.max_drawdown ? (latestResult.max_drawdown * 100).toFixed(1) : '—'}
                    unit="%"
                  />
                  <MetricCard
                    label="Total Return"
                    value={latestResult?.total_return ? (latestResult.total_return * 100).toFixed(1) : '—'}
                    unit="%"
                  />
                  <MetricCard
                    label="Win Rate"
                    value={latestResult?.win_rate ? (latestResult.win_rate * 100).toFixed(0) : '—'}
                    unit="%"
                  />
                  <MetricCard
                    label="Trades"
                    value={latestResult?.trade_count || '—'}
                  />
                  <MetricCard
                    label="Version"
                    value={`v${selectedStrategy.current_version}`}
                  />
                </div>
              </section>

              <IterationChart iterations={iterations} />

              {latestIteration?.analysis && (
                <section className="analysis-section">
                  <h3>Latest Analysis</h3>
                  <div className="analysis-card">
                    <div className="analysis-row">
                      <span className="analysis-label">Diagnosis</span>
                      <span className="analysis-value">{latestIteration.analysis.diagnosis}</span>
                    </div>
                    <div className="analysis-row">
                      <span className="analysis-label">Hypothesis</span>
                      <span className="analysis-value">{latestIteration.analysis.hypothesis}</span>
                    </div>
                    <div className="analysis-row">
                      <span className="analysis-label">Confidence</span>
                      <span className={`confidence-badge ${latestIteration.analysis.confidence}`}>
                        {latestIteration.analysis.confidence}
                      </span>
                    </div>
                  </div>
                </section>
              )}

              <CodeViewer code={selectedStrategy.code} />
            </>
          ) : (
            <div className="empty-state">
              <div className="empty-icon">◈</div>
              <div className="empty-title">Select a Strategy</div>
              <div className="empty-text">
                Choose an existing strategy or create a new one to begin autonomous refinement.
              </div>
            </div>
          )}
        </main>

        <aside className="log-panel">
          <div className="log-header">
            <h3>Activity Log</h3>
            <button className="btn-icon" onClick={() => setLogs([])}>Clear</button>
          </div>
          <div className="log-list">
            {logs.map((log, i) => (
              <LogEntry key={i} {...log} />
            ))}
            {logs.length === 0 && (
              <div className="log-empty">No activity yet</div>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
