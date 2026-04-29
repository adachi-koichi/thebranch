const GlobalSearch = {
  debounceTimer: null,
  debounceDelay: 300,

  init() {
    const input = document.getElementById('globalSearchInput');
    const resultsDiv = document.getElementById('globalSearchResults');

    if (!input || !resultsDiv) return;

    input.addEventListener('input', (e) => this.handleInput(e));
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') this.closeResults();
    });
    document.addEventListener('click', (e) => {
      if (!e.target.closest('.global-search-container')) {
        this.closeResults();
      }
    });
  },

  handleInput(e) {
    const query = e.target.value.trim();
    clearTimeout(this.debounceTimer);

    if (query.length < 2) {
      this.closeResults();
      return;
    }

    this.debounceTimer = setTimeout(() => {
      this.search(query);
    }, this.debounceDelay);
  },

  async search(query) {
    const resultsDiv = document.getElementById('globalSearchResults');
    if (!resultsDiv) return;

    try {
      const response = await fetch(`/api/search?q=${encodeURIComponent(query)}&search_type=all`);
      if (!response.ok) throw new Error('Search failed');

      const data = await response.json();
      this.displayResults(data.results);
    } catch (error) {
      console.error('Search error:', error);
      resultsDiv.innerHTML = '<div style="padding:8px 12px;color:var(--text-secondary,#6b7280);">Search error</div>';
      resultsDiv.style.display = 'block';
    }
  },

  displayResults(results) {
    const resultsDiv = document.getElementById('globalSearchResults');
    if (!resultsDiv) return;

    if (results.length === 0) {
      resultsDiv.innerHTML = '<div style="padding:8px 12px;color:var(--text-secondary,#6b7280);">No results found</div>';
      resultsDiv.style.display = 'block';
      return;
    }

    const typeBadges = {
      department: { bg: '#DCFCE7', color: '#166534', label: '部署' },
      workflow: { bg: '#FED7AA', color: '#92400E', label: 'ワークフロー' },
      team: { bg: '#F3E8FF', color: '#7C3AED', label: 'チーム' }
    };

    const html = results.map(r => {
      const badge = typeBadges[r.type] || typeBadges.task;
      return `
        <div style="padding:10px 12px;border-bottom:1px solid var(--border-color,#f3f4f6);cursor:pointer;transition:background 0.2s;"
             onmouseenter="this.style.background='var(--bg-tertiary,#f0f4f8)'"
             onmouseleave="this.style.background='transparent'"
             onclick="window.location.href='${this.escapeHtml(r.url)}'">
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
            <span style="display:inline-block;padding:2px 6px;border-radius:3px;font-size:0.7rem;font-weight:500;background-color:${badge.bg};color:${badge.color};">${badge.label}</span>
            <span style="font-weight:500;color:var(--text-primary,#1f2328);">${this.escapeHtml(r.title)}</span>
          </div>
          ${r.description ? `<div style="font-size:0.75rem;color:var(--text-secondary,#6b7280);line-height:1.3;">${this.escapeHtml(r.description.substring(0, 100))}</div>` : ''}
        </div>
      `;
    }).join('');

    resultsDiv.innerHTML = html;
    resultsDiv.style.display = 'block';
  },

  closeResults() {
    const resultsDiv = document.getElementById('globalSearchResults');
    if (resultsDiv) {
      resultsDiv.style.display = 'none';
    }
  },

  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
};

document.addEventListener('DOMContentLoaded', () => {
  GlobalSearch.init();
});
