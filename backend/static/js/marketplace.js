const API_BASE = '/api';

const ICONS = {
  shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/><path d="m9 12 2 2 4-4"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
  star: '<path d="m12 2 3.09 6.26L22 9.27l-5 4.87L18.18 21 12 17.77 5.82 21 7 14.14l-5-4.87 6.91-1.01L12 2Z"/>',
  check: '<path d="m20 6-11 11-5-5"/>',
  checkCircle: '<circle cx="12" cy="12" r="9"/><path d="m8.5 12 2.5 2.5 4.5-5"/>',
  calendar: '<rect x="3" y="4" width="18" height="18" rx="3"/><path d="M16 2v4M8 2v4M3 10h18"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  message: '<path d="M21 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4Z"/><path d="M8 9h8M8 13h5"/>',
  arrowRight: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  arrowLeft: '<path d="M19 12H5M11 18l-6-6 6-6"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
  dollar: '<path d="M12 2v20M17 6.5c0-2-2.2-3.5-5-3.5S7 4.5 7 6.5s2.2 3 5 3 5 1.5 5 3.5-2.2 3.5-5 3.5-5-1.5-5-3.5"/>',
  chart: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
  briefcase: '<rect x="3" y="7" width="18" height="14" rx="2"/><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M3 12h18"/>',
  lock: '<rect x="4" y="10" width="16" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>',
  credit: '<rect x="2" y="5" width="20" height="14" rx="2"/><path d="M2 10h20M6 15h3"/>',
  spark: '<path d="m12 3 1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9L12 3Z"/><path d="M19 17v4M17 19h4"/>',
  chevronLeft: '<path d="m15 18-6-6 6-6"/>',
  chevronRight: '<path d="m9 18 6-6-6-6"/>',
  chevronDown: '<path d="m6 9 6 6 6-6"/>',
  menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
  x: '<path d="M18 6 6 18M6 6l12 12"/>',
  send: '<path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/>',
  video: '<rect x="2" y="6" width="14" height="12" rx="2"/><path d="m16 10 6-3v10l-6-3"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  edit: '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/>',
  logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5M21 12H9"/>',
  home: '<path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1Z"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.7 1.7 0 0 0-1.88-.34 1.7 1.7 0 0 0-1 1.55V21a2 2 0 1 1-4 0v-.09a1.7 1.7 0 0 0-1.11-1.55 1.7 1.7 0 0 0-1.88.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-1.55-1H3a2 2 0 1 1 0-4h.09A1.7 1.7 0 0 0 4.6 8.9a1.7 1.7 0 0 0-.34-1.88l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.7 1.7 0 0 0 9 4.6h.09A1.7 1.7 0 0 0 10.1 3.05V3a2 2 0 1 1 4 0v.09a1.7 1.7 0 0 0 1 1.55 1.7 1.7 0 0 0 1.88-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.7 1.7 0 0 0 19.4 9v.09a1.7 1.7 0 0 0 1.55 1H21a2 2 0 1 1 0 4h-.09a1.7 1.7 0 0 0-1.51 1Z"/>',
  alert: '<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4M12 17h.01"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
  file: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6M8 13h8M8 17h5"/>',
  award: '<circle cx="12" cy="8" r="5"/><path d="m8.5 12.5-1.5 9 5-3 5 3-1.5-9"/>',
  pin: '<path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="3"/>',
  zap: '<path d="M13 2 3 14h9l-1 8 10-12h-9l1-8Z"/>',
  trash: '<path d="M3 6h18M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2M19 6l-1 15H6L5 6M10 11v6M14 11v6"/>',
  eye: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',
  refresh: '<path d="M21 12a9 9 0 0 1-15.5 6.2L3 16M3 12a9 9 0 0 1 15.5-6.2L21 8"/><path d="M3 21v-5h5M21 3v5h-5"/>'
};

function icon(name, className = '') {
  const path = ICONS[name] || ICONS.info;
  return `<svg class="icon ${className}" viewBox="0 0 24 24" aria-hidden="true">${path}</svg>`;
}

function escapeHtml(value) {
  return String(value === null || value === undefined ? '' : value).replace(/[&<>"']/g, (char) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  }[char]));
}

function money(value, decimals) {
  const amount = Number(value || 0);
  const digits = decimals === undefined
    ? (Math.abs(amount - Math.round(amount)) > 0.004 ? 2 : 0)
    : decimals;
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: digits,
    maximumFractionDigits: digits
  }).format(amount);
}

function parseDate(value) {
  if (value instanceof Date) return value;
  if (!value) return null;
  let text = String(value);
  if (!/[zZ]|[+-]\d{2}:?\d{2}$/.test(text) && text.includes('T')) {
    text = text.replace(' ', 'T');
  }
  const date = new Date(text);
  return Number.isNaN(date.getTime()) ? null : date;
}

function formatDate(value, options = {}) {
  const date = parseDate(value);
  if (!date) return '—';
  return date.toLocaleDateString('en-US', {
    month: options.month || 'short',
    day: options.day || 'numeric',
    year: options.year === undefined ? 'numeric' : options.year
  });
}

function formatTime(value) {
  const date = parseDate(value);
  if (!date) return '—';
  return date.toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit'
  });
}

function formatDateTime(value) {
  const date = parseDate(value);
  if (!date) return '—';
  return `${formatDate(date)} at ${formatTime(date)}`;
}

function dateKey(value) {
  const date = parseDate(value);
  if (!date) return '';
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function timeAgo(value) {
  const date = parseDate(value);
  if (!date) return '';
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
  if (seconds < 60) return 'Just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return formatDate(date, { year: date.getFullYear() === new Date().getFullYear() ? undefined : 'numeric' });
}

function initials(name) {
  const parts = String(name || '').trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return '?';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
}

const AVATAR_TONES = [
  'linear-gradient(135deg,#2563eb,#1e40af)',
  'linear-gradient(135deg,#059669,#047857)',
  'linear-gradient(135deg,#7c3aed,#5b21b6)',
  'linear-gradient(135deg,#0891b2,#0e7490)',
  'linear-gradient(135deg,#d97706,#b45309)',
  'linear-gradient(135deg,#db2777,#9d174d)'
];

function avatar(name, size = '') {
  const text = String(name || '');
  let hash = 0;
  for (let i = 0; i < text.length; i += 1) {
    hash = (hash * 31 + text.charCodeAt(i)) % 997;
  }
  const tone = AVATAR_TONES[hash % AVATAR_TONES.length];
  return `<span class="avatar ${size}" style="background:${tone}" aria-hidden="true">${escapeHtml(initials(text))}</span>`;
}

function stars(rating) {
  const value = Number(rating || 0);
  const rounded = Math.round(value);
  let output = '<span class="stars" aria-hidden="true">';
  for (let i = 1; i <= 5; i += 1) {
    output += `<span class="${i <= rounded ? '' : 'star-empty'}">★</span>`;
  }
  return `${output}</span>`;
}

function ratingBlock(rating, count) {
  const value = Number(rating || 0);
  return `<span class="rating">${stars(value)}<strong>${value.toFixed(1)}</strong><span class="rating-divider">·</span><span>${Number(count || 0)} consultation${Number(count || 0) === 1 ? '' : 's'}</span></span>`;
}

const STATUS_LABELS = {
  pending: 'Pending',
  confirmed: 'Confirmed',
  completed: 'Completed',
  cancelled: 'Cancelled',
  no_show: 'No show'
};

function statusBadge(status) {
  const value = String(status || 'pending').toLowerCase();
  const style = {
    pending: 'badge-amber',
    confirmed: 'badge-primary',
    completed: 'badge-green',
    cancelled: 'badge-red',
    no_show: 'badge-gray'
  }[value] || 'badge-gray';
  return `<span class="badge ${style}"><span class="badge-dot"></span>${STATUS_LABELS[value] || value}</span>`;
}

function serviceTypeLabel(type) {
  return {
    hourly: 'Hourly',
    fixed: 'Fixed price',
    package: 'Package'
  }[type] || 'Service';
}

function minRate(rateCards) {
  if (!Array.isArray(rateCards) || !rateCards.length) return null;
  return Math.min(...rateCards.map((card) => Number(card.price) || 0));
}

function durationLabel(minutes) {
  const value = Number(minutes || 0);
  if (!value) return 'Flexible';
  if (value < 60) return `${value} min`;
  const hours = value / 60;
  return `${Number.isInteger(hours) ? hours : hours.toFixed(1)} hr${hours === 1 ? '' : 's'}`;
}

function queryParam(name) {
  return new URLSearchParams(window.location.search).get(name);
}

function debounce(fn, wait = 200) {
  let timer;
  return function debounced(...args) {
    clearTimeout(timer);
    timer = setTimeout(() => fn.apply(this, args), wait);
  };
}

function setButtonLoading(button, isLoading) {
  if (!button) return;
  if (isLoading) {
    button.classList.add('is-loading');
    button.disabled = true;
  } else {
    button.classList.remove('is-loading');
    button.disabled = false;
  }
}

function getSessionToken() {
  try {
    return window.localStorage.getItem('sessionToken');
  } catch (error) {
    return null;
  }
}

async function api(path, options = {}) {
  const token = getSessionToken();
  const config = {
    credentials: 'same-origin',
    ...options,
    headers: {
      Accept: 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {})
    }
  };

  if (options.body !== undefined && options.body !== null && typeof options.body !== 'string' && !(options.body instanceof FormData)) {
    config.body = JSON.stringify(options.body);
    config.headers['Content-Type'] = 'application/json';
  }

  const url = /^https?:\/\//i.test(path) ? path : `${API_BASE}${path}`;
  let response;
  try {
    response = await fetch(url, config);
  } catch (networkError) {
    const error = new Error('Network error. Please check your connection and try again.');
    error.status = 0;
    error.cause = networkError;
    throw error;
  }

  const raw = await response.text();
  let data = null;
  if (raw) {
    try {
      data = JSON.parse(raw);
    } catch (parseError) {
      data = raw;
    }
  }

  if (!response.ok) {
    let detail = data && typeof data === 'object' ? data.detail : data;
    if (Array.isArray(detail)) {
      detail = detail.map((item) => item.msg || item.message || JSON.stringify(item)).join(', ');
    }
    if (detail && typeof detail === 'object') {
      detail = detail.message || JSON.stringify(detail);
    }
    const error = new Error(detail || `Request failed with status ${response.status}`);
    error.status = response.status;
    error.data = data;
    throw error;
  }

  return data;
}

let currentUserCache;
let currentUserRequest = null;
let currentUserLoaded = false;

async function getCurrentUser(force = false) {
  if (force) {
    currentUserCache = undefined;
    currentUserLoaded = false;
  }
  if (currentUserLoaded) return currentUserCache;
  if (currentUserRequest) return currentUserRequest;

  currentUserRequest = api('/auth/me')
    .then((user) => {
      currentUserCache = user;
      currentUserLoaded = true;
      return user;
    })
    .catch((error) => {
      if (error.status === 401) {
        currentUserCache = null;
        currentUserLoaded = true;
        return null;
      }
      throw error;
    })
    .finally(() => {
      currentUserRequest = null;
    });

  return currentUserRequest;
}

async function logout() {
  try {
    await api('/auth/logout', { method: 'POST' });
  } catch (error) {
    console.error(error);
  }
  currentUserCache = null;
  currentUserLoaded = false;
  try {
    window.localStorage.removeItem('sessionToken');
  } catch (error) {
    console.warn('Could not clear session token', error);
  }
  window.location.href = '/';
}

function toastStack() {
  let stack = document.getElementById('toastStack');
  if (!stack) {
    stack = document.createElement('div');
    stack.id = 'toastStack';
    stack.className = 'toast-stack';
    document.body.appendChild(stack);
  }
  return stack;
}

function showToast(message, type = 'info', duration = 4200) {
  const stack = toastStack();
  const el = document.createElement('div');
  const iconName = type === 'success' ? 'checkCircle' : type === 'error' ? 'alert' : type === 'warning' ? 'alert' : 'info';
  el.className = `toast ${type}`;
  el.setAttribute('role', 'status');
  el.innerHTML = `${icon(iconName)}<span>${escapeHtml(message)}</span><button class="toast-close" type="button" aria-label="Dismiss">×</button>`;
  const close = () => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(8px)';
    el.style.transition = 'opacity .18s, transform .18s';
    setTimeout(() => el.remove(), 200);
  };
  el.querySelector('.toast-close').addEventListener('click', close);
  stack.appendChild(el);
  if (duration > 0) setTimeout(close, duration);
}

function confirmDialog(options = {}) {
  const {
    title = 'Are you sure?',
    message = '',
    confirmText = 'Confirm',
    cancelText = 'Cancel',
    danger = false
  } = options;

  return new Promise((resolve) => {
    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop';
    backdrop.innerHTML = `
      <div class="modal" role="dialog" aria-modal="true" aria-labelledby="confirmTitle">
        <div class="modal-body">
          <h3 id="confirmTitle">${escapeHtml(title)}</h3>
          <p>${escapeHtml(message)}</p>
        </div>
        <div class="modal-actions">
          <button class="btn btn-outline" type="button" data-cancel>${escapeHtml(cancelText)}</button>
          <button class="btn ${danger ? 'btn-danger' : 'btn-primary'}" type="button" data-confirm>${escapeHtml(confirmText)}</button>
        </div>
      </div>`;
    const finish = (value) => {
      backdrop.remove();
      document.removeEventListener('keydown', onKey);
      resolve(value);
    };
    const onKey = (event) => {
      if (event.key === 'Escape') finish(false);
    };
    backdrop.querySelector('[data-cancel]').addEventListener('click', () => finish(false));
    backdrop.querySelector('[data-confirm]').addEventListener('click', () => finish(true));
    backdrop.addEventListener('click', (event) => {
      if (event.target === backdrop) finish(false);
    });
    document.addEventListener('keydown', onKey);
    document.body.appendChild(backdrop);
    backdrop.querySelector('[data-confirm]').focus();
  });
}

function scrollToBottom(element) {
  if (element) {
    element.scrollTop = element.scrollHeight;
  }
}

function navMarkup(active) {
  const items = [
    { key: 'browse', href: '/marketplace/browse.html', label: 'Find experts' },
    { key: 'jobs', href: '/jobs/browse.html', label: 'Job marketplace' },
    { key: 'messages', href: '/messages.html', label: 'Messages' },
    { key: 'client', href: '/dashboard/client.html', label: 'My dashboard' },
    { key: 'professional', href: '/dashboard/professional.html', label: 'For professionals' }
  ];
  return items.map((item) => `<a class="nav-link ${active === item.key ? 'active' : ''}" href="${item.href}">${item.label}</a>`).join('');
}

function renderGuestActions() {
  return `
    <a class="btn btn-ghost btn-sm" href="/auth/login.html">Log in</a>
    <a class="btn btn-primary btn-sm" href="/auth/signup.html">Get started</a>`;
}

function renderUserActions(user) {
  const name = `${user.first_name || ''} ${user.last_name || ''}`.trim() || user.email;
  return `
    <div class="nav-user-wrap">
      <button class="user-chip" type="button" id="userChip" aria-haspopup="true" aria-expanded="false">
        ${avatar(name, 'avatar-sm')}
        <span>${escapeHtml(user.first_name || 'Account')}</span>
        ${icon('chevronDown', 'icon-sm caret')}
      </button>
      <div class="nav-dropdown" id="navDropdown">
        <div class="dropdown-head">
          <strong>${escapeHtml(name)}</strong>
          <span>${escapeHtml(user.email)}</span>
        </div>
        <a class="dropdown-item" href="/dashboard/client.html">${icon('home', 'icon-sm')} Client dashboard</a>
        <a class="dropdown-item" href="/dashboard/professional.html">${icon('briefcase', 'icon-sm')} Professional dashboard</a>
        <a class="dropdown-item" href="/jobs/my-listings.html">${icon('file', 'icon-sm')} My job listings</a>
        <a class="dropdown-item" href="/messages.html">${icon('message', 'icon-sm')} Messages</a>
        <div class="dropdown-divider"></div>
        <button class="dropdown-item danger" type="button" data-logout>${icon('logout', 'icon-sm')} Sign out</button>
      </div>
    </div>`;
}

function hydrateHeader(user) {
  const desktop = document.getElementById('navActions');
  const mobile = document.getElementById('mobileActions');
  const markup = user ? renderUserActions(user) : renderGuestActions();
  if (desktop) desktop.innerHTML = markup;
  if (mobile) {
    mobile.innerHTML = user
      ? `<div class="dropdown-head"><strong>${escapeHtml(`${user.first_name || ''} ${user.last_name || ''}`.trim() || user.email)}</strong><span>${escapeHtml(user.email)}</span></div>
         <a class="dropdown-item" href="/dashboard/client.html">${icon('home', 'icon-sm')} Client dashboard</a>
         <a class="dropdown-item" href="/dashboard/professional.html">${icon('briefcase', 'icon-sm')} Professional dashboard</a>
         <a class="dropdown-item" href="/jobs/my-listings.html">${icon('file', 'icon-sm')} My job listings</a>
         <a class="dropdown-item" href="/messages.html">${icon('message', 'icon-sm')} Messages</a>
         <button class="dropdown-item danger" type="button" data-logout>${icon('logout', 'icon-sm')} Sign out</button>`
      : `<a class="btn btn-outline btn-sm btn-block mb-2" href="/auth/login.html">Log in</a>
         <a class="btn btn-primary btn-sm btn-block" href="/auth/signup.html">Get started</a>`;
  }

  const chip = document.getElementById('userChip');
  const dropdown = document.getElementById('navDropdown');
  if (chip && dropdown) {
    chip.addEventListener('click', (event) => {
      event.stopPropagation();
      const isOpen = dropdown.classList.toggle('open');
      chip.setAttribute('aria-expanded', String(isOpen));
    });
    document.addEventListener('click', (event) => {
      if (!dropdown.contains(event.target) && event.target !== chip && !chip.contains(event.target)) {
        dropdown.classList.remove('open');
        chip.setAttribute('aria-expanded', 'false');
      }
    });
  }
}

function renderHeader(active = '') {
  const mount = document.getElementById('app-header');
  if (!mount) return;

  mount.innerHTML = `
    <header class="site-header">
      <div class="container nav-shell">
        <a class="brand" href="/marketplace/browse.html">
          <span class="brand-mark">${icon('shield', 'icon-lg')}</span>
          <span>TaxSavings</span>
          <span class="brand-sub">Marketplace</span>
        </a>
        <nav class="main-nav" aria-label="Main navigation">
          ${navMarkup(active)}
        </nav>
        <div class="nav-actions" id="navActions">
          ${renderGuestActions()}
        </div>
        <button class="nav-toggle" id="navToggle" type="button" aria-label="Open menu" aria-expanded="false">
          ${icon('menu')}
        </button>
      </div>
      <div class="mobile-menu" id="mobileMenu">
        <div class="container">
          <div class="main-nav-mobile" style="display:flex;flex-direction:column;gap:.15rem">
            ${navMarkup(active)}
          </div>
          <div class="nav-actions" id="mobileActions"></div>
        </div>
      </div>
    </header>`;

  const toggle = document.getElementById('navToggle');
  const menu = document.getElementById('mobileMenu');
  if (toggle && menu) {
    toggle.addEventListener('click', () => {
      const isOpen = menu.classList.toggle('open');
      toggle.setAttribute('aria-expanded', String(isOpen));
      toggle.innerHTML = isOpen ? icon('x') : icon('menu');
    });
    menu.querySelectorAll('a').forEach((link) => {
      link.addEventListener('click', () => {
        menu.classList.remove('open');
        toggle.setAttribute('aria-expanded', 'false');
        toggle.innerHTML = icon('menu');
      });
    });
    window.addEventListener('resize', () => {
      if (window.innerWidth > 900 && menu.classList.contains('open')) {
        menu.classList.remove('open');
        toggle.setAttribute('aria-expanded', 'false');
        toggle.innerHTML = icon('menu');
      }
    });
  }

  document.addEventListener('click', (event) => {
    const logoutButton = event.target.closest('[data-logout]');
    if (logoutButton) {
      event.preventDefault();
      logout();
    }
  });

  getCurrentUser()
    .then((user) => hydrateHeader(user))
    .catch(() => hydrateHeader(null));
}

function renderFooter() {
  const mount = document.getElementById('app-footer');
  if (!mount) return;

  mount.innerHTML = `
    <footer class="site-footer">
      <div class="container">
        <div class="footer-grid">
          <div class="footer-brand">
            <a class="brand" href="/marketplace/browse.html">
              <span class="brand-mark">${icon('shield', 'icon-lg')}</span>
              <span>TaxSavings</span>
              <span class="brand-sub">Marketplace</span>
            </a>
            <p>Connect with vetted tax professionals who help small businesses keep more of what they earn. Clear pricing, secure booking, and expert guidance.</p>
          </div>
          <div class="footer-col">
            <h4>Marketplace</h4>
            <a href="/marketplace/browse.html">Find experts</a>
            <a href="/jobs/browse.html">Job marketplace</a>
            <a href="/dashboard/client.html">My consultations</a>
            <a href="/messages.html">Messages</a>
            <a href="/dashboard/professional.html">For professionals</a>
          </div>
          <div class="footer-col">
            <h4>Trust & safety</h4>
            <span>Vetted professionals</span>
            <span>Secure payments</span>
            <span>Transparent pricing</span>
            <span>Private messaging</span>
          </div>
          <div class="footer-col">
            <h4>Account</h4>
            <a href="/auth/login.html">Log in</a>
            <a href="/auth/signup.html">Create account</a>
            <a href="/docs">API documentation</a>
          </div>
        </div>
        <div class="footer-bottom">
          <p class="footer-disclaimer"><strong>Disclaimer:</strong> TaxSavings Marketplace connects clients with independent tax professionals. Information on this platform is for general informational purposes and does not constitute tax, legal, or financial advice. Always review a professional's credentials before engaging their services.</p>
          <p>&copy; ${new Date().getFullYear()} TaxSavings Marketplace</p>
        </div>
      </div>
    </footer>`;
}

function renderAuthWall(container, options = {}) {
  if (!container) return;
  const redirect = options.redirect || `${window.location.pathname}${window.location.search}`;
  container.innerHTML = `
    <div class="auth-wall">
      <div class="auth-wall-card">
        <div class="icon-box">${icon('lock', 'icon-lg')}</div>
        <h1>${escapeHtml(options.title || 'Sign in to continue')}</h1>
        <p>${escapeHtml(options.message || 'Access your consultations, messages, and secure checkout from your TaxSavings account.')}</p>
        <a class="btn btn-primary btn-lg" href="/auth/login.html?redirect=${encodeURIComponent(redirect)}">Log in</a>
        <a class="btn btn-outline btn-lg" href="/auth/signup.html?redirect=${encodeURIComponent(redirect)}">Create account</a>
      </div>
    </div>`;
}

function emptyState(options = {}) {
  return `
    <div class="empty-state">
      <div class="icon-box">${icon(options.icon || 'file', 'icon-lg')}</div>
      <h3>${escapeHtml(options.title || 'Nothing here yet')}</h3>
      <p>${escapeHtml(options.message || '')}</p>
      ${options.action ? `<a class="btn btn-primary" href="${options.action.href}">${escapeHtml(options.action.label)}</a>` : ''}
    </div>`;
}

function errorState(message, retryId) {
  return `
    <div class="alert alert-error mb-4">
      ${icon('alert')}
      <div>
        <strong>We couldn't load this section.</strong>
        <div class="small">${escapeHtml(message || 'Please try again in a moment.')}</div>
      </div>
      ${retryId ? `<button class="btn btn-outline btn-sm" style="margin-left:auto" id="${retryId}" type="button">${icon('refresh', 'icon-sm')} Retry</button>` : ''}
    </div>`;
}

function spinnerBlock(label = 'Loading...') {
  return `<div class="loading-block"><div class="spinner"></div><span>${escapeHtml(label)}</span></div>`;
}

function bookingIsUpcoming(booking) {
  const date = parseDate(booking.scheduled_at);
  if (!date) return false;
  const status = String(booking.status || '').toLowerCase();
  return date.getTime() >= Date.now() - 60 * 60 * 1000 && status !== 'cancelled' && status !== 'completed' && status !== 'no_show';
}

function makeId(prefix = 'id') {
  return `${prefix}-${Math.random().toString(36).slice(2, 9)}`;
}
