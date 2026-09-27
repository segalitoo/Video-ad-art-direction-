// Static ads in Figma: the layout system from templates/static-design.md.
// Run through the Figma connector (use_figma), after loading the figma-use skill.
// Edit only CONFIG. It builds one frame per placement: a photo slot, the paper sheet,
// the copy set in the brand font, the wordmark and the CTA. It returns the photo slot ids;
// fill them with upload_assets (nodeIds = those ids, scaleMode FILL) using the kept plates.
//
// Photo slots keep the plate's own aspect ratio, so FILL never crops; the frame clips them.
// Place a slot so the subject lands where the layout wants it (below the sheet, right of the column).
// This file is the Driftpay config, as built on 2026-09-27.

const CONFIG = {
  font: "Space Grotesk",                     // the lock's type.family; must be in the Figma file's fonts
  colors: { sheet: "#F4F1EA", ink: "#1E2A44", muted: "#4A5568", accent: "#FF6B4A", ground: "#957751" },
  brand: "Driftpay",
  statics: [
    { name: "A1 · LinkedIn 1200×1200", w: 1200, h: 1200, layout: "band", sheet: 500, pad: 96, top: 88,
      head: "Get paid like it’s local.", headSize: 112, sub: "Cross-border payments for freelancers", subSize: 30,
      cta: "Open a free account", ctaSize: 28, mark: 40, photo: { plate: "map", w: 1200, h: 2133, x: 0, y: -145 } },
    { name: "A1 · LinkedIn 1200×628", w: 1200, h: 628, layout: "split", column: 560, pad: 64, top: 64,
      head: "Get paid like it’s local.", headSize: 76, sub: "Cross-border payments for freelancers", subSize: 24,
      cta: "Open a free account", ctaSize: 22, mark: 30, photo: { plate: "map", w: 1037, h: 1843, x: 291, y: -496 } },
    { name: "A1 · Meta feed 1080×1350", w: 1080, h: 1350, layout: "band", sheet: 540, pad: 86, top: 84,
      head: "Get paid like it’s local.", headSize: 104, sub: "Payments for freelancers", subSize: 28,
      cta: "Open a free account", ctaSize: 26, mark: 36, photo: { plate: "map", w: 1080, h: 1920, x: 0, y: -25 } },
    { name: "A2 · Stories 1080×1920", w: 1080, h: 1920, layout: "number", sheet: 700, pad: 86, top: 300,
      pre: "Paid in", number: "1 day.", post: "Not 5.", wordSize: 64, numberSize: 220, mark: 34, cta: null,
      photo: { plate: "coins", w: 1382, h: 2458, x: -12, y: -459 } },
    { name: "A2 · Meta feed 1080×1350", w: 1080, h: 1350, layout: "number-inline", sheet: 560, pad: 86, top: 80,
      pre: "Paid in", number: "1 day.", post: "Not 5.", wordSize: 60, numberSize: 190, mark: 34,
      cta: "Open a free account", ctaSize: 26, photo: { plate: "coins", w: 1382, h: 2458, x: -12, y: -529 } },
  ],
};

await Promise.all(["Bold", "Medium"].map(style => figma.loadFontAsync({ family: CONFIG.font, style })));
const hex = h => ({ r: parseInt(h.slice(1, 3), 16) / 255, g: parseInt(h.slice(3, 5), 16) / 255, b: parseInt(h.slice(5, 7), 16) / 255 });
const C = Object.fromEntries(Object.entries(CONFIG.colors).map(([k, v]) => [k, hex(v)]));
const solid = c => [{ type: "SOLID", color: c }];
const created = [], photos = [];

function text(parent, chars, style, size, color, opts = {}) {
  const t = figma.createText();
  t.fontName = { family: CONFIG.font, style };
  t.characters = chars;
  t.fontSize = size;
  t.fills = solid(color);
  t.lineHeight = { unit: "PERCENT", value: opts.lh || 100 };
  t.letterSpacing = { unit: "PERCENT", value: opts.ls ?? -2 };
  parent.appendChild(t);
  if (opts.width) { t.textAutoResize = "HEIGHT"; t.resize(opts.width, t.height); }
  return t;
}
function wordmark(parent, size) {
  const row = figma.createAutoLayout("HORIZONTAL", { name: "Wordmark", itemSpacing: Math.round(size * 0.3), counterAxisAlignItems: "CENTER" });
  row.fills = [];
  const plane = figma.createVector();
  plane.name = "Mark";
  plane.vectorPaths = [{ windingRule: "NONZERO", data: "M 0 11 L 24 0 L 13 24 L 10 14 Z" }];
  plane.fills = solid(C.accent);
  plane.resize(size * 0.75, size * 0.75);
  row.appendChild(plane);
  text(row, CONFIG.brand, "Bold", size, C.ink, { ls: -3 });
  parent.appendChild(row);
}
function pill(parent, label, size) {
  const p = figma.createAutoLayout("HORIZONTAL", { name: "CTA", paddingLeft: size * 1.1, paddingRight: size * 1.1, paddingTop: size * 0.6, paddingBottom: size * 0.6, cornerRadius: 999 });
  p.fills = solid(C.accent);
  text(p, label, "Bold", size, C.ink, { ls: -1 });
  parent.appendChild(p);
}
function row(parent, name, align, gap) {
  const r = figma.createAutoLayout("HORIZONTAL", { name, itemSpacing: gap, counterAxisAlignItems: align });
  r.fills = [];
  parent.appendChild(r);
  return r;
}

const x0 = Math.max(0, ...figma.currentPage.children.map(n => n.x + n.width)) + (figma.currentPage.children.length ? 200 : 0);
let X = x0;
for (const s of CONFIG.statics) {
  const f = figma.createFrame();
  f.name = s.name; f.resize(s.w, s.h); f.x = X; f.y = 0; f.clipsContent = true; f.fills = solid(C.ground);
  figma.currentPage.appendChild(f); created.push(f.id); X += s.w + 100;
  const p = figma.createRectangle();
  p.name = s.photo.plate; p.resize(s.photo.w, s.photo.h); p.x = s.photo.x; p.y = s.photo.y; p.fills = solid(C.ground);
  f.appendChild(p); photos.push({ frame: s.name, slot: p.id, plate: s.photo.plate });
  const sheet = figma.createRectangle();
  sheet.name = "Sheet";
  if (s.layout === "split") sheet.resize(s.column, s.h); else sheet.resize(s.w, s.sheet);
  sheet.fills = solid(C.sheet);
  sheet.effects = [{ type: "DROP_SHADOW", color: { r: 0.12, g: 0.09, b: 0.05, a: 0.28 }, offset: { x: 0, y: 6 }, radius: 18, spread: 0, visible: true, blendMode: "NORMAL" }];
  f.appendChild(sheet);
  const col = figma.createAutoLayout("VERTICAL", { name: "Copy", itemSpacing: s.layout.startsWith("number") ? 0 : Math.round(s.headSize * 0.25) });
  col.fills = []; col.x = s.pad; col.y = s.top; f.appendChild(col);
  const width = (s.layout === "split" ? s.column : s.w) - 2 * s.pad;
  wordmark(col, s.mark);
  if (s.layout === "band" || s.layout === "split") {
    text(col, s.head, "Bold", s.headSize, C.ink, { width, lh: 98 });
    if (s.layout === "split") {
      text(col, s.sub, "Medium", s.subSize, C.muted, { width, ls: -1 });
      pill(col, s.cta, s.ctaSize);
    } else {
      const r = row(col, "Sub + CTA", "CENTER", 32);
      text(r, s.sub, "Medium", s.subSize, C.muted, { ls: -1 });
      pill(r, s.cta, s.ctaSize);
    }
  } else {
    const gap = figma.createFrame(); gap.name = "Space"; gap.resize(10, Math.round(s.mark * 0.7)); gap.fills = []; col.appendChild(gap);
    if (s.layout === "number") {
      text(col, s.pre, "Medium", s.wordSize, C.ink);
      text(col, s.number, "Bold", s.numberSize, C.ink, { lh: 92, ls: -5 });
      text(col, s.post, "Medium", s.wordSize, C.muted);
      if (s.cta) pill(col, s.cta, s.ctaSize);
    } else {
      const top = row(col, "Line", "BASELINE", 22);
      text(top, s.pre, "Medium", s.wordSize, C.ink);
      text(top, s.number, "Bold", s.numberSize, C.ink, { lh: 92, ls: -5 });
      const bot = row(col, "Line 2", "CENTER", 28);
      text(bot, s.post, "Medium", s.wordSize, C.muted);
      if (s.cta) pill(bot, s.cta, s.ctaSize);
    }
  }
}
return { createdFrameIds: created, photoSlots: photos };
