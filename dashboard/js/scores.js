// ============================================================
//  scores.js — エージェントスコア & 部署別ダッシュボード
//  タスク #2485
// ============================================================

const DEPT_ICONS = {
  'エンジニアリング':   '⚙️',
  'セールス':           '📊',
  '人事':               '👥',
  'カスタマーサポート': '🎧',
  '経理・財務':         '💰',
};

// ── helpers ─────────────────────────────────────────────────

function esc(t) {
  if (t == null) return '';
  const d = document.createElement('div');
  d.textContent = String(t);
  return d.innerHTML;
}

function scoreClass(v) {
  if (v >= 90) return 'score-high';
  if (v >= 75) return 'score-mid';
  return 'score-low';
}

function progressBar(pct, cls) {
  const clamped = Math.min(100, Math.max(0, pct));
  return `<div class="progress-wrap">
    <div class="progress-bar-inner ${cls}" style="width:${clamped}%"></div>
    <span class="progress-label">${clamped.toFixed(1)}%</span>
  </div>`;
}

// ── KPI カード ───────────────────────────────────────────────

function renderKpiCards(agents) {
  const el = document.getElementById('scores-kpi');
  if (!el) return;

  const avg = (arr, fn) => arr.length ? arr.reduce((s, x) => s + fn(x), 0) / arr.length : 0;
  const top = agents.reduce((a, b) => a.overall_score > b.overall_score ? a : b, agents[0]);
  const avgOverall = avg(agents, a => a.overall_score);
  const avgCompletion = avg(agents, a => a.completion_rate * 100);
  const totalTasks = agents.reduce((s, a) => s + a.total_tasks, 0);

  el.innerHTML = `
    <div class="kpi-card">
      <div class="kpi-icon">🤖</div>
      <div class="kpi-value">${agents.length}</div>
      <div class="kpi-label">エージェント数</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-icon">⭐</div>
      <div class="kpi-value ${scoreClass(avgOverall)}">${avgOverall.toFixed(1)}</div>
      <div class="kpi-label">平均総合スコア</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-icon">✅</div>
      <div class="kpi-value">${avgCompletion.toFixed(1)}%</div>
      <div class="kpi-label">平均タスク完了率</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-icon">📋</div>
      <div class="kpi-value">${totalTasks}</div>
      <div class="kpi-label">総タスク数</div>
    </div>
    <div class="kpi-card kpi-top">
      <div class="kpi-icon">🏆</div>
      <div class="kpi-value score-high">${esc(top.agent_name)}</div>
      <div class="kpi-label">トップパフォーマー (${top.overall_score.toFixed(1)})</div>
    </div>`;
}

// ── エージェント詳細テーブル ────────────────────────────────

function renderAgentTable(agents) {
  const tbody = document.getElementById('scoresTableBody');
  if (!tbody) return;

  if (!agents.length) {
    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:24px;color:var(--text-secondary)">データなし</td></tr>';
    return;
  }

  tbody.innerHTML = agents.map(a => {
    const compPct = a.completion_rate * 100;
    const cls = scoreClass(a.overall_score);
    return `<tr>
      <td><strong>${esc(a.agent_name)}</strong></td>
      <td><span class="dept-badge">${esc(DEPT_ICONS[a.department] || '🏢')} ${esc(a.department)}</span></td>
      <td>${progressBar(compPct, scoreClass(compPct))}</td>
      <td>${progressBar(a.quality_score, scoreClass(a.quality_score))}</td>
      <td>${progressBar(a.performance_score, scoreClass(a.performance_score))}</td>
      <td><span class="score-badge ${cls}">${a.overall_score.toFixed(1)}</span></td>
      <td class="task-count">${a.completed_tasks}<span class="task-total">/${a.total_tasks}</span></td>
    </tr>`;
  }).join('');
}

// ── 部署別カード ─────────────────────────────────────────────

function renderDepartmentCards(depts) {
  const el = document.getElementById('dept-cards');
  if (!el) return;

  if (!depts.length) {
    el.innerHTML = '<p style="color:var(--text-secondary)">部署データなし</p>';
    return;
  }

  el.innerHTML = depts.map((d, i) => {
    const icon = DEPT_ICONS[d.department] || '🏢';
    const rank = i === 0 ? '<span class="dept-rank rank-1">🥇 1位</span>'
               : i === 1 ? '<span class="dept-rank rank-2">🥈 2位</span>'
               : i === 2 ? '<span class="dept-rank rank-3">🥉 3位</span>'
               : `<span class="dept-rank rank-other">${i + 1}位</span>`;
    const cls = scoreClass(d.avg_overall_score);
    const compPct = (d.avg_completion_rate * 100).toFixed(1);
    return `
    <div class="dept-card">
      <div class="dept-card-header">
        <span class="dept-card-icon">${icon}</span>
        <div class="dept-card-title">
          <h3>${esc(d.department)}</h3>
          <span class="dept-agent-count">${d.agent_count}名</span>
        </div>
        ${rank}
      </div>
      <div class="dept-score-main">
        <span class="dept-score-value ${cls}">${d.avg_overall_score.toFixed(1)}</span>
        <span class="dept-score-sub">総合スコア</span>
      </div>
      <div class="dept-metrics">
        <div class="dept-metric">
          <span class="dept-metric-label">完了率</span>
          ${progressBar(parseFloat(compPct), scoreClass(parseFloat(compPct)))}
        </div>
        <div class="dept-metric">
          <span class="dept-metric-label">品質</span>
          ${progressBar(d.avg_quality_score, scoreClass(d.avg_quality_score))}
        </div>
        <div class="dept-metric">
          <span class="dept-metric-label">パフォーマンス</span>
          ${progressBar(d.avg_performance_score, scoreClass(d.avg_performance_score))}
        </div>
      </div>
      <div class="dept-footer">
        <span>タスク: ${d.completed_tasks}/${d.total_tasks}</span>
        ${d.top_agent ? `<span>🏆 ${esc(d.top_agent)}</span>` : ''}
      </div>
    </div>`;
  }).join('');
}

// ── メインロード ─────────────────────────────────────────────

async function loadScores() {
  const statusEl = document.getElementById('scores-status');
  try {
    const [agentsRes, deptsRes] = await Promise.all([
      fetch('/api/agents/scores'),
      fetch('/api/departments/scores'),
    ]);

    if (!agentsRes.ok) throw new Error(`agents API: HTTP ${agentsRes.status}`);
    const agents = await agentsRes.json();
    const depts  = deptsRes.ok ? await deptsRes.json() : [];

    renderKpiCards(agents);
    renderAgentTable(agents);
    renderDepartmentCards(depts);

    if (statusEl) {
      statusEl.textContent = `最終更新: ${new Date().toLocaleString('ja-JP')} (${agents.length}件)`;
    }
  } catch (err) {
    console.error('スコアデータ取得エラー:', err);
    const tbody = document.getElementById('scoresTableBody');
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:24px;color:#e74c3c">
        エラー: ${esc(err.message)}</td></tr>`;
    }
    if (statusEl) statusEl.textContent = 'データ取得に失敗しました';
  }
}

setInterval(loadScores, 30000);
loadScores();
