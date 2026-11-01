/* Shared helpers for the tax filing & optimization pages. */
(function () {
  'use strict';

  const API_BASE = '/api/tax';

  const navItems = [
    { href: '/tax/dashboard.html', label: 'Dashboard', key: 'dashboard' },
    { href: '/tax/deduction-questionnaire.html', label: 'Deductions', key: 'deductions' },
    { href: '/tax/forms-viewer.html', label: 'Forms', key: 'forms' },
    { href: '/tax/entity-comparison.html', label: 'Entity Compare', key: 'entities' },
    { href: '/tax/estimated-taxes.html', label: 'Estimated Taxes', key: 'estimated' },
    { href: '/tax/audit-docs.html', label: 'Audit Defense', key: 'audit' },
  ];

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function money(value, digits) {
    const n = Number(value || 0);
    return n.toLocaleString('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: digits == null ? 0 : digits,
      maximumFractionDigits: digits == null ? 0 : digits,
    });
  }

  function pct(value) {
    return `${Number(value || 0).toFixed(1)}%`;
  }

  function formatDate(value) {
    if (!value) return '—';
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return escapeHtml(value);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  }

  function queryParam(name) {
    return new URLSearchParams(window.location.search).get(name);
  }

  function withReturn(href) {
    const id = queryParam('return_id');
    if (!id) return href;
    return `${href}${href.includes('?') ? '&' : '?'}return_id=${encodeURIComponent(id)}`;
  }

  async function api(path, options) {
    const config = Object.assign({ credentials: 'same-origin', headers: {} }, options || {});
    if (config.body && !(config.body instanceof FormData)) {
      config.headers['Content-Type'] = config.headers['Content-Type'] || 'application/json';
      if (typeof config.body !== 'string') config.body = JSON.stringify(config.body);
    }
    const response = await fetch(`${API_BASE}${path}`, config);
    const contentType = response.headers.get('content-type') || '';
    const payload = contentType.includes('application/json') ? await response.json() : await response.text();
    if (!response.ok) {
      const detail = payload && payload.detail ? payload.detail : (typeof payload === 'string' ? payload : 'Request failed');
      const error = new Error(Array.isArray(detail) ? detail.map((d) => d.msg || JSON.stringify(d)).join('; ') : detail);
      error.status = response.status;
      throw error;
    }
    return payload;
  }

  function toast(message, type) {
    let host = document.querySelector('.toast-host');
    if (!host) {
      host = document.createElement('div');
      host.className = 'toast-host';
      document.body.appendChild(host);
    }
    const item = document.createElement('div');
    item.className = `toast-item ${type || 'info'}`;
    item.textContent = message;
    host.appendChild(item);
    setTimeout(() => item.remove(), 4200);
  }

  function navBar(active) {
    const links = navItems.map((item) => `
      <li class="nav-item">
        <a class="nav-link ${item.key === active ? 'active' : ''}" href="${withReturn(item.href)}">${item.label}</a>
      </li>`).join('');
    return `
      <nav class="navbar navbar-expand-lg tax-navbar">
        <div class="container">
          <a class="brand" href="/tax/dashboard.html">
            <span class="brand-mark">T</span>
            <span>TaxPilot</span>
          </a>
          <button class="navbar-toggler border-0" type="button" data-bs-toggle="collapse" data-bs-target="#taxNav" aria-controls="taxNav" aria-expanded="false" aria-label="Toggle navigation">
            <span class="navbar-toggler-icon"></span>
          </button>
          <div class="collapse navbar-collapse" id="taxNav">
            <ul class="navbar-nav ms-auto align-items-lg-center gap-lg-1">${links}
              <li class="nav-item ms-lg-2"><a class="nav-link" href="/dashboard/client.html">Marketplace</a></li>
            </ul>
          </div>
        </div>
      </nav>`;
  }

  function mountNav(active) {
    const host = document.getElementById('taxNavRoot');
    if (host) host.innerHTML = navBar(active);
  }

  async function requireAuth() {
    try {
      const response = await fetch('/api/auth/me', { credentials: 'same-origin' });
      if (!response.ok) throw new Error('not authenticated');
      return await response.json();
    } catch (error) {
      const target = window.location.pathname + window.location.search;
      window.location.href = `/auth/login.html?redirect=${encodeURIComponent(target)}`;
      throw error;
    }
  }

  async function getReturns() {
    return api('/returns');
  }

  async function getReturn(id) {
    return api(`/returns/${id}`);
  }

  function statusBadge(status) {
    const value = String(status || 'draft').toLowerCase();
    const cls = value === 'filed' || value === 'accepted' ? 'pill-filed'
      : value === 'ready_to_file' || value === 'in_review' ? 'pill-ready'
      : value === 'rejected' ? 'pill-danger' : 'pill-draft';
    const label = value.replace(/_/g, ' ').replace(/\b\w/g, (m) => m.toUpperCase());
    return `<span class="pill ${cls}">${escapeHtml(label)}</span>`;
  }

  function filingStatusOptions(selected) {
    const options = [
      ['single', 'Single'],
      ['married_filing_jointly', 'Married Filing Jointly'],
      ['married_filing_separately', 'Married Filing Separately'],
      ['head_of_household', 'Head of Household'],
      ['qualifying_surviving_spouse', 'Qualifying Surviving Spouse'],
    ];
    return options.map(([value, label]) =>
      `<option value="${value}" ${value === selected ? 'selected' : ''}>${label}</option>`).join('');
  }

  function entityOptions(selected) {
    const options = [
      ['sole_proprietor', 'Sole Proprietor'],
      ['llc', 'LLC'],
      ['s_corp', 'S-Corp'],
      ['c_corp', 'C-Corp'],
      ['partnership', 'Partnership'],
    ];
    return options.map(([value, label]) =>
      `<option value="${value}" ${value === selected ? 'selected' : ''}>${label}</option>`).join('');
  }

  function stateOptions(selected) {
    const states = ['AL','AK','AZ','AR','CA','CO','CT','DE','DC','FL','GA','HI','ID','IL','IN','IA','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT','VA','WA','WV','WI','WY'];
    return `<option value="">No state</option>` + states.map((code) =>
      `<option value="${code}" ${code === selected ? 'selected' : ''}>${code}</option>`).join('');
  }

  function defaultTaxYear() {
    const now = new Date();
    return now.getMonth() < 3 ? now.getFullYear() - 2 : now.getFullYear() - 1;
  }

  function setLoading(button, loading, label) {
    if (!button) return;
    if (loading) {
      button.dataset.original = button.innerHTML;
      button.disabled = true;
      button.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span>${label || 'Working...'}`;
    } else {
      button.disabled = false;
      if (button.dataset.original) button.innerHTML = button.dataset.original;
    }
  }

  function printHtml(title, bodyHtml) {
    const win = window.open('', '_blank', 'width=900,height=1000');
    if (!win) {
      toast('Allow pop-ups to download or print this form.', 'error');
      return;
    }
    win.document.write(`<!DOCTYPE html><html><head><meta charset="utf-8"><title>${escapeHtml(title)}</title>
      <style>
        body{font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;color:#1e293b;padding:32px;line-height:1.45}
        h1{font-size:20px;text-align:center;text-transform:uppercase;letter-spacing:.04em}
        .sub{text-align:center;color:#64748b;font-size:12px;margin-bottom:24px}
        .line{display:grid;grid-template-columns:70px 1fr 160px;gap:12px;padding:8px 0;border-bottom:1px solid #f1f5f9;font-size:13px}
        .line .amount{text-align:right;font-variant-numeric:tabular-nums;font-weight:600}
        .line .no{color:#64748b;font-weight:600}
        .note{background:#fffbeb;border:1px solid #fde68a;color:#92400e;padding:10px;border-radius:8px;font-size:11px;margin-top:22px}
        table{width:100%;border-collapse:collapse;font-size:12px;margin-top:12px}
        th,td{border:1px solid #cbd5e1;padding:7px;text-align:left}
        th{background:#f8fafc}
        @media print{body{padding:0}}
      </style></head><body>${bodyHtml}<script>window.onload=function(){setTimeout(function(){window.print();},250);}<\/script></body></html>`);
    win.document.close();
  }

  window.Tax = {
    API_BASE, api, money, pct, escapeHtml, formatDate, queryParam, withReturn, toast,
    mountNav, requireAuth, getReturns, getReturn, statusBadge,
    filingStatusOptions, entityOptions, stateOptions, defaultTaxYear, setLoading, printHtml,
  };
})();
