/* =====================================================================
   BookPod core: theme, API client, Google sign-in, shared components.
   Everything the pages show comes from the Django REST API under /api/.
   ===================================================================== */
(function(){
'use strict';

/* ---------- small helpers ---------- */
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const qp = k => new URLSearchParams(location.search).get(k);
const fmtDate = iso => { if(!iso) return ''; const d = new Date(iso + (iso.length === 10 ? 'T00:00:00' : '')); return isNaN(d) ? '' : d.toLocaleDateString('en-US', {month:'short', year:'numeric'}); };
const fmtDay = iso => { const d = new Date(iso); return isNaN(d) ? '' : d.toLocaleDateString('en-US', {day:'numeric', month:'short', year:'numeric'}); };
const bookUrl = b => '/book/' + encodeURIComponent(b.slug) + '/';
const fileExt = url => { const m = /\.([a-z0-9]+)(?:\?|$)/i.exec(url || ''); return m ? m[1].toUpperCase() : ''; };

/* ---------- icons (category icons are chosen in Django admin by key) ---------- */
const ICONS = {
  code: '<path d="m9 8-4 4 4 4"/><path d="m15 8 4 4-4 4"/><path d="m13 6-2 12"/>',
  video: '<rect x="3" y="5" width="14" height="14" rx="2"/><path d="M21 8v8l-4-3.2V11.2Z"/>',
  bible: '<path d="M12 5C10 3.5 6.5 3 4 3.5v15c2.5-.5 6 0 8 1.5"/><path d="M12 5c2-1.5 5.5-2 8-1.5v15c-2.5-.5-6 0-8 1.5"/><path d="M12 5v16"/>',
  graduation: '<path d="M2 9.5 12 5l10 4.5-10 4.5-10-4.5Z"/><path d="M6 11.5v5c0 1.4 2.7 2.5 6 2.5s6-1.1 6-2.5v-5"/><path d="M22 9.5V16"/>',
  books: '<rect x="3" y="4" width="7" height="16" rx="1"/><rect x="11.3" y="6" width="7" height="14" rx="1" transform="rotate(4 14.8 13)"/>',
  science: '<path d="M9 3h6"/><path d="M10 3v6L4.5 19a1.5 1.5 0 0 0 1.3 2.2h12.4a1.5 1.5 0 0 0 1.3-2.2L14 9V3"/><path d="M7.5 15h9"/>',
  business: '<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2"/><path d="M3 13h18"/>',
  fiction: '<path d="M12 3c-3 0-6 2-6 5.5 0 2 1 3 2 4s1 2 1 3.5h6c0-1.5 0-2.5 1-3.5s2-2 2-4C18 5 15 3 12 3Z"/><path d="M10 19h4"/><path d="M10.5 21.5h3"/>',
  tag: '<path d="M12 2h7a1 1 0 0 1 1 1v7l-9.5 9.5a1 1 0 0 1-1.4 0L2.5 13a1 1 0 0 1 0-1.4L12 2Z"/><circle cx="15.5" cy="6.5" r="1.2"/>',
  layers: '<path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 13 9 5 9-5"/>',
  shelfbook: '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>',
  download: '<path d="M12 3v12m0 0 4-4m-4 4-4-4M4 21h16"/>',
  calendar: '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
  file: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14,2 14,8 20,8"/>',
  check: '<path d="m5 12 5 5 9-10"/>',
  sparkle: '<path d="m12 2 2.4 5.4L20 9.8l-5.6 2.4L12 18l-2.4-5.8L4 9.8l5.6-2.4Z"/>',
};
const iconSvg = (name, size) => `<svg width="${size||16}" height="${size||16}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name] || ''}</svg>`;

/* ---------- theme (a display preference only; has nothing to do with sign-in) ---------- */
function toggleTheme(){
  const next = (document.documentElement.getAttribute('data-theme') || 'light') === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  try { localStorage.setItem('bp-theme', next); } catch(e){}
}
function toggleMenu(){
  const open = document.getElementById('mobileMenu').classList.toggle('open');
  const btn = document.getElementById('menuBtn');
  btn.classList.toggle('open', open);
  btn.setAttribute('aria-expanded', String(open));
}

/* ---------- API client ---------- */
function csrfToken(){
  const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]*)/);
  return m ? decodeURIComponent(m[1]) : '';
}
function firstError(data){
  if(!data || typeof data !== 'object') return '';
  for(const v of Object.values(data)){
    if(Array.isArray(v) && v.length) return String(v[0]);
    if(typeof v === 'string') return v;
  }
  return '';
}
async function api(path, opts){
  opts = opts || {};
  const method = (opts.method || 'GET').toUpperCase();
  const headers = {'Accept': 'application/json'};
  let body;
  if(opts.body !== undefined){ headers['Content-Type'] = 'application/json'; body = JSON.stringify(opts.body); }
  if(method !== 'GET' && method !== 'HEAD') headers['X-CSRFToken'] = csrfToken();
  const res = await fetch('/api' + path, {method, headers, body, credentials: 'same-origin'});
  let data = null;
  if(res.status !== 204){ try { data = await res.json(); } catch(e){} }
  if(!res.ok){
    const err = new Error((data && (data.detail || firstError(data))) || 'Something went wrong (' + res.status + ').');
    err.status = res.status; err.data = data;
    throw err;
  }
  return data;
}

/* ---------- toast ---------- */
function toast(msg){
  let stack = document.querySelector('.toast-stack');
  if(!stack){ stack = document.createElement('div'); stack.className = 'toast-stack'; stack.setAttribute('role', 'status'); document.body.appendChild(stack); }
  const el = document.createElement('div');
  el.className = 'toast';
  el.innerHTML = iconSvg('sparkle', 14) + '<span>' + esc(msg) + '</span>';
  stack.appendChild(el);
  setTimeout(() => el.remove(), 2900);
}

/* =====================================================================
   AUTH — Google Sign-In / One Tap. The browser only ever sends Google's
   signed ID token; Django verifies it and creates the session.
   ===================================================================== */
const state = {user: null, googleClientId: null};
let gisPromise = null, gisInitialised = false;

function userInitial(u){ return ((u.first_name || u.name || u.email || '?').trim()[0] || '?').toUpperCase(); }

function renderAuth(){
  const signIn = document.getElementById('signInBtn');
  const menu = document.getElementById('userMenu');
  if(!signIn || !menu) return;
  const u = state.user;
  signIn.hidden = !!u;
  menu.hidden = !u;
  if(u){
    const av = document.getElementById('avatarBtn');
    av.innerHTML = u.picture ? '<img src="' + esc(u.picture) + '" alt="" referrerpolicy="no-referrer">' : esc(userInitial(u));
    document.getElementById('userName').textContent = u.name || '';
    document.getElementById('userMail').textContent = u.email || '';
  } else {
    const pop = document.getElementById('userPop');
    if(pop) pop.hidden = true;
  }
}

function setAuthMsg(text, isError){
  const el = document.getElementById('authMsg');
  if(!el) return;
  el.textContent = text || '';
  el.classList.toggle('error', !!isError);
}

function loadGoogle(){
  if(!state.googleClientId) return Promise.reject(new Error('not-configured'));
  if(gisPromise) return gisPromise;
  gisPromise = new Promise((resolve, reject) => {
    const s = document.createElement('script');
    s.src = 'https://accounts.google.com/gsi/client';
    s.async = true; s.defer = true;
    s.onload = () => {
      if(!gisInitialised){
        window.google.accounts.id.initialize({
          client_id: state.googleClientId,
          callback: onGoogleCredential,
          ux_mode: 'popup',
          auto_select: false,
          cancel_on_tap_outside: true,
          use_fedcm_for_prompt: true,
        });
        gisInitialised = true;
      }
      resolve(window.google);
    };
    s.onerror = () => { gisPromise = null; reject(new Error('load-failed')); };
    document.head.appendChild(s);
  });
  return gisPromise;
}

async function onGoogleCredential(response){
  setAuthMsg('Signing you in…');
  try {
    const data = await api('/auth/google/', {method: 'POST', body: {credential: response.credential}});
    state.user = data.user;
    renderAuth();
    const dlg = document.getElementById('authModal');
    if(dlg && dlg.open) dlg.close();
    setAuthMsg('');
    toast('Welcome, ' + (state.user.first_name || state.user.name) + '!');
    document.dispatchEvent(new CustomEvent('bp:auth', {detail: state.user}));
  } catch(err){
    setAuthMsg(err.message || 'Sign-in failed. Please try again.', true);
  }
}

async function openAuth(message){
  const dlg = document.getElementById('authModal');
  if(!dlg) return;
  await ready;
  setAuthMsg(message || '');
  if(!dlg.open) dlg.showModal();
  const holder = document.getElementById('googleBtnHolder');
  holder.innerHTML = '';
  if(!state.googleClientId){
    setAuthMsg('Google sign-in is not set up on this server yet. The site owner needs to add a GOOGLE_CLIENT_ID.', true);
    return;
  }
  try {
    const google = await loadGoogle();
    google.accounts.id.renderButton(holder, {
      type: 'standard', theme: document.documentElement.getAttribute('data-theme') === 'dark' ? 'filled_black' : 'outline',
      size: 'large', shape: 'pill', text: 'continue_with', logo_alignment: 'left', width: 300,
    });
  } catch(e){
    setAuthMsg('Could not load Google sign-in. Check your connection and try again.', true);
  }
}

async function signOut(){
  try { await api('/auth/logout/', {method: 'POST'}); } catch(e){}
  if(window.google && gisInitialised) window.google.accounts.id.disableAutoSelect();
  state.user = null;
  shelfCache = null;
  renderAuth();
  toast('Signed out');
  document.dispatchEvent(new CustomEvent('bp:auth', {detail: null}));
}

/** Returns true when signed in; otherwise opens the sign-in dialog. */
function requireAuth(message){
  if(state.user) return true;
  openAuth(message || 'Sign in to continue.');
  return false;
}

const ready = (async function(){
  try {
    const [me, cfg] = await Promise.all([api('/auth/me/'), api('/auth/config/')]);
    state.user = me.user;
    state.googleClientId = cfg.google_client_id;
  } catch(e){ /* offline / server down: stay signed-out */ }
  renderAuth();
})();

function maybeOneTap(){
  ready.then(() => {
    if(state.user || !state.googleClientId) return;
    let dismissed = false;
    try { dismissed = sessionStorage.getItem('bp-onetap-dismissed') === '1'; } catch(e){}
    if(dismissed) return;
    loadGoogle().then(google => {
      google.accounts.id.prompt(n => {
        if((n.isDismissedMoment && n.isDismissedMoment() && n.getDismissedReason() !== 'credential_returned') ||
           (n.isSkippedMoment && n.isSkippedMoment())){
          try { sessionStorage.setItem('bp-onetap-dismissed', '1'); } catch(e){}
        }
      });
    }).catch(() => {});
  });
}

/* ---------- the signed-in user's shelf (cached; always fetched from Django) ---------- */
let shelfCache = null;
function shelf(force){
  if(!state.user) return Promise.resolve(new Map());
  if(!shelfCache || force){
    shelfCache = api('/my-books/').then(list => new Map(list.map(e => [e.book.id, e]))).catch(err => { shelfCache = null; throw err; });
  }
  return shelfCache;
}
async function addToShelf(book){
  const entry = await api('/my-books/', {method: 'POST', body: {book_slug: book.slug}});
  shelfCache = null;
  return entry;
}

/* =====================================================================
   COMPONENTS
   ===================================================================== */
function coverHTML(b){
  const cat = b.category || {};
  if(b.cover){
    return '<div class="cover"><img src="' + esc(b.cover) + '" alt="' + esc(b.title) + ' cover" loading="lazy" decoding="async"></div>';
  }
  const color = esc(cat.color || '#3B3A36');
  return '<div class="cover" role="img" aria-label="' + esc(b.title) + ' cover">' +
    '<div class="cover-fb" style="background:linear-gradient(155deg,' + color + ',color-mix(in srgb,' + color + ' 68%,#000) 55%,#141018)">' +
      '<svg class="cover-art" viewBox="0 0 100 150" preserveAspectRatio="xMidYMid slice" aria-hidden="true"><g stroke="#fff" stroke-width="4" fill="none" transform="translate(14,55) scale(2.8)">' + (ICONS[cat.icon] || ICONS.tag) + '</g></svg>' +
      '<p class="eyecat">' + esc((cat.name || '').split(' ')[0]) + '</p>' +
      '<div><p class="ctitle">' + esc(b.title) + '</p><p class="cauthor">' + esc(b.author) + '</p></div>' +
    '</div></div>';
}

function downloadBtn(b, cls){
  const ext = fileExt(b.file_url) || 'PDF';
  if(b.file_url) return '<a class="btn btn-outline icon-label-btn ' + (cls||'') + '" href="' + esc(b.file_url) + '" download>' + iconSvg('download', 14) + '<span class="btn-label">Download ' + esc(ext) + '</span></a>';
  return '<span class="btn btn-outline icon-label-btn is-disabled" title="No file has been uploaded for this book yet" aria-disabled="true">' + iconSvg('download', 14) + '<span class="btn-label">Download</span></span>';
}

function bookCard(b){
  const cat = b.category || {};
  const href = bookUrl(b);
  return '<article class="card">' +
    '<a class="card-main" href="' + href + '">' +
      '<div class="pad">' + coverHTML(b) + '</div>' +
      '<div class="pad body">' +
        '<p class="cat cat-label" style="--cat:' + esc(cat.color) + '">' + esc(cat.name) + '</p>' +
        '<h4>' + esc(b.title) + '</h4>' +
        '<p class="auth">' + esc(b.author) + '</p>' +
        '<p class="desc">' + esc(b.description) + '</p>' +
        '<p class="meta">' + esc(b.page_count) + ' pages · ' + esc(fmtDate(b.publication_date)) + '</p>' +
      '</div></a>' +
    '<div class="row">' +
      '<a class="btn btn-primary icon-label-btn" href="' + href + '">' + iconSvg('shelfbook', 14) + '<span class="btn-label">Read</span></a>' +
      downloadBtn(b) +
    '</div></article>';
}

function bookTile(b){
  const cat = b.category || {};
  return '<a class="tile" href="' + bookUrl(b) + '" aria-label="' + esc(b.title) + ' by ' + esc(b.author) + '">' +
    coverHTML(b) +
    '<p class="t-title">' + esc(b.title) + '</p>' +
    '<p class="t-sub">' + esc(b.author) + '</p>' +
    '<p class="t-cat cat-label" style="--cat:' + esc(cat.color) + '">' + esc(cat.name) + '</p></a>';
}

function relatedTile(b){
  return '<a class="rel" href="' + bookUrl(b) + '" aria-label="' + esc(b.title) + ' by ' + esc(b.author) + '">' +
    coverHTML(b) + '<h4>' + esc(b.title) + '</h4><p class="auth">' + esc(b.author) + '</p></a>';
}

function progressBar(pct){ return '<div class="bar" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="' + pct + '"><i style="width:' + pct + '%"></i></div>'; }

function shelfRowItem(entry){
  const b = entry.book;
  return '<div class="shelf-row-item reveal">' +
    '<a href="' + bookUrl(b) + '" class="thumb">' + coverHTML(b) + '</a>' +
    '<div class="body"><a href="' + bookUrl(b) + '"><h5>' + esc(b.title) + '</h5></a>' +
      '<p class="sub">' + esc(b.author) + '</p>' +
      '<div class="pbar">' + progressBar(entry.percentage) + '<span>' + entry.percentage + '% · p. ' + entry.current_page + ' / ' + entry.total_pages + '</span></div>' +
    '</div>' +
    '<div class="ract"><a href="' + bookUrl(b) + '" class="btn btn-primary icon-label-btn">' + iconSvg('shelfbook', 14) + '<span class="btn-label">Continue</span></a></div>' +
  '</div>';
}

function stackedCoverHTML(b){
  return '<div class="cover-stack"><span class="behind" aria-hidden="true"></span><div class="front">' + coverHTML(b) + '</div></div>';
}

function errorBlock(msg, retryId){
  return '<div class="empty-card"><p style="margin:0">' + esc(msg || 'Could not load this section.') + '</p>' +
    (retryId ? '<button class="btn btn-outline" type="button" id="' + retryId + '">Try again</button>' : '') + '</div>';
}

/* =====================================================================
   PROGRESS DIALOG (used on My Shelf and the book page)
   ===================================================================== */
let progCtx = null;
function progUpdateView(){
  const total = progCtx.total, page = Math.max(0, Math.min(total || Infinity, parseInt(document.getElementById('progPage').value || '0', 10) || 0));
  const pct = total ? Math.min(100, Math.floor(page * 100 / total)) : 0;
  document.getElementById('progPct').textContent = pct + '%';
  document.getElementById('progBar').style.width = pct + '%';
}
function openProgress(entry, onChange){
  const dlg = document.getElementById('progressModal');
  progCtx = {entry, onChange, total: entry.total_pages};
  document.getElementById('progBook').textContent = entry.book.title + ' — ' + entry.book.author;
  const range = document.getElementById('progRange'), num = document.getElementById('progPage');
  range.max = entry.total_pages; range.value = entry.current_page;
  num.max = entry.total_pages; num.value = entry.current_page;
  document.getElementById('progTotal').textContent = 'of ' + entry.total_pages + ' pages';
  const msg = document.getElementById('progMsg'); msg.textContent = ''; msg.classList.remove('error');
  progUpdateView();
  dlg.showModal();
}
async function progAct(fn, doneMsg){
  const msg = document.getElementById('progMsg');
  msg.classList.remove('error'); msg.textContent = 'Saving…';
  try {
    const result = await fn();
    shelfCache = null;
    document.getElementById('progressModal').close();
    toast(doneMsg(result));
    if(progCtx && progCtx.onChange) progCtx.onChange(result);
  } catch(err){
    msg.textContent = err.message; msg.classList.add('error');
  }
}
function initDialogs(){
  document.querySelectorAll('dialog.modal').forEach(dlg => {
    dlg.addEventListener('click', e => { if(e.target === dlg || e.target.closest('[data-close]')) dlg.close(); });
  });
  document.addEventListener('click', e => {
    if(e.target.closest('[data-open-auth]')) openAuth();
  });
  const range = document.getElementById('progRange'), num = document.getElementById('progPage');
  if(!range) return;
  range.addEventListener('input', () => { num.value = range.value; progUpdateView(); });
  num.addEventListener('input', () => { range.value = num.value || 0; progUpdateView(); });
  document.getElementById('progSave').addEventListener('click', () => {
    const page = parseInt(num.value || '0', 10) || 0;
    progAct(() => api('/my-books/' + progCtx.entry.id + '/', {method: 'PATCH', body: {current_page: page}}),
      r => r.status === 'finished' ? 'Finished — nice work!' : 'Progress saved: ' + r.percentage + '%');
  });
  document.getElementById('progFinish').addEventListener('click', () => {
    progAct(() => api('/my-books/' + progCtx.entry.id + '/', {method: 'PATCH', body: {status: 'finished'}}), () => 'Marked as finished');
  });
  document.getElementById('progRemove').addEventListener('click', () => {
    progAct(async () => { await api('/my-books/' + progCtx.entry.id + '/', {method: 'DELETE'}); return null; }, () => 'Removed from My Shelf');
  });
}

/* =====================================================================
   CHROME: nav state, header shadow, account menu, footer topics
   ===================================================================== */
let categoriesPromise = null;
function categories(){
  if(!categoriesPromise) categoriesPromise = api('/categories/').catch(err => { categoriesPromise = null; throw err; });
  return categoriesPromise;
}

function initReveal(root){
  const els = (root || document).querySelectorAll('.reveal:not(.in)');
  if(!els.length) return;
  if(!('IntersectionObserver' in window)){ els.forEach(el => el.classList.add('in')); return; }
  const io = new IntersectionObserver(entries => {
    entries.forEach((entry, i) => {
      if(entry.isIntersecting){ setTimeout(() => entry.target.classList.add('in'), i * 50); io.unobserve(entry.target); }
    });
  }, {threshold: .12, rootMargin: '0px 0px -36px 0px'});
  els.forEach(el => io.observe(el));
}

function initChrome(){
  const active = document.body.dataset.nav;
  document.querySelectorAll('[data-nav]').forEach(el => {
    if(el === document.body) return;
    const on = el.dataset.nav === active;
    el.classList.toggle('on', on);
    if(on) el.setAttribute('aria-current', 'page'); else el.removeAttribute('aria-current');
  });

  const header = document.querySelector('.site-header');
  const onScroll = () => header.classList.toggle('scrolled', window.scrollY > 8);
  onScroll(); window.addEventListener('scroll', onScroll, {passive: true});

  document.querySelectorAll('#mobileMenu a').forEach(a => a.addEventListener('click', () => {
    document.getElementById('mobileMenu').classList.remove('open');
    const btn = document.getElementById('menuBtn'); btn.classList.remove('open'); btn.setAttribute('aria-expanded', 'false');
  }));

  document.getElementById('signInBtn').addEventListener('click', () => openAuth());
  document.getElementById('signOutBtn').addEventListener('click', signOut);
  const avatar = document.getElementById('avatarBtn'), pop = document.getElementById('userPop');
  avatar.addEventListener('click', e => { e.stopPropagation(); pop.hidden = !pop.hidden; avatar.setAttribute('aria-expanded', String(!pop.hidden)); });
  document.addEventListener('click', e => { if(!pop.hidden && !e.target.closest('#userMenu')){ pop.hidden = true; avatar.setAttribute('aria-expanded', 'false'); } });
  document.addEventListener('keydown', e => { if(e.key === 'Escape' && !pop.hidden){ pop.hidden = true; avatar.focus(); } });

  initDialogs();

  categories().then(cats => {
    const ul = document.getElementById('footCats');
    if(ul && cats.length) ul.innerHTML = cats.map(c => '<li><a href="/topics/?category=' + encodeURIComponent(c.slug) + '">' + esc(c.name) + '</a></li>').join('');
  }).catch(() => {});

  maybeOneTap();
}

window.BP = {
  esc, qp, fmtDate, fmtDay, bookUrl, fileExt, iconSvg, ICONS,
  api, toast, state, ready, shelf, addToShelf, requireAuth, openAuth, openProgress,
  coverHTML, bookCard, bookTile, relatedTile, shelfRowItem, stackedCoverHTML, progressBar, downloadBtn, errorBlock,
  categories, initReveal, initChrome, toggleTheme, toggleMenu,
};
})();
