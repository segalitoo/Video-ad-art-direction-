// Driftpay statics v2: two directions built from the taste library (examples/driftpay/statics-v2/plan.md).
// Run through use_figma after loading the figma-use skill. Edit only CONFIG.
// A · One bold word: paper field, a huge word, the cut-out hero crossing it (T0013, T0012, T0016, L010).
// B · The hand lets go: full-bleed hand photo, one coral phrase, a floating proof chip (T0022, T0025, T0024, T0017).
// Returns the image slot ids; fill them with upload_assets (nodeIds, scaleMode FILL).
// Slots keep the source image's aspect ratio, so FILL never distorts; the frame clips them.

const CONFIG = {
  font: "Space Grotesk",
  c: { paper: "#F4F1EA", navy: "#1E2A44", coral: "#FF6B4A", white: "#FFFFFF", muted: "#5B6478", mutedDark: "#B8C0D2" },
  y0: 2300,                                  // below the v1 frames
  cta: "Open a free account",
  A: [
    { name: "v2 A · A1 LinkedIn 1200×1200", w: 1200, h: 1200, kind: "word", word: "LOCAL.", wordSize: 330, wordY: 330,
      sub: "Get paid from abroad like it’s next door.", subSize: 40, subY: 800, ctaSize: 30, ctaY: 1010, pad: 90, mark: 38,
      hero: { slot: "plane", w: 640, x: 560, y: 150, rot: 0 } },
    { name: "v2 A · A1 LinkedIn 1200×628", w: 1200, h: 628, kind: "word", word: "LOCAL.", wordSize: 300, wordY: 120,
      sub: "Get paid from abroad like it’s next door.", subSize: 30, subY: 470, ctaSize: 24, ctaY: 520, ctaX: 790, pad: 64, mark: 30,
      hero: { slot: "plane", w: 470, x: 620, y: -20, rot: 0 } },
    { name: "v2 A · A1 Meta feed 1080×1350", w: 1080, h: 1350, kind: "word", word: "LOCAL.", wordSize: 296, wordY: 420,
      sub: "Get paid from abroad like it’s next door.", subSize: 40, subY: 900, ctaSize: 30, ctaY: 1150, pad: 80, mark: 36,
      hero: { slot: "plane", w: 600, x: 470, y: 230, rot: 0 } },
    { name: "v2 A · A2 Stories 1080×1920", w: 1080, h: 1920, kind: "number", pre: "Paid in", number: "1 day.", post: "Not 5.",
      preSize: 80, numberSize: 300, numberY: 330, pad: 86, mark: 36, cta: false,
      hero: { slot: "coins", w: 560, x: 260, y: 1200, rot: 0 } },
    { name: "v2 A · A2 Meta feed 1080×1350", w: 1080, h: 1350, kind: "number", pre: "Paid in", number: "1 day.", post: "Not 5.",
      preSize: 64, numberSize: 250, numberY: 190, pad: 80, mark: 34, cta: true, ctaSize: 28,
      hero: { slot: "coins", w: 420, x: 600, y: 780, rot: 0 } },
  ],
  B: [
    { name: "v2 B · A1 LinkedIn 1200×1200", w: 1200, h: 1200, field: "navy", photo: { slot: "B-plane", w: 1200, h: 1600, x: 0, y: -200 },
      lines: ["Send the invoice.", "Get paid |tomorrow.|"], size: 92, pad: 90, top: 90, mark: 38, ctaSize: 30,
      chip: { x: 150, y: 760 } },
    { name: "v2 B · A1 LinkedIn 1200×628", w: 1200, h: 628, field: "navy", photo: { slot: "B-plane", w: 600, h: 800, x: 600, y: -60 },
      lines: ["Send the invoice.", "Get paid |tomorrow.|"], size: 60, pad: 64, top: 64, mark: 30, ctaSize: 24, column: 580,
      chip: { x: 640, y: 420 } },
    { name: "v2 B · A1 Meta feed 1080×1350", w: 1080, h: 1350, field: "navy", photo: { slot: "B-plane", w: 1080, h: 1440, x: 0, y: -40 },
      lines: ["Send the invoice.", "Get paid |tomorrow.|"], size: 88, pad: 80, top: 90, mark: 36, ctaSize: 30,
      chip: { x: 120, y: 860 } },
    { name: "v2 B · A2 Stories 1080×1920", w: 1080, h: 1920, field: "paper", photo: { slot: "B-coins-916", w: 1080, h: 1920, x: 0, y: 0 },
      lines: ["Paid in", "|1 day.|", "Not 5."], size: 150, pad: 86, top: 330, mark: 36, cta: false },
    { name: "v2 B · A2 Meta feed 1080×1350", w: 1080, h: 1350, field: "paper", photo: { slot: "B-coins-34", w: 1080, h: 1440, x: 0, y: -60 },
      lines: ["Paid in", "|1 day.|", "Not 5."], size: 120, pad: 80, top: 90, mark: 34, ctaSize: 28 },
  ],
  heroAspect: { plane: 1, coins: 1 },      // w/h of each cut-out, set from the files before running
};

await Promise.all(["Bold", "Medium"].map(style => figma.loadFontAsync({ family: CONFIG.font, style })));
const hex = h => ({ r: parseInt(h.slice(1, 3), 16) / 255, g: parseInt(h.slice(3, 5), 16) / 255, b: parseInt(h.slice(5, 7), 16) / 255 });
const C = Object.fromEntries(Object.entries(CONFIG.c).map(([k, v]) => [k, hex(v)]));
const solid = c => [{ type: "SOLID", color: c }];
const created = [], slots = [];

function text(parent, chars, style, size, color, o = {}) {
  const t = figma.createText();
  t.fontName = { family: CONFIG.font, style };
  t.characters = chars;
  t.fontSize = size;
  t.fills = solid(color);
  t.lineHeight = { unit: "PERCENT", value: o.lh || 100 };
  t.letterSpacing = { unit: "PERCENT", value: o.ls ?? -2 };
  parent.appendChild(t);
  if (o.width) { t.textAutoResize = "HEIGHT"; t.resize(o.width, t.height); }
  if (o.x !== undefined) { t.x = o.x; t.y = o.y; }
  return t;
}
// "Get paid |tomorrow.|" : the part between bars is the one coral phrase
function accentText(parent, line, style, size, base, accent, o = {}) {
  const plain = line.replace(/\|/g, "");
  const t = text(parent, plain, style, size, base, o);
  const a = line.indexOf("|"), b = line.lastIndexOf("|");
  if (a >= 0 && b > a) t.setRangeFills(a, b - 1, solid(accent));
  return t;
}
function wordmark(parent, size, ink, x, y) {
  const row = figma.createAutoLayout("HORIZONTAL", { name: "Wordmark", itemSpacing: Math.round(size * 0.3), counterAxisAlignItems: "CENTER" });
  row.fills = [];
  const plane = figma.createVector();
  plane.name = "Mark";
  plane.vectorPaths = [{ windingRule: "NONZERO", data: "M 0 11 L 24 0 L 13 24 L 10 14 Z" }];
  plane.fills = solid(C.coral);
  plane.resize(size * 0.75, size * 0.75);
  row.appendChild(plane);
  text(row, "Driftpay", "Bold", size, ink, { ls: -3 });
  parent.appendChild(row);
  row.x = x; row.y = y;
  return row;
}
function pill(parent, label, size, x, y) {
  const p = figma.createAutoLayout("HORIZONTAL", { name: "CTA", paddingLeft: size * 1.1, paddingRight: size * 1.1, paddingTop: size * 0.62, paddingBottom: size * 0.62, cornerRadius: 999 });
  p.fills = solid(C.coral);
  text(p, label, "Bold", size, C.navy, { ls: -1 });
  parent.appendChild(p);
  p.x = x; p.y = y;
  return p;
}
function slot(parent, name, w, h, x, y, o = {}) {
  const r = figma.createRectangle();
  r.name = name; r.resize(w, h); r.x = x; r.y = y;
  r.fills = [{ type: "SOLID", color: C.navy, opacity: 0.08 }];
  if (o.rot) r.rotation = o.rot;
  if (o.shadow) r.effects = [{ type: "DROP_SHADOW", color: { r: 0.12, g: 0.1, b: 0.08, a: 0.22 }, offset: { x: 0, y: o.shadow }, radius: o.shadow * 1.4, spread: 0, visible: true, blendMode: "MULTIPLY" }];
  parent.appendChild(r);
  slots.push({ frame: parent.name, slot: r.id, image: name });
  return r;
}
function frame(s, X, Y, bg) {
  const f = figma.createFrame();
  f.name = s.name; f.resize(s.w, s.h); f.x = X; f.y = Y; f.clipsContent = true; f.fills = solid(bg);
  figma.currentPage.appendChild(f); created.push(f.id);
  return f;
}

// Direction A
let X = 0;
for (const s of CONFIG.A) {
  const f = frame(s, X, CONFIG.y0, C.paper); X += s.w + 100;
  wordmark(f, s.mark, C.navy, s.pad, s.pad * 0.8);
  const hw = s.hero.w, hh = Math.round(hw / CONFIG.heroAspect[s.hero.slot]);
  if (s.kind === "word") {
    const word = text(f, s.word, "Bold", s.wordSize, C.navy, { ls: -5, lh: 90, x: s.pad * 0.6, y: s.wordY });
    word.name = "Big word";
    slot(f, s.hero.slot, hw, hh, s.hero.x, s.hero.y, { shadow: 40, rot: s.hero.rot });   // above the word: it crosses it
    text(f, s.sub, "Medium", s.subSize, C.navy, { ls: -1, width: Math.min(s.w - 2 * s.pad, s.subSize * 14), x: s.pad, y: s.subY });
    pill(f, CONFIG.cta, s.ctaSize, s.ctaX ?? s.pad, s.ctaY);
  } else {
    slot(f, s.hero.slot, hw, hh, s.hero.x, s.hero.y, { shadow: 30 });                     // never over the claim
    const col = figma.createAutoLayout("VERTICAL", { name: "Claim", itemSpacing: 0 });
    col.fills = []; f.appendChild(col); col.x = s.pad; col.y = s.numberY;
    text(col, s.pre, "Medium", s.preSize, C.navy);
    text(col, s.number, "Bold", s.numberSize, C.navy, { ls: -5, lh: 92 });
    text(col, s.post, "Medium", s.preSize, C.muted);
    if (s.cta) pill(f, CONFIG.cta, s.ctaSize, s.pad, s.h - s.pad - s.ctaSize * 2.3);
  }
}

// Direction B
X = 0;
for (const s of CONFIG.B) {
  const dark = s.field === "navy";
  const f = frame(s, X, CONFIG.y0 + 2100, dark ? C.navy : C.paper); X += s.w + 100;
  slot(f, s.photo.slot, s.photo.w, s.photo.h, s.photo.x, s.photo.y);
  const ink = dark ? C.white : C.navy;
  wordmark(f, s.mark, ink, s.pad, s.pad * 0.8);
  const col = figma.createAutoLayout("VERTICAL", { name: "Headline", itemSpacing: 0 });
  col.fills = []; f.appendChild(col); col.x = s.pad; col.y = s.top + s.mark * 2.2;
  for (const line of s.lines) accentText(col, line, "Bold", s.size, ink, C.coral, { ls: -3, lh: 104 });
  if (s.cta !== false) pill(f, CONFIG.cta, s.ctaSize, s.pad, col.y + col.height + s.size * 0.45);
  if (s.chip) {
    const chip = figma.createAutoLayout("HORIZONTAL", { name: "Proof chip", itemSpacing: 14, paddingLeft: 22, paddingRight: 26, paddingTop: 16, paddingBottom: 16, cornerRadius: 16, counterAxisAlignItems: "CENTER" });
    chip.fills = solid(C.white);
    chip.effects = [{ type: "DROP_SHADOW", color: { r: 0, g: 0, b: 0, a: 0.25 }, offset: { x: 0, y: 10 }, radius: 28, spread: 0, visible: true, blendMode: "NORMAL" }];
    const dot = figma.createEllipse(); dot.resize(16, 16); dot.fills = solid(C.coral); chip.appendChild(dot);
    text(chip, "Invoice", "Medium", 26, C.navy, { ls: -1 });
    text(chip, "Paid", "Bold", 26, C.coral, { ls: -1 });
    f.appendChild(chip); chip.x = s.chip.x; chip.y = s.chip.y;
  }
}
return { createdFrameIds: created, slots };
