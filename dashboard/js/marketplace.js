// ============================================
// Marketplace Search & Filter Module
// ============================================

const Marketplace = (() => {
  // State management
  const state = {
    currentPage: 1,
    searchQuery: '',
    selectedCategory: '',
    sortBy: 'installation_count',
    sortOrder: 'desc',
    perPage: 20,
    totalItems: 0,
    agents: []
  };

  // DOM elements
  let elements = {};

  // Initialize module
  function init() {
    cacheElements();
    attachEventListeners();
    loadCategories();
    loadAgents();
  }

  // Cache DOM elements
  function cacheElements() {
    elements = {
      searchInput: document.getElementById('marketplace-search'),
      categoryFilter: document.getElementById('marketplace-category'),
      sortSelect: document.getElementById('marketplace-sort'),
      agentsList: document.getElementById('marketplace-list'),
      pagination: document.getElementById('marketplace-pagination'),
      loader: document.getElementById('marketplace-loader'),
      searchResults: document.getElementById('marketplace-results-count')
    };
  }

  // Attach event listeners
  function attachEventListeners() {
    if (elements.searchInput) {
      elements.searchInput.addEventListener('input', debounce(handleSearch, 300));
    }
    if (elements.categoryFilter) {
      elements.categoryFilter.addEventListener('change', handleCategoryChange);
    }
    if (elements.sortSelect) {
      elements.sortSelect.addEventListener('change', handleSortChange);
    }
  }

  // Debounce utility
  function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  }

  // Load categories
  async function loadCategories() {
    try {
      const response = await fetch('/api/marketplace/categories');
      if (!response.ok) throw new Error('Failed to load categories');

      const categories = await response.json();
      if (elements.categoryFilter) {
        populateCategoryFilter(categories);
      }
    } catch (error) {
      console.error('Error loading categories:', error);
    }
  }

  // Populate category dropdown
  function populateCategoryFilter(categories) {
    const defaultOption = document.createElement('option');
    defaultOption.value = '';
    defaultOption.textContent = '全カテゴリ';
    elements.categoryFilter.appendChild(defaultOption);

    categories.forEach(category => {
      const option = document.createElement('option');
      option.value = category.id;
      option.textContent = category.name;
      elements.categoryFilter.appendChild(option);
    });
  }

  // Handle search
  function handleSearch(e) {
    state.searchQuery = e.target.value.trim();
    state.currentPage = 1;
    loadAgents();
  }

  // Handle category change
  function handleCategoryChange(e) {
    state.selectedCategory = e.target.value;
    state.currentPage = 1;
    loadAgents();
  }

  // Handle sort change
  function handleSortChange(e) {
    const [sortBy, sortOrder] = e.target.value.split(':');
    state.sortBy = sortBy;
    state.sortOrder = sortOrder;
    state.currentPage = 1;
    loadAgents();
  }

  // Load agents
  async function loadAgents() {
    try {
      if (elements.loader) {
        elements.loader.style.display = 'flex';
      }

      const params = new URLSearchParams({
        q: state.searchQuery,
        category: state.selectedCategory,
        sort_by: state.sortBy,
        sort_order: state.sortOrder,
        page: state.currentPage,
        per_page: state.perPage
      });

      const response = await fetch(`/api/marketplace/agents?${params}`);
      if (!response.ok) throw new Error('Failed to load agents');

      const data = await response.json();
      state.agents = data.items;
      state.totalItems = data.total;

      renderAgentsList(data.items);
      renderPagination(Math.ceil(data.total / state.perPage));
      updateResultsCount(data.total);
    } catch (error) {
      console.error('Error loading agents:', error);
      if (elements.agentsList) {
        elements.agentsList.innerHTML = `<p class="error-message">エージェント読込エラー: ${error.message}</p>`;
      }
    } finally {
      if (elements.loader) {
        elements.loader.style.display = 'none';
      }
    }
  }

  // Render agents list
  function renderAgentsList(agents) {
    if (!elements.agentsList) return;

    if (agents.length === 0) {
      elements.agentsList.innerHTML = '<p class="empty-state">該当するエージェントがありません</p>';
      return;
    }

    elements.agentsList.innerHTML = agents.map(agent => `
      <div class="agent-card" data-agent-id="${agent.id}">
        <div class="agent-header">
          ${agent.icon_url ? `<img src="${agent.icon_url}" alt="${agent.name}" class="agent-icon">` : '<div class="agent-icon-placeholder">📦</div>'}
          <div class="agent-info">
            <h3 class="agent-name">${escapeHtml(agent.name)}</h3>
            <p class="agent-description">${escapeHtml(agent.description)}</p>
          </div>
        </div>
        <div class="agent-meta">
          <span class="agent-stat">
            <span class="stat-label">インストール</span>
            <span class="stat-value">${agent.installation_count}</span>
          </span>
          <span class="agent-stat">
            <span class="stat-label">評価</span>
            <span class="stat-value">⭐ ${agent.rating.toFixed(1)}</span>
          </span>
          <span class="agent-stat">
            <span class="stat-label">版</span>
            <span class="stat-value">${escapeHtml(agent.version)}</span>
          </span>
        </div>
        <button class="agent-button" onclick="Marketplace.viewDetail('${agent.id}')">詳細を見る</button>
      </div>
    `).join('');
  }

  // Render pagination
  function renderPagination(totalPages) {
    if (!elements.pagination || totalPages <= 1) {
      if (elements.pagination) {
        elements.pagination.innerHTML = '';
      }
      return;
    }

    let html = '<div class="pagination">';

    // Previous button
    if (state.currentPage > 1) {
      html += `<button class="page-button" onclick="Marketplace.goToPage(${state.currentPage - 1})">← 前へ</button>`;
    }

    // Page numbers
    const startPage = Math.max(1, state.currentPage - 2);
    const endPage = Math.min(totalPages, state.currentPage + 2);

    if (startPage > 1) {
      html += `<button class="page-button" onclick="Marketplace.goToPage(1)">1</button>`;
      if (startPage > 2) {
        html += '<span class="page-ellipsis">...</span>';
      }
    }

    for (let i = startPage; i <= endPage; i++) {
      html += `<button class="page-button ${i === state.currentPage ? 'active' : ''}" onclick="Marketplace.goToPage(${i})">${i}</button>`;
    }

    if (endPage < totalPages) {
      if (endPage < totalPages - 1) {
        html += '<span class="page-ellipsis">...</span>';
      }
      html += `<button class="page-button" onclick="Marketplace.goToPage(${totalPages})">${totalPages}</button>`;
    }

    // Next button
    if (state.currentPage < totalPages) {
      html += `<button class="page-button" onclick="Marketplace.goToPage(${state.currentPage + 1})">次へ →</button>`;
    }

    html += '</div>';
    elements.pagination.innerHTML = html;
  }

  // Update results count
  function updateResultsCount(total) {
    if (elements.searchResults) {
      elements.searchResults.textContent = `${total} 件見つかりました`;
    }
  }

  // View agent detail
  async function viewDetail(agentId) {
    try {
      const response = await fetch(`/api/marketplace/agents/${agentId}`);
      if (!response.ok) throw new Error('Failed to load agent detail');

      const agent = await response.json();
      showDetailModal(agent);
    } catch (error) {
      console.error('Error loading agent detail:', error);
      alert('エージェント情報の読込に失敗しました');
    }
  }

  // Show detail modal
  function showDetailModal(agent) {
    const modal = document.createElement('div');
    modal.className = 'marketplace-modal';
    modal.innerHTML = `
      <div class="modal-overlay" onclick="this.closest('.marketplace-modal').remove()"></div>
      <div class="modal-content">
        <button class="modal-close" onclick="this.closest('.marketplace-modal').remove()">×</button>
        <div class="modal-body">
          ${agent.banner_url ? `<img src="${agent.banner_url}" alt="" class="modal-banner">` : ''}
          <div class="modal-header">
            ${agent.icon_url ? `<img src="${agent.icon_url}" alt="" class="modal-icon">` : '<div class="modal-icon-placeholder">📦</div>'}
            <div>
              <h2>${escapeHtml(agent.name)}</h2>
              <p class="modal-publisher">パブリッシャー: ${escapeHtml(agent.publisher_id)}</p>
            </div>
          </div>
          <div class="modal-description">${escapeHtml(agent.description)}</div>
          ${agent.detailed_description ? `<div class="modal-detailed">${escapeHtml(agent.detailed_description)}</div>` : ''}
          <div class="modal-stats">
            <div class="stat">
              <span class="label">インストール</span>
              <span class="value">${agent.installation_count}</span>
            </div>
            <div class="stat">
              <span class="label">評価</span>
              <span class="value">⭐ ${agent.rating.toFixed(1)}</span>
            </div>
            <div class="stat">
              <span class="label">レビュー</span>
              <span class="value">${agent.review_count}</span>
            </div>
            <div class="stat">
              <span class="label">版</span>
              <span class="value">${escapeHtml(agent.version)}</span>
            </div>
          </div>
          ${agent.capabilities && agent.capabilities.length > 0 ? `
            <div class="modal-section">
              <h3>スキル・機能</h3>
              <div class="tags">
                ${agent.capabilities.map(cap => `<span class="tag">${escapeHtml(cap)}</span>`).join('')}
              </div>
            </div>
          ` : ''}
          ${agent.tags && agent.tags.length > 0 ? `
            <div class="modal-section">
              <h3>タグ</h3>
              <div class="tags">
                ${agent.tags.map(tag => `<span class="tag tag--secondary">${escapeHtml(tag)}</span>`).join('')}
              </div>
            </div>
          ` : ''}
          <div class="modal-actions">
            <button class="btn btn-primary" onclick="Marketplace.installAgent('${agent.id}')">インストール</button>
            ${agent.documentation_url ? `<a href="${escapeHtml(agent.documentation_url)}" target="_blank" class="btn btn-secondary">ドキュメント</a>` : ''}
            ${agent.github_url ? `<a href="${escapeHtml(agent.github_url)}" target="_blank" class="btn btn-secondary">GitHub</a>` : ''}
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
  }

  // Install agent
  async function installAgent(agentId) {
    try {
      const response = await fetch(`/api/marketplace/agents/${agentId}/install`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ organization_id: null, configuration: null })
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'インストール失敗');
      }

      alert('エージェントをインストールしました');
      document.querySelector('.marketplace-modal')?.remove();
    } catch (error) {
      console.error('Error installing agent:', error);
      alert(`インストール失敗: ${error.message}`);
    }
  }

  // Go to page
  function goToPage(page) {
    state.currentPage = page;
    loadAgents();
    if (elements.agentsList) {
      elements.agentsList.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }

  // Escape HTML
  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // Public API
  return {
    init,
    viewDetail,
    installAgent,
    goToPage,
    loadAgents,
    state: () => state
  };
})();

// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', Marketplace.init);
} else {
  Marketplace.init();
}
