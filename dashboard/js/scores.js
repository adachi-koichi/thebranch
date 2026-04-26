async function loadScores() {
  const tbody = document.getElementById('scoresTableBody');
  const statusEl = document.getElementById('scores-status');

  try {
    const response = await fetch('/api/agents/scores');

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();

    if (statusEl) {
      statusEl.textContent = `最終更新: ${new Date().toLocaleString('ja-JP')}`;
    }

    if (!data || data.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 24px; color: var(--text-secondary);">データなし</td></tr>';
      return;
    }

    tbody.innerHTML = data.map(score => {
      const completionRate = score.completion_rate != null
        ? (score.completion_rate * 100).toFixed(1) + '%'
        : ((score.completed_tasks / Math.max(score.total_tasks, 1)) * 100).toFixed(1) + '%';
      const overallClass = score.overall_score >= 90 ? 'score-high' : score.overall_score >= 70 ? 'score-mid' : 'score-low';
      return `
      <tr>
        <td>${escapeHtml(score.agent_name)}</td>
        <td>${completionRate}</td>
        <td>${score.quality_score.toFixed(1)}</td>
        <td>${score.performance_score.toFixed(1)}</td>
        <td><strong class="${overallClass}">${score.overall_score.toFixed(1)}</strong></td>
        <td>${new Date(score.last_updated).toLocaleString('ja-JP')}</td>
      </tr>`;
    }).join('');

    renderScoresChart(data);

  } catch (error) {
    console.error('スコアデータ取得エラー:', error);
    tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 24px; color: #e74c3c;">データ取得エラー: ${error.message}</td></tr>`;
  }
}

function renderScoresChart(data) {
  const container = document.getElementById('scoresChart');
  if (!container || data.length === 0) return;

  container.innerHTML = '';

  const canvas = document.createElement('canvas');
  canvas.width = container.offsetWidth || 600;
  canvas.height = 240;
  canvas.style.width = '100%';
  canvas.style.maxWidth = '700px';
  container.appendChild(canvas);

  const ctx = canvas.getContext('2d');
  const barWidth = Math.min(60, (canvas.width - 80) / data.length - 12);
  const maxScore = 100;
  const chartHeight = canvas.height - 60;
  const startX = 40;

  ctx.clearRect(0, 0, canvas.width, canvas.height);

  const isDark = document.documentElement.dataset.theme !== 'light' &&
    window.matchMedia('(prefers-color-scheme: dark)').matches;
  const textColor = isDark ? '#c9d1d9' : '#24292e';
  const gridColor = isDark ? '#30363d' : '#d0d7de';
  const barColor = isDark ? '#58a6ff' : '#3B82F6';

  for (let i = 0; i <= 4; i++) {
    const y = 20 + (chartHeight / 4) * i;
    ctx.strokeStyle = gridColor;
    ctx.lineWidth = 0.5;
    ctx.beginPath();
    ctx.moveTo(startX, y);
    ctx.lineTo(canvas.width - 20, y);
    ctx.stroke();
    ctx.fillStyle = textColor;
    ctx.font = '10px sans-serif';
    ctx.textAlign = 'right';
    ctx.fillText(String(100 - i * 25), startX - 4, y + 4);
  }

  data.forEach((score, i) => {
    const barHeight = (score.overall_score / maxScore) * chartHeight;
    const x = startX + i * (barWidth + 12) + 8;
    const y = 20 + chartHeight - barHeight;

    ctx.fillStyle = barColor;
    ctx.beginPath();
    ctx.roundRect ? ctx.roundRect(x, y, barWidth, barHeight, 4) : ctx.rect(x, y, barWidth, barHeight);
    ctx.fill();

    ctx.fillStyle = textColor;
    ctx.font = 'bold 10px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(score.overall_score.toFixed(0), x + barWidth / 2, y - 4);

    const label = score.agent_name.length > 8 ? score.agent_name.slice(0, 7) + '…' : score.agent_name;
    ctx.font = '10px sans-serif';
    ctx.fillText(label, x + barWidth / 2, canvas.height - 6);
  });
}

function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

setInterval(loadScores, 30000);
loadScores();
