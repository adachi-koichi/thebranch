/**
 * THEBRANCH i18n — client-side Japanese / English switcher
 * Locale preference is persisted in localStorage under "thebranch_lang".
 * Usage:
 *   data-i18n="key"              → element.textContent
 *   data-i18n-html="key"        → element.innerHTML
 *   data-i18n-placeholder="key" → input placeholder attribute
 *   data-i18n-title="key"       → title attribute
 *   data-i18n-aria="key"        → aria-label attribute
 */

const TRANSLATIONS = {
  ja: {
    // ── Brand ─────────────────────────────────────────────────────────────
    'brand.name': 'THEBRANCH',

    // ── Navbar ────────────────────────────────────────────────────────────
    'nav.dashboard': 'ダッシュボード',
    'nav.account': 'アカウント',
    'nav.profile': 'プロフィール',
    'nav.settings': '設定',
    'nav.logout': 'ログアウト',
    'nav.lang_toggle': 'EN',
    'nav.lang_current': '日本語',

    // ── Sidebar ───────────────────────────────────────────────────────────
    'sidebar.dashboard': 'ダッシュボード',
    'sidebar.organizations': '組織管理',
    'sidebar.workflow_builder': 'ワークフロー設計',
    'sidebar.agents': 'エージェント一覧',
    'sidebar.templates': 'テンプレートギャラリー',
    'sidebar.notifications': '通知センター',
    'sidebar.analytics': '分析',
    'sidebar.settings': '設定',

    // ── Dashboard page ────────────────────────────────────────────────────
    'page.dashboard.title': 'ダッシュボード',
    'page.dashboard.period.weekly': '週間',
    'page.dashboard.period.monthly': '月間',
    'page.dashboard.period.yearly': '年間',
    'page.dashboard.kpi.agent_uptime': 'エージェント稼働率',
    'page.dashboard.kpi.agent_uptime_sub': '過去7日間',
    'page.dashboard.kpi.tasks_done': 'タスク完了数',
    'page.dashboard.kpi.tasks_done_sub': '今月',
    'page.dashboard.kpi.monthly_cost': '月次コスト',
    'page.dashboard.kpi.monthly_cost_sub': '使用額',
    'page.dashboard.chart.uptime': '過去7日間のエージェント稼働率',
    'page.dashboard.chart.uptime_label': '稼働率 (%)',
    'page.dashboard.chart.cost': 'コスト内訳',
    'page.dashboard.chart.tasks': '日別タスク完了数（12ヶ月）',
    'page.dashboard.chart.tasks_label': 'タスク完了数',
    'chart.days.mon': '月',
    'chart.days.tue': '火',
    'chart.days.wed': '水',
    'chart.days.thu': '木',
    'chart.days.fri': '金',
    'chart.days.sat': '土',
    'chart.days.sun': '日',
    'chart.months': '1月,2月,3月,4月,5月,6月,7月,8月,9月,10月,11月,12月',
    'chart.cost.api': 'API実行',
    'chart.cost.storage': 'ストレージ',
    'chart.cost.network': '通信',
    'chart.cost.other': 'その他',

    // ── Analytics page ────────────────────────────────────────────────────
    'page.analytics.title': '分析',
    'page.analytics.export': 'エクスポート',
    'page.analytics.filter': 'フィルタ',
    'page.analytics.kpi.total_tasks': '総タスク処理数',
    'page.analytics.kpi.total_tasks_trend': '前月比 +28%',
    'page.analytics.kpi.avg_time': '平均処理時間',
    'page.analytics.kpi.success_rate': '成功率',
    'page.analytics.kpi.success_rate_sub': 'エラー率 0.8%',
    'page.analytics.kpi.roi': 'ROI',
    'page.analytics.kpi.roi_sub': '投資回収率',
    'page.analytics.chart.task_trend': 'タスク処理量の推移（30日間）',
    'page.analytics.chart.dept_success': '部署別成功率',
    'page.analytics.chart.dept_success_label': '成功率 (%)',
    'page.analytics.chart.task_type': 'タスクタイプ別分布',
    'page.analytics.table.title': '詳細パフォーマンス分析',
    'page.analytics.table.dept': '部署',
    'page.analytics.table.this_month': '今月処理数',
    'page.analytics.table.success': '成功数',
    'page.analytics.table.failure': '失敗数',
    'page.analytics.table.success_rate': '成功率',
    'page.analytics.table.avg_time': '平均処理時間',
    'page.analytics.table.trend': 'トレンド',
    'page.analytics.dept.sales': '営業部',
    'page.analytics.dept.finance': '財務部',
    'page.analytics.dept.hr': '人事部',
    'page.analytics.dept.analytics': '分析部',
    'page.analytics.dept.cs': 'カスタマーサポート',
    'page.analytics.insights.title': 'インサイト・アラート',
    'page.analytics.insights.info': 'インサイト:',
    'page.analytics.insights.info_body': '営業部のタスク処理量が過去 3 ヶ月で 35% 増加しています。容量計画の見直しをお勧めします。',
    'page.analytics.insights.warning': '注意:',
    'page.analytics.insights.warning_body': '分析部の処理時間が増加しています（5.2秒 → 6.5秒）。パフォーマンス調査が必要です。',
    'page.analytics.insights.success': '成功:',
    'page.analytics.insights.success_body': '全部署の成功率が 99% を超えています。品質管理の目標を達成しています。',
    'chart.task_types.leads': 'リード処理',
    'chart.task_types.invoices': '請求書処理',
    'chart.task_types.data_analysis': 'データ分析',
    'chart.task_types.support': 'サポートチケット',
    'chart.task_types.other': 'その他',
    'chart.days.range': '1日,5日,10日,15日,20日,25日,30日',

    // ── Notifications page ────────────────────────────────────────────────
    'page.notifications.title': '通知センター',
    'page.notifications.mark_all_read': '全て既読',
    'page.notifications.filter': 'フィルタ',
    'page.notifications.all': 'すべて',
    'page.notifications.unread': '未読',
    'page.notifications.alerts': 'アラート',
    'page.notifications.kpi.urgent': '緊急アラート',
    'page.notifications.kpi.urgent_sub': '直ちに対応が必要',
    'page.notifications.kpi.warning': '警告',
    'page.notifications.kpi.warning_sub': '注意が必要',
    'page.notifications.kpi.info': '情報通知',
    'page.notifications.kpi.info_sub': '一般的なお知らせ',
    'page.notifications.kpi.success': '成功',
    'page.notifications.kpi.success_sub': '完了・成功通知',
    'page.notifications.realtime_title': 'リアルタイムアラート（未読）',
    'page.notifications.history_title': '通知履歴',
    'page.notifications.settings_title': '通知設定',
    'page.notifications.search': '検索...',
    'page.notifications.col.time': '時刻',
    'page.notifications.col.type': 'タイプ',
    'page.notifications.col.message': 'メッセージ',
    'page.notifications.col.source': 'ソース',
    'page.notifications.col.status': 'ステータス',
    'page.notifications.settings.email': 'メール通知を有効にする',
    'page.notifications.settings.slack': 'Slack通知を有効にする',
    'page.notifications.settings.urgent_only': '緊急アラートのみ通知する',
    'page.notifications.settings.save': '設定を保存',

    // ── Organizations page ────────────────────────────────────────────────
    'page.organizations.title': '組織管理',
    'page.organizations.create': '新規組織作成',
    'page.organizations.search': '組織を検索...',

    // ── Workflow builder page ─────────────────────────────────────────────
    'page.workflow.title': 'ワークフロー設計',
    'page.workflow.save': '保存',
    'page.workflow.run': '実行',
    'page.workflow.template': 'テンプレートから作成',

    // ── Cost dashboard page ───────────────────────────────────────────────
    'page.cost.title': 'コストダッシュボード',
    'page.cost.export': 'レポート出力',

    // ── API Keys page ─────────────────────────────────────────────────────
    'page.api_keys.title': 'APIキー管理',
    'page.api_keys.create': '新規APIキー生成',

    // ── Common ────────────────────────────────────────────────────────────
    'common.loading': '読み込み中...',
    'common.error': 'エラー',
    'common.save': '保存',
    'common.cancel': 'キャンセル',
    'common.delete': '削除',
    'common.edit': '編集',
    'common.close': '閉じる',
    'common.search': '検索',
    'common.back': '戻る',
    'common.next': '次へ',
    'common.prev': '前へ',
    'common.confirm': '確認',
    'common.yes': 'はい',
    'common.no': 'いいえ',
    'common.status.active': 'アクティブ',
    'common.status.inactive': '非アクティブ',
    'common.trend.mom': '前月比',
  },

  en: {
    // ── Brand ─────────────────────────────────────────────────────────────
    'brand.name': 'THEBRANCH',

    // ── Navbar ────────────────────────────────────────────────────────────
    'nav.dashboard': 'Dashboard',
    'nav.account': 'Account',
    'nav.profile': 'Profile',
    'nav.settings': 'Settings',
    'nav.logout': 'Logout',
    'nav.lang_toggle': 'JA',
    'nav.lang_current': 'English',

    // ── Sidebar ───────────────────────────────────────────────────────────
    'sidebar.dashboard': 'Dashboard',
    'sidebar.organizations': 'Organizations',
    'sidebar.workflow_builder': 'Workflow Builder',
    'sidebar.agents': 'Agents',
    'sidebar.templates': 'Template Gallery',
    'sidebar.notifications': 'Notifications',
    'sidebar.analytics': 'Analytics',
    'sidebar.settings': 'Settings',

    // ── Dashboard page ────────────────────────────────────────────────────
    'page.dashboard.title': 'Dashboard',
    'page.dashboard.period.weekly': 'Weekly',
    'page.dashboard.period.monthly': 'Monthly',
    'page.dashboard.period.yearly': 'Yearly',
    'page.dashboard.kpi.agent_uptime': 'Agent Uptime',
    'page.dashboard.kpi.agent_uptime_sub': 'Last 7 days',
    'page.dashboard.kpi.tasks_done': 'Tasks Completed',
    'page.dashboard.kpi.tasks_done_sub': 'This month',
    'page.dashboard.kpi.monthly_cost': 'Monthly Cost',
    'page.dashboard.kpi.monthly_cost_sub': 'Usage',
    'page.dashboard.chart.uptime': 'Agent Uptime — Last 7 Days',
    'page.dashboard.chart.uptime_label': 'Uptime (%)',
    'page.dashboard.chart.cost': 'Cost Breakdown',
    'page.dashboard.chart.tasks': 'Daily Tasks Completed (12 months)',
    'page.dashboard.chart.tasks_label': 'Tasks Completed',
    'chart.days.mon': 'Mon',
    'chart.days.tue': 'Tue',
    'chart.days.wed': 'Wed',
    'chart.days.thu': 'Thu',
    'chart.days.fri': 'Fri',
    'chart.days.sat': 'Sat',
    'chart.days.sun': 'Sun',
    'chart.months': 'Jan,Feb,Mar,Apr,May,Jun,Jul,Aug,Sep,Oct,Nov,Dec',
    'chart.cost.api': 'API Execution',
    'chart.cost.storage': 'Storage',
    'chart.cost.network': 'Network',
    'chart.cost.other': 'Other',

    // ── Analytics page ────────────────────────────────────────────────────
    'page.analytics.title': 'Analytics',
    'page.analytics.export': 'Export',
    'page.analytics.filter': 'Filter',
    'page.analytics.kpi.total_tasks': 'Total Tasks Processed',
    'page.analytics.kpi.total_tasks_trend': 'MoM +28%',
    'page.analytics.kpi.avg_time': 'Avg Processing Time',
    'page.analytics.kpi.success_rate': 'Success Rate',
    'page.analytics.kpi.success_rate_sub': 'Error rate 0.8%',
    'page.analytics.kpi.roi': 'ROI',
    'page.analytics.kpi.roi_sub': 'Return on Investment',
    'page.analytics.chart.task_trend': 'Task Volume Trend (30 days)',
    'page.analytics.chart.dept_success': 'Success Rate by Department',
    'page.analytics.chart.dept_success_label': 'Success Rate (%)',
    'page.analytics.chart.task_type': 'Task Type Distribution',
    'page.analytics.table.title': 'Detailed Performance Analysis',
    'page.analytics.table.dept': 'Department',
    'page.analytics.table.this_month': 'This Month',
    'page.analytics.table.success': 'Success',
    'page.analytics.table.failure': 'Failure',
    'page.analytics.table.success_rate': 'Success Rate',
    'page.analytics.table.avg_time': 'Avg Time',
    'page.analytics.table.trend': 'Trend',
    'page.analytics.dept.sales': 'Sales',
    'page.analytics.dept.finance': 'Finance',
    'page.analytics.dept.hr': 'HR',
    'page.analytics.dept.analytics': 'Analytics',
    'page.analytics.dept.cs': 'Customer Support',
    'page.analytics.insights.title': 'Insights & Alerts',
    'page.analytics.insights.info': 'Insight:',
    'page.analytics.insights.info_body': 'Sales task volume has increased 35% over the past 3 months. We recommend reviewing capacity planning.',
    'page.analytics.insights.warning': 'Warning:',
    'page.analytics.insights.warning_body': 'Analytics processing time has increased (5.2s → 6.5s). Performance investigation needed.',
    'page.analytics.insights.success': 'Success:',
    'page.analytics.insights.success_body': 'All departments maintain a success rate above 99%. Quality management goals are being achieved.',
    'chart.task_types.leads': 'Lead Processing',
    'chart.task_types.invoices': 'Invoice Processing',
    'chart.task_types.data_analysis': 'Data Analysis',
    'chart.task_types.support': 'Support Tickets',
    'chart.task_types.other': 'Other',
    'chart.days.range': '1,5,10,15,20,25,30',

    // ── Notifications page ────────────────────────────────────────────────
    'page.notifications.title': 'Notification Center',
    'page.notifications.mark_all_read': 'Mark all as read',
    'page.notifications.filter': 'Filter',
    'page.notifications.all': 'All',
    'page.notifications.unread': 'Unread',
    'page.notifications.alerts': 'Alerts',
    'page.notifications.kpi.urgent': 'Critical Alerts',
    'page.notifications.kpi.urgent_sub': 'Immediate action required',
    'page.notifications.kpi.warning': 'Warnings',
    'page.notifications.kpi.warning_sub': 'Attention needed',
    'page.notifications.kpi.info': 'Informational',
    'page.notifications.kpi.info_sub': 'General notices',
    'page.notifications.kpi.success': 'Success',
    'page.notifications.kpi.success_sub': 'Completed notifications',
    'page.notifications.realtime_title': 'Real-time Alerts (Unread)',
    'page.notifications.history_title': 'Notification History',
    'page.notifications.settings_title': 'Notification Settings',
    'page.notifications.search': 'Search...',
    'page.notifications.col.time': 'Time',
    'page.notifications.col.type': 'Type',
    'page.notifications.col.message': 'Message',
    'page.notifications.col.source': 'Source',
    'page.notifications.col.status': 'Status',
    'page.notifications.settings.email': 'Enable email notifications',
    'page.notifications.settings.slack': 'Enable Slack notifications',
    'page.notifications.settings.urgent_only': 'Critical alerts only',
    'page.notifications.settings.save': 'Save settings',

    // ── Organizations page ────────────────────────────────────────────────
    'page.organizations.title': 'Organizations',
    'page.organizations.create': 'Create Organization',
    'page.organizations.search': 'Search organizations...',

    // ── Workflow builder page ─────────────────────────────────────────────
    'page.workflow.title': 'Workflow Builder',
    'page.workflow.save': 'Save',
    'page.workflow.run': 'Run',
    'page.workflow.template': 'Create from Template',

    // ── Cost dashboard page ───────────────────────────────────────────────
    'page.cost.title': 'Cost Dashboard',
    'page.cost.export': 'Export Report',

    // ── API Keys page ─────────────────────────────────────────────────────
    'page.api_keys.title': 'API Keys',
    'page.api_keys.create': 'Generate API Key',

    // ── Common ────────────────────────────────────────────────────────────
    'common.loading': 'Loading...',
    'common.error': 'Error',
    'common.save': 'Save',
    'common.cancel': 'Cancel',
    'common.delete': 'Delete',
    'common.edit': 'Edit',
    'common.close': 'Close',
    'common.search': 'Search',
    'common.back': 'Back',
    'common.next': 'Next',
    'common.prev': 'Previous',
    'common.confirm': 'Confirm',
    'common.yes': 'Yes',
    'common.no': 'No',
    'common.status.active': 'Active',
    'common.status.inactive': 'Inactive',
    'common.trend.mom': 'MoM',
  },
};

const STORAGE_KEY = 'thebranch_lang';
const SUPPORTED = ['ja', 'en'];

const i18n = (() => {
  let _lang = localStorage.getItem(STORAGE_KEY) || 'ja';
  if (!SUPPORTED.includes(_lang)) _lang = 'ja';

  function t(key) {
    return (TRANSLATIONS[_lang] && TRANSLATIONS[_lang][key]) ||
           (TRANSLATIONS['ja'][key]) ||
           key;
  }

  function getLang() { return _lang; }

  function setLang(lang) {
    if (!SUPPORTED.includes(lang)) return;
    _lang = lang;
    localStorage.setItem(STORAGE_KEY, lang);
    applyTranslations();
    document.documentElement.lang = lang;
    document.dispatchEvent(new CustomEvent('i18n:changed', { detail: { lang } }));
  }

  function toggleLang() {
    setLang(_lang === 'ja' ? 'en' : 'ja');
  }

  function applyTranslations() {
    // textContent
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const key = el.getAttribute('data-i18n');
      el.textContent = t(key);
    });
    // innerHTML (for elements with nested HTML)
    document.querySelectorAll('[data-i18n-html]').forEach(el => {
      const key = el.getAttribute('data-i18n-html');
      el.innerHTML = t(key);
    });
    // placeholder
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
      el.placeholder = t(el.getAttribute('data-i18n-placeholder'));
    });
    // title attribute
    document.querySelectorAll('[data-i18n-title]').forEach(el => {
      el.title = t(el.getAttribute('data-i18n-title'));
    });
    // aria-label
    document.querySelectorAll('[data-i18n-aria]').forEach(el => {
      el.setAttribute('aria-label', t(el.getAttribute('data-i18n-aria')));
    });
    // <html lang="...">
    document.documentElement.lang = _lang;
  }

  // Auto-apply on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', applyTranslations);
  } else {
    applyTranslations();
  }

  return { t, getLang, setLang, toggleLang, applyTranslations };
})();

window.i18n = i18n;
