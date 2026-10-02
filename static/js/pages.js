/* Page controllers. Each one fetches from the Django API and renders with the shared components. */
(function(){
'use strict';
const {esc, qp, api, fmtDate, fmtDay, bookUrl, fileExt, iconSvg, ICONS, toast} = BP;
const $ = id => document.getElementById(id);
const wait = ms => new Promise(r => setTimeout(r, ms));

function artBackground(color, icon, seed){
  const c = esc(color || '#3B3A36');
  return '<svg class="cat-art" viewBox="0 0 200 150" preserveAspectRatio="xMidYMid slice" aria-hidden="true">' +
    '<defs><linearGradient id="g' + seed + '" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="' + c + '"/><stop offset="1" stop-color="#11141f"/></linearGradient></defs>' +
    '<rect width="200" height="150" fill="url(#g' + seed + ')"/>' +
    '<g stroke="#fff" stroke-opacity=".16" stroke-width="6" fill="none" transform="translate(120,20) scale(3.4)">' + (ICONS[icon] || ICONS.tag) + '</g></svg>';
}

function failInto(el, msg, retry){
  el.innerHTML = BP.errorBlock(msg, 'retryBtn');
  const b = el.querySelector('#retryBtn');
  if(b) b.addEventListener('click', retry);
}

/* ================================================================ CATALOG */
async function home(){
  BP.initChrome();

  /* topics, latest books, featured volume */
  try {
    const [cats, latest, featuredRes, stats] = await Promise.all([
      BP.categories(), api('/books/?page_size=8'), api('/books/?featured=true&page_size=1'), api('/stats/'),
    ]);
    const featured = (featuredRes.results[0]) || latest.results[0];

    const tags = cats.filter(c => c.book_count > 0).sort((a, b) => b.book_count - a.book_count).slice(0, 4);
    $('popularTags').innerHTML = tags.map(c => '<a class="pill tinted" style="--cat:' + esc(c.color) + '" href="/topics/?category=' + encodeURIComponent(c.slug) + '">' + esc(c.name) + '</a>').join('');

    $('categoryGrid').innerHTML = cats.length ? cats.map((c, i) =>
      '<div class="reveal"><a href="/topics/?category=' + encodeURIComponent(c.slug) + '" class="cat-card">' + artBackground(c.color, c.icon, i) +
      '<div class="cat-body"><span class="cat-icn">' + iconSvg(c.icon, 14) + '</span><p class="cat-name">' + esc(c.name) + '</p>' +
      '<p class="cat-count">' + c.book_count + ' publication' + (c.book_count === 1 ? '' : 's') + '</p></div></a></div>'
    ).join('') : '<div class="empty-card" style="grid-column:1/-1">No topics yet. Add some in Django admin.</div>';

    $('latestGrid').innerHTML = latest.results.length
      ? latest.results.map(b => '<div class="reveal">' + BP.bookCard(b) + '</div>').join('')
      : '<div class="empty-card" style="grid-column:1/-1">No books have been published yet. Add the first one in Django admin.</div>';

    renderCurator(featured);
    renderStats(stats);
    BP.initReveal();
  } catch(err){
    const msg = 'We couldn\'t load the library right now.';
    failInto($('curatorSlot'), msg, () => location.reload());
    $('categoryGrid').innerHTML = ''; $('latestGrid').innerHTML = '';
  }

  await BP.ready;
  renderShelfRow();
  document.addEventListener('bp:auth', () => { renderShelfRow(); renderStatsShelf(); updateCuratorShelfBtn(); });
}

let curatorBook = null, statsCache = null;
function renderCurator(b){
  const slot = $('curatorSlot');
  if(!b){ slot.innerHTML = '<div class="empty-card" style="grid-column:1/-1">Nothing featured yet.</div>'; return; }
  curatorBook = b;
  const cat = b.category || {};
  const metaIcon = n => iconSvg(n, 14);
  const readHref = b.file_url || bookUrl(b);
  slot.innerHTML =
    '<div>' + BP.stackedCoverHTML(b) + '</div>' +
    '<div>' +
      '<div style="display:flex; justify-content:space-between; align-items:flex-start; gap:12px">' +
        '<span class="badge">Special Feature</span>' +
        '<a href="' + bookUrl(b) + '" class="card-link">Details <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m9 18 6-6-6-6"/></svg></a>' +
      '</div>' +
      '<h3 class="serif">' + esc(b.title) + '</h3>' +
      '<p class="by">by <a href="' + bookUrl(b) + '">' + esc(b.author) + '</a></p>' +
      '<p class="desc">' + esc(b.description) + '</p>' +
      '<div class="meta-row">' +
        '<span>' + metaIcon('shelfbook') + esc(b.page_count) + ' pages</span>' +
        '<span>' + metaIcon('calendar') + esc(b.type) + ' · ' + esc(b.level) + '</span>' +
        '<span>' + metaIcon('calendar') + 'Published ' + esc(fmtDate(b.publication_date)) + '</span>' +
      '</div>' +
      '<div class="actions">' +
        BP.downloadBtn(b) +
        '<button class="btn btn-outline icon-label-btn" id="curatorShelfBtn" type="button">' + iconSvg('shelfbook', 14) + '<span class="btn-label">Add to My Shelf</span></button>' +
      '</div>' +
    '</div>';
  $('curatorShelfBtn').addEventListener('click', async e => {
    if(!BP.requireAuth('Sign in to add books to your shelf.')) return;
    const btn = e.currentTarget;
    try {
      const map = await BP.shelf();
      if(map.has(b.id)){ toast('Already on your shelf'); return; }
      await BP.addToShelf(b);
      btn.classList.add('pop'); toast('Added to My Shelf');
      updateCuratorShelfBtn(); renderShelfRow(); renderStatsShelf();
    } catch(err){ toast(err.message); }
  });
  updateCuratorShelfBtn();
}
async function updateCuratorShelfBtn(){
  const btn = $('curatorShelfBtn'); if(!btn || !curatorBook) return;
  let on = false;
  if(BP.state.user){ try { on = (await BP.shelf()).has(curatorBook.id); } catch(e){} }
  btn.classList.toggle('on', on);
  const label = btn.querySelector('.btn-label'); if(label) label.textContent = on ? 'On My Shelf' : 'Add to My Shelf';
}

async function renderShelfRow(){
  const row = $('shelfRow');
  if(!BP.state.user){
    row.innerHTML = '<div class="empty-card"><p style="margin:0">Sign in to see the books you\'re reading and your progress.</p><button class="btn btn-primary" type="button" data-open-auth>Sign in / Sign up</button></div>';
    return;
  }
  try {
    const reading = (await api('/my-books/?status=reading')).slice(0, 3);
    row.innerHTML = reading.length
      ? '<div class="shelf-list">' + reading.map(BP.shelfRowItem).join('') + '</div>'
      : '<div class="empty-card"><p style="margin:0">You\'re not reading anything yet. Open a book and add it to My Shelf.</p></div>';
    BP.initReveal(row);
  } catch(err){ failInto(row, 'Couldn\'t load your shelf.', renderShelfRow); }
}

function renderStats(stats){
  statsCache = stats;
  renderStatsShelf();
}
async function renderStatsShelf(){
  if(!statsCache) return;
  let mine = '—';
  if(BP.state.user){ try { mine = (await BP.shelf(true)).size; } catch(e){} }
  const items = [
    {n: statsCache.books, l: 'Books', href: '/topics/', icon: 'shelfbook'},
    {n: statsCache.collections, l: 'Collections', href: '/collections/', icon: 'layers'},
    {n: statsCache.topics, l: 'Topics', href: '/topics/', icon: 'tag'},
    {n: mine, l: 'On My Shelf', href: '/my-shelf/', icon: 'check'},
  ];
  $('statGrid').innerHTML = items.map(s =>
    '<a href="' + s.href + '" class="stat-card"><span class="stat-icn">' + iconSvg(s.icon, 17) + '</span><div><div class="n">' + s.n + '</div><div class="l">' + s.l + '</div></div></a>'
  ).join('');
}

/* ================================================================ COLLECTIONS */
async function collections(){
  BP.initChrome();
  const list = $('collectionList');
  async function load(){
    try {
      const data = await api('/collections/');
      if(!data.length){ list.innerHTML = '<p class="empty">No collections yet. Create one in Django admin.</p>'; return; }
      list.innerHTML = data.map(c =>
        '<section class="collection-section reveal">' +
          '<div class="collection-header"><h2 class="serif">' + esc(c.title) + '</h2>' +
            '<div class="collection-meta"><span class="collection-badge">' + iconSvg('shelfbook', 11) + c.book_count + ' volume' + (c.book_count === 1 ? '' : 's') + '</span>' +
            '<a class="link-more" href="/topics/?collection=' + encodeURIComponent(c.slug) + '">View all →</a></div></div>' +
          (c.description ? '<p class="collection-desc">' + esc(c.description) + '</p>' : '') +
          '<div class="grid g3">' + c.books.map(b => '<div>' + BP.bookCard(b) + '</div>').join('') + '</div>' +
        '</section>'
      ).join('');
      BP.initReveal();
    } catch(err){ failInto(list, 'Couldn\'t load collections.', load); }
  }
  load();
}

/* ================================================================ TOPICS */
async function topics(){
  BP.initChrome();
  const PAGE = 20;
  const st = {category: qp('category') || '', q: qp('q') || '', collection: qp('collection') || '', page: 1, count: 0, loaded: 0, token: 0};
  const grid = $('topicsGrid'), search = $('navsearch');
  search.value = st.q;

  function syncUrl(){
    const p = new URLSearchParams();
    if(st.collection) p.set('collection', st.collection);
    else if(st.category) p.set('category', st.category);
    if(st.q) p.set('q', st.q);
    history.replaceState(null, '', location.pathname + (p.toString() ? '?' + p : ''));
  }

  async function fetchPage(reset){
    const token = ++st.token;
    if(reset){ st.page = 1; st.loaded = 0; grid.innerHTML = '<div class="skeleton" style="height:260px;grid-column:1/-1"></div>'; }
    const p = new URLSearchParams({page: st.page, page_size: PAGE});
    if(st.collection) p.set('collection', st.collection); else if(st.category) p.set('category', st.category);
    if(st.q) p.set('q', st.q);
    try {
      const data = await api('/books/?' + p);
      if(token !== st.token) return;               // a newer request superseded this one
      if(reset) grid.innerHTML = '';
      st.count = data.count;
      st.loaded += data.results.length;
      grid.insertAdjacentHTML('beforeend', data.results.map(b => '<div class="reveal">' + BP.bookTile(b) + '</div>').join(''));
      BP.initReveal(grid);
      $('topicsEmpty').hidden = st.count > 0;
      $('topicsFoot').hidden = st.count === 0;
      $('loadMore').hidden = !data.next;
      $('topicsCount').innerHTML = '<b>' + String(st.loaded).padStart(2, '0') + '</b> / ' + st.count + ' book' + (st.count === 1 ? '' : 's');
      $('topicsNote').innerHTML = 'Looking for a guided path? Try the <a href="/collections/">curated collections</a>.';
    } catch(err){
      if(token !== st.token) return;
      failInto(grid, err.message || 'Couldn\'t load books.', () => fetchPage(true));
      grid.firstElementChild && (grid.firstElementChild.style.gridColumn = '1/-1');
    }
  }

  function renderHeading(title, sub){
    $('topicsTitle').textContent = title;
    $('topicsSub').textContent = sub;
  }

  let cats = [];
  try { cats = await BP.categories(); } catch(e){}

  if(st.collection){
    try {
      const c = await api('/collections/' + encodeURIComponent(st.collection) + '/');
      renderHeading(c.title, c.description || (c.book_count + ' publications'));
      $('chipRow').innerHTML = '<a class="chip" href="/topics/">← All topics</a>';
    } catch(e){ st.collection = ''; }
  }
  if(!st.collection){
    const total = cats.reduce((n, c) => n + c.book_count, 0);
    $('chipRow').innerHTML =
      '<button class="chip' + (!st.category ? ' on' : '') + '" type="button" role="tab" data-cat="">All<small>' + total + '</small></button>' +
      cats.map(c => '<button class="chip' + (st.category === c.slug ? ' on' : '') + '" type="button" role="tab" data-cat="' + esc(c.slug) + '">' + esc(c.name) + '<small>' + c.book_count + '</small></button>').join('');
    const updateTitle = () => {
      const c = cats.find(x => x.slug === st.category);
      renderHeading(c ? c.name : 'Topics', c ? (c.description || 'Books in this topic.') : 'Browse the library by subject.');
    };
    updateTitle();
    $('chipRow').addEventListener('click', e => {
      const chip = e.target.closest('[data-cat]'); if(!chip) return;
      st.category = chip.dataset.cat;
      $('chipRow').querySelectorAll('.chip').forEach(c => { const on = c === chip; c.classList.toggle('on', on); c.setAttribute('aria-selected', String(on)); });
      updateTitle(); syncUrl(); fetchPage(true);
    });
  }

  let timer;
  search.addEventListener('input', () => {
    clearTimeout(timer);
    timer = setTimeout(() => { st.q = search.value.trim(); syncUrl(); fetchPage(true); }, 250);
  });
  $('loadMore').addEventListener('click', () => { st.page += 1; fetchPage(false); });

  fetchPage(true);
}

/* ================================================================ MY SHELF */
function shelfSlot(entry, finished){
  const b = entry.book;
  const info = finished
    ? '<p class="s-title">' + esc(b.title) + '</p><p class="s-done">' + (entry.date_finished ? 'Finished ' + esc(fmtDay(entry.date_finished)) : 'Finished') + '</p>'
    : '<p class="s-title">' + esc(b.title) + '</p><p class="s-pct">' + entry.percentage + '%</p>' + BP.progressBar(entry.percentage) +
      '<p class="s-pages">p. ' + entry.current_page + ' of ' + entry.total_pages + '</p>';
  return '<div class="shelf-slot" data-entry="' + entry.id + '">' +
    '<div class="shelf-area"><a class="shelf-book" href="' + bookUrl(b) + '" aria-label="' + esc(b.title) + '">' + BP.coverHTML(b) + '</a></div>' +
    '<div class="ledge"></div>' +
    '<div class="shelf-info">' + info +
      (finished ? '' : '') +
      '<button class="s-link" type="button" data-update="' + entry.id + '">' + (finished ? 'Manage' : 'Update') + '</button></div></div>';
}
function fillerSlot(){ return '<div class="shelf-slot is-filler" aria-hidden="true"><div class="shelf-area"></div><div class="ledge"></div><div class="shelf-info"></div></div>'; }

function fillShelf(grid){
  grid.querySelectorAll('.is-filler').forEach(n => n.remove());
  const cols = Math.max(1, getComputedStyle(grid).gridTemplateColumns.split(' ').length);
  const real = grid.querySelectorAll('.shelf-slot').length;
  const total = Math.max(cols, Math.ceil(real / cols) * cols);
  let html = ''; for(let i = real; i < total; i++) html += fillerSlot();
  grid.insertAdjacentHTML('beforeend', html);
  grid.dataset.cols = cols;
}
const observed = new WeakSet();
function watchShelf(grid){
  if(observed.has(grid) || !('ResizeObserver' in window)) return;
  observed.add(grid);
  new ResizeObserver(() => {
    const cols = Math.max(1, getComputedStyle(grid).gridTemplateColumns.split(' ').length);
    if(String(cols) !== grid.dataset.cols) fillShelf(grid);
  }).observe(grid);
}

async function shelf(){
  BP.initChrome();
  const readingEl = $('readingShelf'), finishedEl = $('finishedShelf');
  let entries = [];

  function paint(){
    const reading = entries.filter(e => e.status === 'reading');
    const finished = entries.filter(e => e.status === 'finished');
    const signedIn = !!BP.state.user;
    $('shelfGate').hidden = signedIn;
    $('readingCount').textContent = signedIn ? reading.length + (reading.length === 1 ? ' book' : ' books') : '';
    $('finishedCount').textContent = signedIn ? finished.length + (finished.length === 1 ? ' book' : ' books') : '';
    const note = (grid, text) => '<div class="shelf-note">' + text + '</div>';
    readingEl.innerHTML = reading.map(e => shelfSlot(e, false)).join('') +
      (!reading.length ? note(readingEl, signedIn ? 'Nothing here yet — open a book and add it to <a href="/topics/">My Shelf</a>.' : 'Your current reads will stand here.') : '');
    finishedEl.innerHTML = finished.map(e => shelfSlot(e, true)).join('') +
      (!finished.length ? note(finishedEl, signedIn ? 'Books you finish will move here.' : 'Finished books will line up here.') : '');
    [readingEl, finishedEl].forEach(g => { fillShelf(g); watchShelf(g); });
  }

  async function load(){
    await BP.ready;
    if(!BP.state.user){ entries = []; paint(); return; }
    try { entries = await api('/my-books/'); paint(); }
    catch(err){ entries = []; paint(); toast(err.message); }
  }

  document.querySelector('.shelf-board').addEventListener('click', e => {
    const btn = e.target.closest('[data-update]'); if(!btn) return;
    const entry = entries.find(x => String(x.id) === btn.dataset.update); if(!entry) return;
    BP.openProgress(entry, load);
  });
  document.addEventListener('bp:auth', load);
  load();
}

/* ================================================================ BOOK DETAIL */
function snippetHTML(b){
  const text = (b.preview_text || b.description || '').trim();
  return text.split(/\n{1,}/).map(s => s.trim()).filter(Boolean).map(s => '<p>' + esc(s) + '</p>').join('') || '<p>No preview is available for this book yet.</p>';
}
function openBookHTML(b){
  return '<div class="ob" id="ob" role="button" tabindex="0" aria-pressed="false" aria-label="Book preview for ' + esc(b.title) + '. Press to open or close the book.">' +
    '<div class="ob-book">' +
      '<div class="ob-shadow"></div>' +
      '<div class="ob-page ob-base"><div class="pg pg-right">' +
        '<figure class="plate">' + BP.coverHTML(b) + '</figure>' +
        '<p class="pg-author">' + esc(b.author) + '</p>' +
        '<span class="pg-num">3</span></div></div>' +
      '<div class="ob-page ob-flap">' +
        '<div class="ob-face front">' + BP.coverHTML(b) + '</div>' +
        '<div class="ob-face back"><div class="pg pg-left">' +
          '<p class="pg-run">' + esc(b.title) + '</p>' +
          '<h4 class="pg-chap">Preview</h4>' +
          '<div class="pg-text">' + snippetHTML(b) + '</div>' +
          '<span class="pg-num">2</span></div></div>' +
      '</div>' +
    '</div></div>';
}

async function book(slug){
  BP.initChrome();
  let data = null;

  async function load(){
    try { data = await api('/books/' + encodeURIComponent(slug) + '/'); }
    catch(err){ failInto($('obWrap'), err.status === 404 ? 'This book could not be found.' : (err.message || 'Couldn\'t load this book.'), load); return; }
    render();
  }

  function renderOpenBook(first){
    const wrap = $('obWrap');
    wrap.innerHTML = openBookHTML(data);
    const ob = $('ob');
    const setOpen = open => { ob.classList.toggle('open', open); ob.setAttribute('aria-pressed', String(open)); };
    ob.addEventListener('click', () => setOpen(!ob.classList.contains('open')));
    ob.addEventListener('keydown', e => { if(e.key === 'Enter' || e.key === ' '){ e.preventDefault(); setOpen(!ob.classList.contains('open')); } });
    // cover → opens → spread
    requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(() => setOpen(true), first ? 450 : 0)));
  }

  function renderCaption(){
    const e = data.my_entry;
    const pages = e
      ? '<span>' + iconSvg('shelfbook', 14) + (e.status === 'finished' ? data.page_count + ' pages · finished' : e.current_page + ' / ' + e.total_pages + ' pages · ' + e.percentage + '% read') + '</span>'
      : '<span>' + iconSvg('shelfbook', 14) + data.page_count + ' pages</span>';
    $('obCaption').innerHTML = pages + '<span class="hint">Tap the book to open or close it</span>';
  }

  function renderActions(){
    const b = data, e = b.my_entry;
    const ext = fileExt(b.file_url) || 'PDF';
    const read = b.file_url
      ? '<a class="btn btn-primary" id="readBtn" href="' + esc(b.file_url) + '" target="_blank" rel="noopener">' + iconSvg('shelfbook', 15) + 'Read online</a>'
      : '<span class="btn btn-primary is-disabled" title="No file has been uploaded for this book yet" aria-disabled="true">' + iconSvg('shelfbook', 15) + 'Read online</span>';
    const dl = b.file_url
      ? '<a class="btn btn-outline" href="' + esc(b.file_url) + '" download>' + iconSvg('download', 15) + 'Download ' + esc(ext) + '</a>'
      : '<span class="btn btn-outline is-disabled" title="No file has been uploaded for this book yet" aria-disabled="true">' + iconSvg('download', 15) + 'Download</span>';
    const shelfBtn = e
      ? '<span class="btn btn-outline on" aria-live="polite">' + iconSvg('check', 15) + 'On My Shelf</span>'
      : '<button class="btn btn-outline" type="button" id="shelfBtn">' + iconSvg('shelfbook', 15) + 'Add to My Shelf</button>';
    $('bActions').innerHTML = read + dl + shelfBtn;

    const sb = $('shelfBtn');
    if(sb) sb.addEventListener('click', async () => {
      if(!BP.requireAuth('Sign in to add this book to your shelf.')) return;
      try { await BP.addToShelf(data); toast('Added to My Shelf'); await load(); } catch(err){ toast(err.message); }
    });
    const rb = $('readBtn');
    if(rb) rb.addEventListener('click', () => {
      // Opening a book you're signed in for starts tracking it (the file itself opens in a new tab).
      if(BP.state.user && !data.my_entry) BP.addToShelf(data).then(() => load()).catch(() => {});
    });
  }

  function renderProgress(){
    const e = data.my_entry, box = $('bProgress');
    if(!e){ box.innerHTML = ''; return; }
    if(e.status === 'finished'){
      box.innerHTML = '<div class="prog-panel"><h4>Finished <b>100%</b></h4>' + BP.progressBar(100) +
        '<p class="meta">' + (e.date_finished ? 'Completed ' + esc(fmtDay(e.date_finished)) + '.' : 'Completed.') + '</p>' +
        '<div class="row"><button class="btn btn-outline" type="button" id="againBtn">Read again</button><button class="btn btn-outline" type="button" id="manageBtn">Manage</button></div></div>';
      $('againBtn').addEventListener('click', async () => {
        try { await api('/my-books/' + e.id + '/', {method: 'PATCH', body: {status: 'reading'}}); toast('Back on Currently Reading'); await load(); } catch(err){ toast(err.message); }
      });
    } else {
      box.innerHTML = '<div class="prog-panel"><h4>Your progress <b>' + e.percentage + '%</b></h4>' + BP.progressBar(e.percentage) +
        '<p class="meta">Page ' + e.current_page + ' of ' + e.total_pages + '</p>' +
        '<div class="row"><button class="btn btn-primary" type="button" id="manageBtn">Update progress</button>' +
        '<button class="btn btn-outline" type="button" id="finishBtn">Mark as finished</button></div></div>';
      $('finishBtn').addEventListener('click', async () => {
        try { await api('/my-books/' + e.id + '/', {method: 'PATCH', body: {status: 'finished'}}); toast('Marked as finished'); await load(); } catch(err){ toast(err.message); }
      });
    }
    $('manageBtn').addEventListener('click', () => {
      BP.openProgress({id: e.id, current_page: e.current_page, total_pages: e.total_pages, status: e.status, book: data}, load);
    });
  }

  function render(){
    const b = data, cat = b.category || {};
    $('bCat').textContent = [cat.name, b.type, b.level].filter(Boolean).join(' · ');
    $('bTitle').textContent = b.title;
    $('bAuthor').textContent = 'by ' + b.author;
    $('bDesc').textContent = b.description;
    const ext = fileExt(b.file_url);
    $('bMeta').innerHTML =
      '<span>' + iconSvg('shelfbook', 14) + b.page_count + ' pages</span>' +
      '<span>' + iconSvg('calendar', 14) + 'Published ' + esc(fmtDate(b.publication_date)) + '</span>' +
      (ext ? '<span>' + iconSvg('file', 14) + esc(ext) + ' format</span>' : '') +
      (b.publisher ? '<span>' + esc(b.publisher) + '</span>' : '') +
      (b.isbn ? '<span>ISBN ' + esc(b.isbn) + '</span>' : '');
    $('bToc').innerHTML = b.table_of_contents.length
      ? b.table_of_contents.map((t, i) => '<li><span class="n">' + (i + 1) + '</span>' + esc(t) + '</li>').join('')
      : '<li style="opacity:.7">The table of contents hasn\'t been added yet.</li>';
    $('bRelated').innerHTML = b.related.length ? b.related.map(BP.relatedTile).join('') : '<p class="page-sub" style="margin:0">No related publications yet.</p>';

    if(!$('ob')) renderOpenBook(true);
    renderCaption(); renderActions(); renderProgress();
  }

  await BP.ready;
  await load();
  document.addEventListener('bp:auth', load);
}

window.Pages = {home, collections, topics, shelf, book};
})();
