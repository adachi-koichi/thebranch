/**
 * RBAC フロントエンド制御 (#2493)
 * ロール階層: owner > manager > member
 */

const ROLE_HIERARCHY = { owner: 3, manager: 2, member: 1 };

window.userRole = 'member';
window.currentUser = null;

async function initRBAC() {
  const token = localStorage.getItem('auth_token');
  if (!token) return;

  try {
    const res = await fetch('/api/auth/me', {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) return;

    const user = await res.json();
    window.currentUser = user;

    const roles = (user.roles || []).map(r => (typeof r === 'object' ? r.role : r));
    window.userRole = roles.length
      ? roles.reduce((best, r) => (ROLE_HIERARCHY[r] > ROLE_HIERARCHY[best] ? r : best), 'member')
      : 'member';

    applyRBAC();
  } catch (e) {
    console.error('RBAC init failed', e);
  }
}

function applyRBAC() {
  const level = ROLE_HIERARCHY[window.userRole] || 1;

  document.querySelectorAll('.admin-only').forEach(el => {
    el.style.display = level >= ROLE_HIERARCHY.owner ? '' : 'none';
  });

  document.querySelectorAll('.manager-only').forEach(el => {
    el.style.display = level >= ROLE_HIERARCHY.manager ? '' : 'none';
  });

  document.querySelectorAll('.member-visible').forEach(el => {
    el.style.display = '';
  });

  const badge = document.getElementById('user-role-badge');
  if (badge) {
    badge.textContent = window.userRole;
    badge.className = `role-badge role-badge--${window.userRole}`;
    badge.style.display = '';
  }
}

// ロール管理モーダル制御
async function openRoleManager() {
  const modal = document.getElementById('rbac-modal');
  if (!modal) return;
  modal.style.display = 'flex';
  await loadUserList();
}

function closeRoleManager() {
  const modal = document.getElementById('rbac-modal');
  if (modal) modal.style.display = 'none';
}

async function loadUserList() {
  const token = localStorage.getItem('auth_token');
  const tbody = document.getElementById('rbac-users-tbody');
  if (!tbody) return;

  tbody.innerHTML = '<tr><td colspan="3">読み込み中...</td></tr>';

  try {
    const res = await fetch('/api/rbac/users', {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) {
      tbody.innerHTML = '<tr><td colspan="3">アクセス権限がありません</td></tr>';
      return;
    }
    const data = await res.json();
    renderUserList(data.users || []);
  } catch (e) {
    tbody.innerHTML = '<tr><td colspan="3">取得エラー</td></tr>';
  }
}

function renderUserList(users) {
  const tbody = document.getElementById('rbac-users-tbody');
  if (!tbody) return;
  tbody.innerHTML = '';

  users.forEach(u => {
    const tr = document.createElement('tr');
    const roles = u.roles || [];
    const roleLabels = roles.length ? roles.join(', ') : 'member';

    tr.innerHTML = `
      <td>${escapeHtml(u.username || u.email || u.id)}</td>
      <td>
        <span class="role-badge role-badge--${roles[0] || 'member'}">${escapeHtml(roleLabels)}</span>
      </td>
      <td class="admin-only">
        <select class="role-select" data-user-id="${escapeHtml(u.id)}">
          <option value="member" ${roles.includes('member') ? 'selected' : ''}>member</option>
          <option value="manager" ${roles.includes('manager') ? 'selected' : ''}>manager</option>
          <option value="owner" ${roles.includes('owner') ? 'selected' : ''}>owner</option>
        </select>
        <button class="btn-role-assign" onclick="assignRole('${escapeHtml(u.id)}', this)">更新</button>
      </td>
    `;
    tbody.appendChild(tr);
  });

  applyRBAC();
}

async function assignRole(userId, btn) {
  const token = localStorage.getItem('auth_token');
  const select = btn.previousElementSibling;
  const newRole = select.value;

  btn.disabled = true;
  try {
    const res = await fetch(`/api/rbac/users/${encodeURIComponent(userId)}/roles`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ role: newRole }),
    });
    if (!res.ok) {
      const err = await res.json();
      alert(err.detail || 'ロール更新に失敗しました');
    } else {
      await loadUserList();
    }
  } catch (e) {
    alert('通信エラーが発生しました');
  } finally {
    btn.disabled = false;
  }
}

function escapeHtml(str) {
  if (str == null) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

document.addEventListener('DOMContentLoaded', initRBAC);
