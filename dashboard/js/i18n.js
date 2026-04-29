(function () {
    'use strict';

    var STORAGE_KEY = 'thebranch_lang';
    var DEFAULT_LANG = 'ja';

    var translations = {
        ja: {
            'brand.name': 'THEBRANCH',

            'nav.dashboard': 'ダッシュボード',
            'nav.account': 'アカウント',
            'nav.profile': 'プロフィール',
            'nav.settings': '設定',
            'nav.logout': 'ログアウト',
            'nav.lang_toggle': 'EN',

            'sidebar.dashboard': 'ダッシュボード',
            'sidebar.organizations': '組織管理',
            'sidebar.workflow_builder': 'ワークフロー設計',
            'sidebar.agents': 'エージェント一覧',
            'sidebar.templates': 'テンプレートギャラリー',
            'sidebar.notifications': '通知センター',
            'sidebar.analytics': '分析',
            'sidebar.settings': '設定',

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

            'page.notifications.title': '通知センター',
            'page.notifications.mark_all_read': 'すべて既読',
            'page.notifications.filter.all': 'すべて',
            'page.notifications.filter.unread': '未読',
            'page.notifications.filter.important': '重要',

            'chart.days.mon': '月',
            'chart.days.tue': '火',
            'chart.days.wed': '水',
            'chart.days.thu': '木',
            'chart.days.fri': '金',
            'chart.days.sat': '土',
            'chart.days.sun': '日',
            'chart.days.range': '1日,5日,10日,15日,20日,25日,30日',
            'chart.months': '1月,2月,3月,4月,5月,6月,7月,8月,9月,10月,11月,12月',
            'chart.cost.api': 'API実行',
            'chart.cost.storage': 'ストレージ',
            'chart.cost.network': '通信',
            'chart.cost.other': 'その他',
            'chart.task_types.leads': 'リード管理',
            'chart.task_types.invoices': '請求処理',
            'chart.task_types.data_analysis': 'データ分析',
            'chart.task_types.support': 'サポート対応',
            'chart.task_types.other': 'その他',

            'common.loading': '読み込み中...',
            'common.error': 'エラーが発生しました',
            'common.save': '保存',
            'common.cancel': 'キャンセル',
            'common.delete': '削除',
            'common.edit': '編集',
            'common.add': '追加',
        },

        en: {
            'brand.name': 'THEBRANCH',

            'nav.dashboard': 'Dashboard',
            'nav.account': 'Account',
            'nav.profile': 'Profile',
            'nav.settings': 'Settings',
            'nav.logout': 'Logout',
            'nav.lang_toggle': 'JA',

            'sidebar.dashboard': 'Dashboard',
            'sidebar.organizations': 'Organizations',
            'sidebar.workflow_builder': 'Workflow Builder',
            'sidebar.agents': 'Agents',
            'sidebar.templates': 'Template Gallery',
            'sidebar.notifications': 'Notifications',
            'sidebar.analytics': 'Analytics',
            'sidebar.settings': 'Settings',

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
            'page.dashboard.chart.uptime': 'Agent Uptime (Last 7 Days)',
            'page.dashboard.chart.uptime_label': 'Uptime (%)',
            'page.dashboard.chart.cost': 'Cost Breakdown',
            'page.dashboard.chart.tasks': 'Daily Tasks Completed (12 Months)',
            'page.dashboard.chart.tasks_label': 'Tasks Completed',

            'page.analytics.title': 'Analytics',
            'page.analytics.export': 'Export',
            'page.analytics.filter': 'Filter',
            'page.analytics.kpi.total_tasks': 'Total Tasks Processed',
            'page.analytics.kpi.total_tasks_trend': '+28% vs last month',
            'page.analytics.kpi.avg_time': 'Avg Processing Time',
            'page.analytics.kpi.success_rate': 'Success Rate',
            'page.analytics.kpi.success_rate_sub': 'Error rate 0.8%',
            'page.analytics.kpi.roi': 'ROI',
            'page.analytics.kpi.roi_sub': 'Return on investment',
            'page.analytics.chart.task_trend': 'Task Volume Trend (30 Days)',
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
            'page.analytics.insights.info_body': 'Sales department task volume has increased 35% over the past 3 months. Capacity planning review recommended.',
            'page.analytics.insights.warning': 'Warning:',
            'page.analytics.insights.warning_body': 'Analytics department processing time is increasing (5.2s → 6.5s). Performance investigation needed.',
            'page.analytics.insights.success': 'Success:',
            'page.analytics.insights.success_body': 'All departments exceed 99% success rate. Quality management goals achieved.',

            'page.notifications.title': 'Notification Center',
            'page.notifications.mark_all_read': 'Mark All Read',
            'page.notifications.filter.all': 'All',
            'page.notifications.filter.unread': 'Unread',
            'page.notifications.filter.important': 'Important',

            'chart.days.mon': 'Mon',
            'chart.days.tue': 'Tue',
            'chart.days.wed': 'Wed',
            'chart.days.thu': 'Thu',
            'chart.days.fri': 'Fri',
            'chart.days.sat': 'Sat',
            'chart.days.sun': 'Sun',
            'chart.days.range': 'Day 1,Day 5,Day 10,Day 15,Day 20,Day 25,Day 30',
            'chart.months': 'Jan,Feb,Mar,Apr,May,Jun,Jul,Aug,Sep,Oct,Nov,Dec',
            'chart.cost.api': 'API Calls',
            'chart.cost.storage': 'Storage',
            'chart.cost.network': 'Network',
            'chart.cost.other': 'Other',
            'chart.task_types.leads': 'Lead Mgmt',
            'chart.task_types.invoices': 'Invoicing',
            'chart.task_types.data_analysis': 'Data Analysis',
            'chart.task_types.support': 'Support',
            'chart.task_types.other': 'Other',

            'common.loading': 'Loading...',
            'common.error': 'An error occurred',
            'common.save': 'Save',
            'common.cancel': 'Cancel',
            'common.delete': 'Delete',
            'common.edit': 'Edit',
            'common.add': 'Add',
        },
    };

    function I18n() {
        this._lang = localStorage.getItem(STORAGE_KEY) || DEFAULT_LANG;
    }

    I18n.prototype.t = function (key) {
        var dict = translations[this._lang] || translations[DEFAULT_LANG];
        return dict[key] !== undefined ? dict[key] : key;
    };

    I18n.prototype.getLang = function () {
        return this._lang;
    };

    I18n.prototype.setLang = function (lang) {
        if (!translations[lang]) return;
        this._lang = lang;
        localStorage.setItem(STORAGE_KEY, lang);
        document.documentElement.lang = lang;
        this.applyTranslations();
        document.dispatchEvent(new CustomEvent('i18n:changed', { detail: { lang: lang } }));
    };

    I18n.prototype.toggleLang = function () {
        this.setLang(this._lang === 'ja' ? 'en' : 'ja');
    };

    I18n.prototype.applyTranslations = function () {
        var self = this;

        document.querySelectorAll('[data-i18n]').forEach(function (el) {
            var key = el.getAttribute('data-i18n');
            el.textContent = self.t(key);
        });

        document.querySelectorAll('[data-i18n-html]').forEach(function (el) {
            var key = el.getAttribute('data-i18n-html');
            el.innerHTML = self.t(key);
        });

        document.querySelectorAll('[data-i18n-placeholder]').forEach(function (el) {
            var key = el.getAttribute('data-i18n-placeholder');
            el.placeholder = self.t(key);
        });

        document.querySelectorAll('[data-i18n-title]').forEach(function (el) {
            var key = el.getAttribute('data-i18n-title');
            el.title = self.t(key);
        });

        document.querySelectorAll('[data-i18n-aria]').forEach(function (el) {
            var key = el.getAttribute('data-i18n-aria');
            el.setAttribute('aria-label', self.t(key));
        });
    };

    var i18n = new I18n();

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () {
            i18n.applyTranslations();
        });
    } else {
        i18n.applyTranslations();
    }

    window.i18n = i18n;
})();
