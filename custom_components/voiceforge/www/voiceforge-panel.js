/**
 * VoiceForge Dashboard Panel
 *
 * Registered as a custom HA sidebar panel at /voiceforge.
 * Receives `hass` and `panel` properties from the HA frontend.
 *
 * Dynamic content (character names, message bodies, memory facts) is always
 * inserted via textContent — never innerHTML — to prevent XSS.
 */

const _CSS = `
  :host {
    display: block;
    height: 100%;
    overflow-y: auto;
    background: #0d0d0d;
    color: #ccc;
    font-family: monospace;
  }
  .page { max-width: 1100px; margin: 0 auto; padding: 20px; }
  h1 { color: #ff4444; letter-spacing: 4px; text-align: center; margin: 0 0 30px; font-size: 1.4rem; }

  .hero { text-align: center; margin-bottom: 30px; }
  .hero img { width: 320px; height: 240px; image-rendering: pixelated; border: 2px solid #333; }
  .hero .char-label { margin-top: 8px; font-size: 0.85rem; letter-spacing: 3px; color: #888; text-transform: uppercase; }

  .section { margin-bottom: 40px; }
  .section-title {
    font-size: 0.9rem; letter-spacing: 3px; text-transform: uppercase;
    color: #ff4444; border-bottom: 1px solid #222; padding-bottom: 6px; margin-bottom: 16px;
    display: flex; align-items: center; justify-content: space-between; cursor: pointer;
  }
  .section-title .toggle { font-size: 0.75rem; color: #555; }
  .section-body.collapsed { display: none; }

  .char-grid { display: flex; gap: 16px; flex-wrap: wrap; }
  .char-card {
    width: 160px; background: #111; border: 1px solid #222; border-radius: 4px;
    padding: 12px; text-align: center; cursor: pointer; transition: border-color 0.15s;
  }
  .char-card:hover { border-color: #444; }
  .char-card.active { border-color: #ff4444; }
  .char-card img { width: 80px; height: 60px; image-rendering: pixelated; display: block; margin: 0 auto 8px; }
  .char-card .cname { font-size: 0.8rem; letter-spacing: 2px; color: #ccc; }
  .char-card .cdesc { font-size: 0.7rem; color: #555; margin-top: 4px; line-height: 1.3; }
  .char-card.active .cname { color: #ff4444; }

  .msg-filters { display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
  .msg-filters select {
    background: #111; color: #ccc; border: 1px solid #333; padding: 4px 8px;
    font-family: monospace; font-size: 0.75rem; border-radius: 2px;
  }
  .msg-list { display: flex; flex-direction: column; gap: 8px; }
  .msg-item {
    background: #111; border: 1px solid #222; border-radius: 4px;
    padding: 10px 12px; cursor: pointer;
  }
  .msg-item.unread { border-left: 3px solid #ff4444; }
  .msg-meta {
    display: flex; gap: 10px; align-items: center;
    font-size: 0.7rem; color: #555; margin-bottom: 4px;
  }
  .msg-from { color: #888; }
  .msg-badge {
    background: #222; border-radius: 2px; padding: 1px 5px;
    font-size: 0.65rem; text-transform: uppercase; letter-spacing: 1px;
  }
  .msg-badge.event { color: #aaa; }
  .msg-badge.personal { color: #ff9933; }
  .msg-body { font-size: 0.82rem; color: #ccc; line-height: 1.4; }
  .msg-item.read .msg-body { color: #555; }

  .empty { color: #444; font-size: 0.82rem; font-style: italic; padding: 8px 0; }

  .mem-char-select { display: flex; gap: 8px; margin-bottom: 12px; }
  .mem-char-select select {
    background: #111; color: #ccc; border: 1px solid #333; padding: 4px 8px;
    font-family: monospace; font-size: 0.75rem; border-radius: 2px;
  }
  .mem-list { display: flex; flex-direction: column; gap: 6px; }
  .mem-entry {
    background: #111; border: 1px solid #1a1a1a; border-radius: 3px; padding: 8px 10px;
  }
  .mem-cat { font-size: 0.65rem; letter-spacing: 2px; color: #555; text-transform: uppercase; margin-bottom: 2px; }
  .mem-fact { font-size: 0.8rem; color: #999; }

  .status-bar {
    text-align: center; font-size: 0.7rem; color: #333; letter-spacing: 2px;
    margin-top: 40px; padding-top: 16px; border-top: 1px solid #111;
  }
`;

// ── DOM helpers ──────────────────────────────────────────────────────────────

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function emptyNote(text) {
  return el("div", "empty", text);
}

// ── Panel class ──────────────────────────────────────────────────────────────

class VoiceForgePanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._initialized = false;
    this._hass = null;
    this._characters = [];
    this._activeCharId = null;
    this._messages = [];
    this._memory = [];
    this._emotionSub = null;
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._initialized) {
      this._initialized = true;
      this._buildSkeleton();
      this._loadState();
      this._subscribeEmotionEvents();
    }
  }

  // ── Static skeleton (no user data — innerHTML is safe here) ───────────────

  _buildSkeleton() {
    const root = this.shadowRoot;
    const styleEl = document.createElement("style");
    styleEl.textContent = _CSS;
    root.appendChild(styleEl);

    const page = el("div", "page");
    page.appendChild(el("h1", null, "VOICEFORGE"));

    // Hero sprite
    const hero = el("div", "hero");
    const heroImg = document.createElement("img");
    heroImg.id = "sprite-hero";
    heroImg.alt = "Active character";
    hero.appendChild(heroImg);
    const heroLabel = el("div", "char-label", "Loading...");
    heroLabel.id = "hero-label";
    hero.appendChild(heroLabel);
    page.appendChild(hero);

    page.appendChild(this._buildSection("chars", "CHARACTER LIBRARY", false, () => {
      const grid = el("div", "char-grid");
      grid.id = "char-grid";
      grid.appendChild(emptyNote("Loading characters..."));
      return grid;
    }));

    page.appendChild(this._buildSection("msgs", "MESSAGE BOARD", false, () => {
      const wrap = document.createDocumentFragment();

      const filters = el("div", "msg-filters");

      const filterChar = document.createElement("select");
      filterChar.id = "filter-character";
      const optAll1 = document.createElement("option");
      optAll1.value = "all";
      optAll1.textContent = "All characters";
      filterChar.appendChild(optAll1);

      const filterMember = document.createElement("select");
      filterMember.id = "filter-member";
      const optAll2 = document.createElement("option");
      optAll2.value = "all";
      optAll2.textContent = "All members";
      filterMember.appendChild(optAll2);

      const filterType = document.createElement("select");
      filterType.id = "filter-type";
      [["all", "All types"], ["event", "Event"], ["personal", "Personal"]].forEach(([v, t]) => {
        const opt = document.createElement("option");
        opt.value = v;
        opt.textContent = t;
        filterType.appendChild(opt);
      });

      filters.appendChild(filterChar);
      filters.appendChild(filterMember);
      filters.appendChild(filterType);

      const msgList = el("div", "msg-list");
      msgList.id = "msg-list";
      msgList.appendChild(emptyNote("Loading messages..."));

      const container = el("div");
      container.appendChild(filters);
      container.appendChild(msgList);
      return container;
    }));

    page.appendChild(this._buildSection("mem", "MEMORY VIEWER", true, () => {
      const wrap = el("div");

      const memSel = document.createElement("select");
      memSel.id = "mem-character-select";
      const defOpt = document.createElement("option");
      defOpt.value = "";
      defOpt.textContent = "Select character";
      memSel.appendChild(defOpt);

      const memSelWrap = el("div", "mem-char-select");
      memSelWrap.appendChild(memSel);
      wrap.appendChild(memSelWrap);

      const memList = el("div", "mem-list");
      memList.id = "mem-list";
      memList.appendChild(emptyNote("Select a character to view memory."));
      wrap.appendChild(memList);
      return wrap;
    }));

    page.appendChild(el("div", "status-bar", "VOICEFORGE — LOCAL ONLY — NEVER UPLOADED"));
    root.appendChild(page);

    // Wire event listeners
    root.addEventListener("click", (e) => this._handleClick(e));
    root.getElementById("filter-character").addEventListener("change", () => this._renderMessages());
    root.getElementById("filter-member").addEventListener("change", () => this._renderMessages());
    root.getElementById("filter-type").addEventListener("change", () => this._renderMessages());
    root.getElementById("mem-character-select").addEventListener("change", (e) => {
      this._loadMemory(e.target.value);
    });
  }

  _buildSection(id, title, collapsed, bodyFn) {
    const section = el("div", "section");

    const titleEl = el("div", "section-title");
    titleEl.dataset.section = id;
    const titleText = document.createElement("span");
    titleText.textContent = title;
    const toggle = el("span", "toggle", collapsed ? "▶" : "▼");
    titleEl.appendChild(titleText);
    titleEl.appendChild(toggle);

    const body = el("div", collapsed ? "section-body collapsed" : "section-body");
    body.id = `${id}-body`;
    body.appendChild(bodyFn());

    section.appendChild(titleEl);
    section.appendChild(body);
    return section;
  }

  // ── Data loading ──────────────────────────────────────────────────────────

  async _loadState() {
    try {
      const result = await this._hass.connection.sendMessagePromise({
        type: "voiceforge/get_state",
      });
      this._characters = result.characters || [];
      this._activeCharId = result.active_character_id;
      this._updateHero();
      this._updateCharGrid();
      this._populateFilters();
    } catch (err) {
      console.error("VoiceForge: failed to load state", err);
    }

    try {
      const result = await this._hass.connection.sendMessagePromise({
        type: "voiceforge/get_messages",
      });
      this._messages = result.messages || [];
    } catch (_err) {
      // message endpoint may not be wired yet
    }
    this._renderMessages();
  }

  async _loadMemory(charId) {
    if (!charId) return;
    const listEl = this.shadowRoot.getElementById("mem-list");
    if (!listEl) return;
    listEl.replaceChildren(emptyNote("Loading..."));
    try {
      const result = await this._hass.connection.sendMessagePromise({
        type: "voiceforge/get_memory",
        character_id: charId,
      });
      this._memory = result.entries || [];
      this._renderMemory();
    } catch (_err) {
      listEl.replaceChildren(emptyNote("Memory not available."));
    }
  }

  // ── WebSocket emotion subscription ────────────────────────────────────────

  _subscribeEmotionEvents() {
    this._emotionSub = this._hass.connection.subscribeEvents((event) => {
      const { character_id, sprite_url } = event.data;
      if (character_id === this._activeCharId) {
        const img = this.shadowRoot.getElementById("sprite-hero");
        if (img) img.src = sprite_url;
      }
    }, "voiceforge_emotion_change");
  }

  // ── DOM updates (all via textContent — no innerHTML for user data) ────────

  _updateHero() {
    const active = this._characters.find(c => c.id === this._activeCharId);
    if (!active) return;
    const img = this.shadowRoot.getElementById("sprite-hero");
    if (img) {
      img.src = `/local/voiceforge/sprites/${active.id}/idle.gif`;
      img.alt = active.name;
    }
    const label = this.shadowRoot.getElementById("hero-label");
    if (label) label.textContent = active.name + (active.description ? " — " + active.description : "");
  }

  _updateCharGrid() {
    const grid = this.shadowRoot.getElementById("char-grid");
    if (!grid) return;
    grid.replaceChildren();
    if (this._characters.length === 0) {
      grid.appendChild(emptyNote("No characters loaded."));
      return;
    }
    this._characters.forEach(c => {
      const card = el("div", "char-card" + (c.id === this._activeCharId ? " active" : ""));
      card.dataset.charId = c.id;

      const img = document.createElement("img");
      img.src = `/local/voiceforge/sprites/${c.id}/idle.gif`;
      img.alt = c.name;

      const name = el("div", "cname", c.name);
      const desc = el("div", "cdesc", c.description || "");

      card.appendChild(img);
      card.appendChild(name);
      card.appendChild(desc);
      grid.appendChild(card);
    });
  }

  _populateFilters() {
    const charSel = this.shadowRoot.getElementById("filter-character");
    const memSel = this.shadowRoot.getElementById("mem-character-select");
    this._characters.forEach(c => {
      [charSel, memSel].forEach(sel => {
        const opt = document.createElement("option");
        opt.value = c.id;
        opt.textContent = c.name;
        sel.appendChild(opt);
      });
    });
  }

  _renderMessages() {
    const list = this.shadowRoot.getElementById("msg-list");
    if (!list) return;

    const charVal = (this.shadowRoot.getElementById("filter-character") || {}).value || "all";
    const memberVal = (this.shadowRoot.getElementById("filter-member") || {}).value || "all";
    const typeVal = (this.shadowRoot.getElementById("filter-type") || {}).value || "all";

    const filtered = this._messages.filter(m => {
      if (charVal !== "all" && m.from !== charVal) return false;
      if (memberVal !== "all" && m.to !== memberVal && m.to !== "all") return false;
      if (typeVal !== "all" && m.type !== typeVal) return false;
      return true;
    });

    list.replaceChildren();
    if (filtered.length === 0) {
      list.appendChild(emptyNote("No messages."));
      return;
    }

    filtered.forEach(m => {
      const item = el("div", "msg-item" + (m.read ? " read" : " unread"));
      item.dataset.msgId = m.id || "";

      const meta = el("div", "msg-meta");
      meta.appendChild(el("span", "msg-from", m.from || "?"));
      meta.appendChild(el("span", null, " → "));
      meta.appendChild(el("span", null, m.to || "all"));
      const badge = el("span", "msg-badge " + (m.type === "personal" ? "personal" : "event"),
        m.type === "personal" ? "personal" : "event");
      meta.appendChild(badge);
      if (m.ts) {
        meta.appendChild(el("span", null, new Date(m.ts).toLocaleString()));
      }

      const body = el("div", "msg-body", m.body || "");
      item.appendChild(meta);
      item.appendChild(body);
      list.appendChild(item);
    });
  }

  _renderMemory() {
    const list = this.shadowRoot.getElementById("mem-list");
    if (!list) return;
    list.replaceChildren();
    if (this._memory.length === 0) {
      list.appendChild(emptyNote("No memory entries."));
      return;
    }
    this._memory.forEach(entry => {
      const item = el("div", "mem-entry");
      item.appendChild(el("div", "mem-cat", entry.category || "general"));
      item.appendChild(el("div", "mem-fact", entry.fact || ""));
      list.appendChild(item);
    });
  }

  // ── Event handling ────────────────────────────────────────────────────────

  async _handleClick(e) {
    // Section collapse/expand
    const sectionTitle = e.target.closest("[data-section]");
    if (sectionTitle) {
      const id = sectionTitle.dataset.section;
      const body = this.shadowRoot.getElementById(`${id}-body`);
      const toggle = sectionTitle.querySelector(".toggle");
      if (body) {
        body.classList.toggle("collapsed");
        if (toggle) toggle.textContent = body.classList.contains("collapsed") ? "▶" : "▼";
      }
      return;
    }

    // Character switch
    const charCard = e.target.closest("[data-char-id]");
    if (charCard) {
      const charId = charCard.dataset.charId;
      if (charId === this._activeCharId) return;
      try {
        await this._hass.connection.sendMessagePromise({
          type: "voiceforge/switch_character",
          character_id: charId,
        });
        this._activeCharId = charId;
        this._updateHero();
        this._updateCharGrid();
      } catch (err) {
        console.error("VoiceForge: failed to switch character", err);
      }
      return;
    }

    // Mark message as read on tap
    const msgItem = e.target.closest("[data-msg-id]");
    if (msgItem && msgItem.classList.contains("unread")) {
      msgItem.classList.replace("unread", "read");
    }
  }

  // ── Lifecycle ─────────────────────────────────────────────────────────────

  disconnectedCallback() {
    if (this._emotionSub) {
      Promise.resolve(this._emotionSub).then(unsub => {
        if (typeof unsub === "function") unsub();
      });
      this._emotionSub = null;
    }
  }
}

customElements.define("voiceforge-panel", VoiceForgePanel);
