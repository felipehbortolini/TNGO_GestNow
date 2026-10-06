/* ==========================================================================
   icons.js | Ícones SVG em linha (grade 24x24, traço 2px, cor = currentColor)
   Nenhuma cor própria: o ícone herda a cor do texto do elemento pai.

   Uso em HTML:  <i data-icon="upload"></i>   (GI.icons.hydrate() substitui)
   Uso em JS:    GI.icons.svg("upload", { size: 18 })
   ========================================================================== */
(function (GI) {
  "use strict";

  var DOC = '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6"/>';
  var CAL = '<rect x="3" y="4" width="18" height="17" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>';
  var CLIP = '<rect x="8" y="2" width="8" height="4" rx="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>';

  var PATHS = {
    menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
    x: '<path d="M18 6 6 18M6 6l12 12"/>',
    chevronDown: '<path d="m6 9 6 6 6-6"/>',
    chevronUp: '<path d="m18 15-6-6-6 6"/>',
    chevronLeft: '<path d="m15 18-6-6 6-6"/>',
    chevronRight: '<path d="m9 18 6-6-6-6"/>',
    chevronsLeft: '<path d="m11 17-5-5 5-5M18 17l-5-5 5-5"/>',
    chevronsRight: '<path d="m13 17 5-5-5-5M6 17l5-5-5-5"/>',
    sort: '<path d="m7 15 5 5 5-5M7 9l5-5 5 5"/>',
    home: '<path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>',
    actions: '<path d="m9 11 3 3 8-8"/><path d="M20 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>',
    dashboard: '<rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/>',
    fileText: DOC + '<path d="M8 13h8M8 17h6"/>',
    filePlus: DOC + '<path d="M12 12v6M9 15h6"/>',
    filePdf: DOC + '<path d="M9 18v-5h1.8a1.6 1.6 0 0 1 0 3.2H9"/>',
    fileSheet: DOC + '<path d="M8 12h8v6H8zM12 12v6M8 15h8"/>',
    fileSearch: '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h5"/><path d="M14 3v6h6v3"/><circle cx="16" cy="17" r="3"/><path d="m18.2 19.2 2.8 2.8"/>',
    curve: '<path d="M3 3v18h18"/><path d="M6 17c4.5 0 5-10 13-11"/>',
    trendingUp: '<path d="m3 17 6-6 4 4 8-8"/><path d="M14 7h7v7"/>',
    gauge: '<path d="M4.9 18a9 9 0 1 1 14.2 0"/><path d="m12 14 3.5-3.5"/><circle cx="12" cy="14" r="1.5"/>',
    calendarRange: CAL + '<path d="M7 14h5M12 17h5"/>',
    calendarDays: CAL + '<path d="M8 14h.01M12 14h.01M16 14h.01M8 18h.01M12 18h.01"/>',
    calendar: CAL,
    alertTriangle: '<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/>',
    matrix: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M3 15h18M9 3v18M15 3v18"/>',
    pieChart: '<path d="M21 12A9 9 0 1 1 12 3v9z"/><path d="M15 3.5A9 9 0 0 1 20.5 9H15z"/>',
    barChart: '<path d="M3 3v18h18"/><path d="M8 17v-5M13 17V8M18 17v-3"/>',
    shieldCheck: '<path d="M12 3 20 6v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><path d="m9 12 2 2 4-4"/>',
    octagonAlert: '<path d="M7.9 2h8.2L22 7.9v8.2L16.1 22H7.9L2 16.1V7.9z"/><path d="M12 8v4M12 16h.01"/>',
    clipboardCheck: CLIP + '<path d="m9 14 2 2 4-4"/>',
    clipboardList: CLIP + '<path d="M9 11h6M9 15h6M9 19h3"/>',
    upload: '<path d="M12 15V3"/><path d="m7 8 5-5 5 5"/><path d="M20 15v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-4"/>',
    uploadCloud: '<path d="M12 13v8"/><path d="m8 17 4-4 4 4"/><path d="M20 16.6A5 5 0 0 0 18 7h-1.3A8 8 0 1 0 4 15.3"/>',
    download: '<path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M20 15v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-4"/>',
    image: '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-5-5L5 21"/>',
    filter: '<path d="M3 4h18l-7 8.5V19l-4 2v-8.5z"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    edit: '<path d="M17 3a2.8 2.8 0 0 1 4 4L7.5 20.5 2 22l1.5-5.5z"/><path d="m15 5 4 4"/>',
    trash: '<path d="M3 6h18"/><path d="M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2"/><path d="m19 6-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6M14 11v6"/>',
    eye: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    eyeOff: '<path d="M9.9 4.2A10 10 0 0 1 12 4c6.5 0 10 8 10 8a17 17 0 0 1-2.2 3.2"/><path d="M6.6 6.6C3.9 8.4 2 12 2 12s3.5 8 10 8a9.7 9.7 0 0 0 5.4-1.6"/><path d="M14.1 14.1a3 3 0 1 1-4.2-4.2"/><path d="m2 2 20 20"/>',
    more: '<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
    user: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    users: '<circle cx="9" cy="8" r="4"/><path d="M2 21a7 7 0 0 1 14 0"/><path d="M16 3.1a4 4 0 0 1 0 7.8"/><path d="M22 21a7 7 0 0 0-5-6.7"/>',
    logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5"/><path d="M21 12H9"/>',
    refresh: '<path d="M21 12a9 9 0 1 1-2.6-6.4L21 8"/><path d="M21 3v5h-5"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>',
    check: '<path d="M20 6 9 17l-5-5"/>',
    checkCircle: '<circle cx="12" cy="12" r="10"/><path d="m8 12 3 3 5-6"/>',
    alertCircle: '<circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    arrowUp: '<path d="M12 19V5"/><path d="m5 12 7-7 7 7"/>',
    arrowDown: '<path d="M12 5v14"/><path d="m19 12-7 7-7-7"/>',
    arrowRight: '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
    mail: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
    send: '<path d="M22 2 11 13"/><path d="M22 2 15 22l-4-9-9-4z"/>',
    columns: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18M15 3v18"/>',
    kanban: '<rect x="3" y="3" width="5" height="12" rx="1"/><rect x="10" y="3" width="5" height="18" rx="1"/><rect x="17" y="3" width="4" height="8" rx="1"/>',
    list: '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
    history: '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l3 2"/>',
    sliders: '<path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6"/>',
    target: '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
    flag: '<path d="M4 22V4"/><path d="M4 4h13l-2 4 2 4H4"/>',
    printer: '<path d="M6 9V2h12v7"/><rect x="6" y="14" width="12" height="8"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/>',
    lock: '<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
    building: '<path d="M3 21h18"/><path d="M5 21V7l7-4 7 4v14"/><path d="M9 10h1M14 10h1M9 14h1M14 14h1M10 21v-3h4v3"/>',
    palette: '<path d="M12 22a10 10 0 1 1 10-10c0 2-1.5 3-3 3h-2a2 2 0 0 0-1.5 3.3A2 2 0 0 1 12 22z"/><circle cx="7.5" cy="11" r="1"/><circle cx="11" cy="7" r="1"/><circle cx="16" cy="8.5" r="1"/>',
    money: '<rect x="2" y="6" width="20" height="12" rx="2"/><circle cx="12" cy="12" r="2.5"/><path d="M6 12h.01M18 12h.01"/>',
    listTree: '<path d="M21 6H9M21 12h-8M21 18h-8"/><path d="M4 4v4a2 2 0 0 0 2 2h3M4 8v8a2 2 0 0 0 2 2h3"/>',
    coins: '<circle cx="8" cy="8" r="6"/><path d="M18.1 10.4A6 6 0 1 1 10.4 18.1"/><path d="M7 6h1v4"/>',
    waterfall: '<path d="M3 3v18h18"/><path d="M7 17V9M11 9V5M15 13V5M19 17v-4"/>',
    fileContract: DOC + '<path d="M8 17c1.5-2 2.5-2 3 0s1.5 2 3 0"/>',
    listChecks: '<path d="m3 6 2 2 4-4M3 14l2 2 4-4"/><path d="M13 6h8M13 14h8M13 20h8"/>',
    swap: '<path d="M4 8h14"/><path d="m14 4 4 4-4 4"/><path d="M20 16H6"/><path d="m10 20-4-4 4-4"/>',
    lightbulb: '<path d="M9 18h6M10 22h4"/><path d="M12 2a7 7 0 0 0-4 12.7c.6.5 1 1.2 1 2V17h6v-.3c0-.8.4-1.5 1-2A7 7 0 0 0 12 2z"/>',
    landmark: '<path d="M3 21h18M5 21v-9M9.5 21v-9M14.5 21v-9M19 21v-9"/><path d="M2 10 12 3l10 7z"/>',
    hardHat: '<path d="M2 18a1 1 0 0 0 1 1h18a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1H3a1 1 0 0 0-1 1z"/><path d="M10 15V6a2 2 0 0 1 4 0v9"/><path d="M4 15v-3a8 8 0 0 1 6-7.7M20 15v-3a8 8 0 0 0-6-7.7"/>',
    truck: '<path d="M1 5h13v11H1z"/><path d="M14 9h4l3 3.5V16h-7"/><circle cx="5.5" cy="18" r="2"/><circle cx="17.5" cy="18" r="2"/>',
    cart: '<circle cx="9" cy="20" r="1.5"/><circle cx="18" cy="20" r="1.5"/><path d="M2 3h3l2.7 12.4a1 1 0 0 0 1 .8h9.6a1 1 0 0 0 1-.8L21 7H6"/>',
    gavel: '<path d="m14 13-7.5 7.5a2.1 2.1 0 0 1-3-3L11 10"/><path d="m16 16 6-6M8 8l6-6M9 7l8 8M21 11l-8-8"/>',
    star: '<path d="m12 2 3.1 6.3 6.9 1-5 4.9 1.2 6.8L12 17.8 5.8 21l1.2-6.8-5-4.9 6.9-1z"/>',
    calendarClock: '<path d="M21 10V6a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h6"/><path d="M16 2v4M8 2v4M3 10h18"/><circle cx="17.5" cy="17.5" r="4.5"/><path d="M17.5 15.5v2l1.5 1"/>',
    pyramid: '<path d="M12 3 2 21h20z"/><path d="M8.5 9h7M5.5 15h13"/>',
    package: '<path d="M21 8 12 3 3 8v8l9 5 9-5z"/><path d="M3.3 7 12 12l8.7-5M12 22V12M7.5 5.5l9 5"/>',
    grip: '<circle cx="9" cy="6" r="1"/><circle cx="15" cy="6" r="1"/><circle cx="9" cy="12" r="1"/><circle cx="15" cy="12" r="1"/><circle cx="9" cy="18" r="1"/><circle cx="15" cy="18" r="1"/>'
  };

  function svg(name, opts) {
    opts = opts || {};
    var body = PATHS[name];
    if (!body) {
      if (window.console) console.warn("[icons] ícone inexistente: " + name);
      body = PATHS.info;
    }
    var n = opts.size || 20; /* tamanho padrão; o CSS do componente pode sobrescrever */
    var size = ' width="' + n + '" height="' + n + '"';
    var cls = opts.className ? ' class="' + opts.className + '"' : "";
    var label = opts.label
      ? ' role="img" aria-label="' + opts.label + '"'
      : ' aria-hidden="true" focusable="false"';
    return '<svg viewBox="0 0 24 24"' + size + cls + label +
      ' fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
      body + "</svg>";
  }

  /* Substitui <i data-icon="nome"> pelo SVG correspondente */
  function hydrate(root) {
    var nodes = (root || document).querySelectorAll("i[data-icon]");
    Array.prototype.forEach.call(nodes, function (el) {
      var tmp = document.createElement("span");
      tmp.innerHTML = svg(el.getAttribute("data-icon"), {
        size: el.getAttribute("data-size"),
        className: el.className || "",
        label: el.getAttribute("aria-label")
      });
      el.parentNode.replaceChild(tmp.firstChild, el);
    });
  }

  GI.icons = { svg: svg, hydrate: hydrate, names: Object.keys(PATHS) };
})(window.GI = window.GI || {});
