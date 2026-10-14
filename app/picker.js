// Gleaner picker. Injected into every page the Builder loads, in an isolated script world:
// the page's own scripts can neither see nor call it. Turns a click into CSS selectors that
// core/extract.py (BeautifulSoup/soupsieve) evaluates the same way the browser does.
// Results go to the app as console messages tagged with a per-session token.
(() => {
  if (window.__gleaner) return;
  const TOKEN = "%TOKEN%";
  const SKIP_ITEM_TAGS = new Set(["TD", "TH", "SPAN", "A", "B", "STRONG", "EM", "I", "IMG", "BR", "OPTION",
    "SMALL", "LABEL", "BUTTON", "FONT", "U", "SUP", "SUB", "ABBR", "P", "H1", "H2", "H3", "H4", "H5", "H6"]);
  const SKIP_PATH_TAGS = new Set(["TBODY", "THEAD", "TFOOT"]); // html.parser does not invent <tbody>
  const ATTR_KEYS = ["itemprop", "data-title", "data-label", "data-field", "name"];
  const UNSTABLE_CLASS = /^(active|selected|current|hover|focus|open|odd|even|first|last|clearfix|ng-|css-|sc-|jsx-)/;

  let mode = null;
  let ctx = {};
  let layer, hoverBox, highlights = [];

  const send = (payload) => console.log("__GLEANER__" + TOKEN + JSON.stringify(payload));
  const text = (el) => (el ? (el.textContent || "").replace(/\s+/g, " ").trim() : "");
  const esc = (s) => CSS.escape(s);

  function ensureLayer() {
    if (layer && layer.isConnected) return;
    layer = document.createElement("div");
    layer.id = "__gleaner_layer";
    layer.style.cssText = "position:absolute;left:0;top:0;width:0;height:0;z-index:2147483647;pointer-events:none";
    document.documentElement.appendChild(layer);
    hoverBox = box("#2E86C1", true);
  }

  function box(color, dashed) {
    const d = document.createElement("div");
    d.style.cssText = "position:absolute;pointer-events:none;box-sizing:border-box;display:none;" +
      `border:2px ${dashed ? "dashed" : "solid"} ${color};` +
      `background:${dashed ? "transparent" : "rgba(243,156,18,0.15)"}`;
    layer.appendChild(d);
    return d;
  }

  function place(d, el) {
    const r = el.getBoundingClientRect();
    Object.assign(d.style, {
      left: r.left + window.scrollX + "px", top: r.top + window.scrollY + "px",
      width: r.width + "px", height: r.height + "px", display: "block",
    });
  }

  function clearHighlights() {
    highlights.forEach((d) => d.remove());
    highlights = [];
  }

  function highlight(els) {
    ensureLayer();
    clearHighlights();
    els.slice(0, 500).forEach((el) => {
      const d = box("#F39C12", false);
      place(d, el);
      highlights.push(d);
    });
  }

  // ---- selector building -------------------------------------------------------------------

  function goodClasses(el) {
    return [...el.classList]
      .filter((c) => /^[A-Za-z][\w-]*$/.test(c) && !/\d{3,}/.test(c) && !UNSTABLE_CLASS.test(c))
      .slice(0, 3);
  }

  function goodId(el) {
    return el.id && /^[A-Za-z][\w-]*$/.test(el.id) && !/\d{4,}/.test(el.id) ? el.id : null;
  }

  function attrStep(el) {
    const tag = el.tagName.toLowerCase();
    for (const k of ATTR_KEYS) {
      const v = el.getAttribute(k);
      if (v && v.length <= 40 && !/["\\\n]/.test(v)) return `${tag}[${k}="${v}"]`;
    }
    return null;
  }

  function step(el, withNth) {
    const byAttr = attrStep(el);
    if (byAttr) return byAttr;
    const cls = goodClasses(el);
    let s = el.tagName.toLowerCase() + cls.map((c) => "." + esc(c)).join("");
    if (withNth && el.parentElement) {
      const sameTag = [...el.parentElement.children].filter((x) => x.tagName === el.tagName);
      const sameClass = sameTag.filter((x) => cls.every((c) => x.classList.contains(c)));
      if (sameTag.length > 1 && !(cls.length && sameClass.length === 1)) {
        s += `:nth-of-type(${sameTag.indexOf(el) + 1})`;
      }
    }
    return s;
  }

  // Ancestors of el, from the nearest one with a stable id, as descendant-combinator steps.
  function anchorChain(el, withNth) {
    const parts = [];
    for (let p = el.parentElement; p && p !== document.body && p !== document.documentElement; p = p.parentElement) {
      const id = goodId(p);
      if (id) {
        parts.unshift("#" + esc(id));
        break;
      }
      if (!SKIP_PATH_TAGS.has(p.tagName)) parts.unshift(step(p, withNth));
    }
    return parts.join(" ");
  }

  function absPath(el) {
    const id = goodId(el);
    if (id) return "#" + esc(id);
    const chain = anchorChain(el, true);
    return (chain ? chain + " " : "") + step(el, true);
  }

  // Same tag and, if el has classes, at least one class in common ("card" vs "card featured").
  function similarSiblings(el) {
    if (!el.parentElement) return [];
    const cls = goodClasses(el);
    return [...el.parentElement.children].filter(
      (x) => x.tagName === el.tagName && (!cls.length || cls.some((c) => x.classList.contains(c))));
  }

  function findItem(el) {
    for (let a = el; a && a !== document.body; a = a.parentElement) {
      if (SKIP_ITEM_TAGS.has(a.tagName)) continue;
      if (similarSiblings(a).length >= 2) return a;
    }
    return null;
  }

  function itemSelectorFor(item) {
    const chain = anchorChain(item, false);
    const common = goodClasses(item).filter((c) => similarSiblings(item).every((x) => x.classList.contains(c)));
    const own = item.tagName.toLowerCase() + common.map((c) => "." + esc(c)).join("");
    return (chain ? chain + " " : "") + own;
  }

  function relSteps(item, el) {
    const steps = [];
    for (let e = el; e && e !== item; e = e.parentElement) {
      if (!SKIP_PATH_TAGS.has(e.tagName)) steps.unshift(step(e, true));
    }
    return steps;
  }

  const toRel = (steps) => (steps.length ? ":scope " + steps.join(" ") : ":scope");
  const stripNth = (s) => s.replace(/:nth-of-type\(\d+\)$/, "");

  // Two examples of the same field: keep what they share, loosen what differs.
  function mergeSteps(a, b) {
    if (a.length !== b.length) return b;
    return a.map((x, i) => {
      const y = b[i];
      if (x === y) return x;
      if (stripNth(x) === stripNth(y)) return stripNth(x);
      const tx = x.match(/^[a-z0-9]+/), ty = y.match(/^[a-z0-9]+/);
      return tx && ty && tx[0] === ty[0] ? tx[0] : y;
    });
  }

  function matchesFor(itemSelector, rel) {
    const out = [];
    document.querySelectorAll(itemSelector).forEach((it) => {
      const m = rel === ":scope" ? it : it.querySelector(rel);
      if (m) out.push(m);
    });
    return out;
  }

  function itemFor(el) {
    if (ctx.itemSelector) return el.closest(ctx.itemSelector);
    return findItem(el);
  }

  // Label/value rows: <tr><td>Phone Number</td><td>98...</td></tr> or <dt>Phone</dt><dd>98...</dd>.
  function labelFor(el) {
    const dd = el.closest("dd");
    if (dd && dd.previousElementSibling && dd.previousElementSibling.tagName === "DT") {
      const lab = text(dd.previousElementSibling);
      const chain = anchorChain(dd.previousElementSibling, false);
      if (lab && lab.length <= 40) return { label: lab, label_scope: (chain ? chain + " " : "") + "dt" };
    }
    let depth = 0;
    for (let r = el; r && r !== document.body && depth < 5; r = r.parentElement, depth++) {
      const kids = [...r.children];
      if (kids.length < 2 || !kids[1].contains(el)) continue;
      const lab = text(kids[0]);
      if (!lab || lab.length > 40) continue;
      const chain = anchorChain(r, false);
      return { label: lab, label_scope: (chain ? chain + " " : "") + step(r, false) };
    }
    return null;
  }

  function nextFor(el) {
    const a = el.closest("a[href]");
    if (!a) return { type: "error", message: "That isn't a link. Click the Next button or the next page number." };
    const cur = new URL(location.href);
    const nxt = new URL(a.getAttribute("href"), location.href);
    for (const [k, v] of nxt.searchParams) {
      if (!/^\d+$/.test(v)) continue;
      const curv = parseInt(cur.searchParams.get(k) || "1", 10);
      if (parseInt(v, 10) === curv + 1) return { type: "next", pagination: { type: "page_param", param: k, start: curv } };
    }
    const rel = (a.getAttribute("rel") || "").split(/\s+/);
    if (rel.includes("next")) return { type: "next", pagination: { type: "next_link", selector: 'a[rel~="next"]' } };
    const chain = anchorChain(a, false);
    const cls = goodClasses(a);
    const sel = (chain ? chain + " " : "") + "a" + cls.map((c) => "." + esc(c)).join("");
    const pagination = { type: "next_link", selector: sel };
    const matches = [...document.querySelectorAll(sel)];
    if (matches.length !== 1 || matches[0] !== a) pagination.text = text(a);
    return { type: "next", pagination };
  }

  // ---- click handling ----------------------------------------------------------------------

  function handle(el) {
    if (!el || (layer && layer.contains(el))) return null;
    let res;
    try {
      if (mode === "list" || mode === "link") {
        const target = mode === "link" ? el.closest("a[href]") : el;
        const item = target && itemFor(target);
        if (mode === "link" && !target) {
          res = { type: "error", message: "That isn't a link. Click the link that opens one item's page." };
        } else if (!item) {
          res = { type: "error", message: ctx.itemSelector
            ? "That isn't inside one of the list items already picked. Click inside a highlighted item."
            : "This looks like a single item, not part of a list. Click something that repeats for every item." };
        } else {
          const itemSelector = ctx.itemSelector || itemSelectorFor(item);
          let steps = relSteps(item, target);
          if (ctx.refineSteps) steps = mergeSteps(ctx.refineSteps, steps);
          const selector = toRel(steps);
          const matches = matchesFor(itemSelector, selector);
          highlight(matches);
          const hintKey = ATTR_KEYS.find((k) => target.getAttribute(k));
          res = {
            type: mode, itemSelector, selector, steps, count: matches.length,
            items: document.querySelectorAll(itemSelector).length, sample: text(target).slice(0, 80),
            hint: hintKey ? target.getAttribute(hintKey) : null,
            href: mode === "link" ? target.href : null,
          };
        }
      } else if (mode === "detail") {
        const lab = labelFor(el);
        highlight([el]);
        res = { type: "detail", selector: absPath(el), sample: text(el).slice(0, 80), ...(lab || {}) };
      } else if (mode === "next") {
        res = nextFor(el);
        if (res.type === "next") highlight([el.closest("a[href]")]);
      }
    } catch (err) {
      res = { type: "error", message: "Couldn't use that element (" + err.message + ")." };
    }
    stop();
    if (res) send(res);
    return res;
  }

  function stop() {
    mode = null;
    ctx = {};
    if (hoverBox) hoverBox.style.display = "none";
    document.documentElement.style.cursor = "";
  }

  function block(ev) {
    if (!mode) return;
    ev.preventDefault();
    ev.stopPropagation();
    ev.stopImmediatePropagation();
    if (ev.type === "click") handle(ev.target);
  }

  ["click", "mousedown", "mouseup", "pointerdown", "pointerup", "dblclick", "submit"].forEach((t) =>
    window.addEventListener(t, block, true));
  window.addEventListener("mouseover", (ev) => {
    if (!mode || (layer && layer.contains(ev.target))) return;
    place(hoverBox, ev.target);
  }, true);
  window.addEventListener("keydown", (ev) => {
    if (mode && ev.key === "Escape") {
      stop();
      send({ type: "cancel" });
    }
  }, true);

  window.__gleaner = {
    start(m, options) {
      ensureLayer();
      mode = m;
      ctx = options || {};
      document.documentElement.style.cursor = "crosshair";
    },
    stop,
    handle,
    show(itemSelector, selector) {
      try {
        highlight(selector === undefined ? [...document.querySelectorAll(itemSelector)] : matchesFor(itemSelector, selector));
      } catch (err) {
        clearHighlights();
      }
    },
    showOne(selector) {
      try {
        const el = document.querySelector(selector);
        highlight(el ? [el] : []);
      } catch (err) {
        clearHighlights();
      }
    },
    clear: clearHighlights,
    // Page HTML without the picker's own overlay, for previews.
    snapshot() {
      const attached = layer && layer.isConnected;
      if (attached) layer.remove();
      const html = "<!DOCTYPE html>" + document.documentElement.outerHTML;
      if (attached) document.documentElement.appendChild(layer);
      return html;
    },
  };
})();
