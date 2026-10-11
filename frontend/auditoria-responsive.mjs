/**
 * Auditoría responsive: recorre las pantallas con un navegador real, en varios
 * anchos, y reporta lo que se rompe.
 *
 * Qué busca (todo medido en el navegador, no a ojo):
 *   1. Scroll horizontal de la página: el síntoma más claro de layout roto.
 *   2. Elementos que se salen del viewport.
 *   3. Texto cortado dentro de su caja (scrollWidth > clientWidth).
 *   4. Controles con área táctil menor a 44px en móvil.
 *
 * Uso: node auditoria-responsive.mjs [--rol alumno|admin] [--ancho 390]
 */
import { chromium } from '@playwright/test';

const BASE = 'http://localhost:5173';

const ANCHOS = [
  { w: 320, h: 720, nombre: 'movil-chico' },
  { w: 390, h: 844, nombre: 'movil' },
  { w: 768, h: 1024, nombre: 'tablet' },
  { w: 1280, h: 800, nombre: 'escritorio' },
];

const CUENTAS = {
  alumno: { usuario: 'estudiante1', clave: 'Alumno123' },
  admin: { usuario: 'admin', clave: 'Admin123' },
};

// OJO: tienen que ser las rutas REALES de App.tsx. Una ruta inventada cae al
// panel por defecto y se termina auditando la misma pantalla cuatro veces creyendo
// que se cubrieron cuatro (pasó con /admin/materias-comisiones y /alumno/notas).
const EXAMEN_ID = '33de2166-abee-491f-9955-b6abf3044009';

const RUTAS = {
  alumno: [
    '/alumno',
    '/alumno/mis-examenes',
    '/alumno/materias',
    '/alumno/perfil',
    '/requisitos',
    '/biometria',
    '/calibracion',
    '/sala-espera',
    '/pre-examen',
    '/cierre',
  ],
  admin: [
    '/admin',
    '/admin/estadisticas',
    '/admin/auditoria',
    '/admin/usuarios',
    '/admin/usuarios/nuevo',
    '/admin/examenes',
    `/admin/examenes/${EXAMEN_ID}`,
    `/admin/examenes/${EXAMEN_ID}/resultados`,
    '/admin/examenes/importar',
    '/admin/materias',
    '/admin/notas',
    '/admin/banco-preguntas',
    '/admin/configuracion',
    '/admin/lti',
    '/admin/perfil',
    '/admin/detection-test',
    '/proctor',
    '/admin/proctoring-sessions',
    '/admin/cola-revision',
  ],
};

/** Se corre DENTRO de la página: mide el layout tal como lo ve el usuario. */
function medir() {
  const doc = document.documentElement;
  const anchoV = doc.clientWidth;
  const problemas = [];

  if (doc.scrollWidth > anchoV + 1) {
    problemas.push({
      tipo: 'scroll-horizontal',
      detalle: `la página mide ${doc.scrollWidth}px en un viewport de ${anchoV}px`,
    });
  }

  const texto = (el) => (el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 45);
  const clase = (el) => (el.className || '').toString().slice(0, 45);

  for (const el of document.querySelectorAll('body *')) {
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    const estilo = getComputedStyle(el);
    if (estilo.visibility === 'hidden' || estilo.display === 'none') continue;
    // `sr-only` es texto para lectores de pantalla: mide 1px A PROPÓSITO y no se
    // ve. Medirlo como "texto cortado" es ruido.
    if (el.classList.contains('sr-only') || (r.width <= 1 && r.height <= 1)) continue;
    // Un panel deslizable CERRADO vive fuera de pantalla a propósito (el menú
    // lateral del staff en móvil). Si está entero a la izquierda del viewport no
    // es contenido que se escapa: es un cajón guardado.
    if (r.right <= 0) continue;
    if (el.closest('[aria-hidden="true"], [inert]')) continue;
    // Una tabla ancha DENTRO de un contenedor que scrollea a lo ancho es una
    // decisión válida, no un defecto: el contenido se alcanza arrastrando y la
    // página no se rompe. Solo se reporta lo que desborda sin red.
    let dentroDeScroll = false;
    for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
      const ox = getComputedStyle(p).overflowX;
      if (ox === 'auto' || ox === 'scroll') { dentroDeScroll = true; break; }
    }
    if (dentroDeScroll) continue;

    // Se sale del viewport (con 1px de tolerancia por redondeos).
    if (r.right > anchoV + 1 || r.left < -1) {
      // Solo el elemento más profundo: si no, se reporta él y todos sus padres.
      const hijoTambienDesborda = [...el.children].some((h) => {
        const rh = h.getBoundingClientRect();
        return rh.width > 0 && (rh.right > anchoV + 1 || rh.left < -1);
      });
      if (!hijoTambienDesborda) {
        problemas.push({
          tipo: 'fuera-de-pantalla',
          detalle: `${el.tagName} llega a ${Math.round(r.right)}px (viewport ${anchoV}px)`,
          clase: clase(el),
          texto: texto(el),
        });
      }
    }

    // Texto cortado dentro de su propia caja, sin que nadie lo muestre.
    if (
      el.scrollWidth > el.clientWidth + 2 &&
      el.clientWidth > 0 &&
      estilo.overflowX !== 'auto' &&
      estilo.overflowX !== 'scroll' &&
      estilo.textOverflow !== 'ellipsis' &&
      el.children.length === 0 &&
      texto(el).length > 0 &&
      // Mismo caso que arriba: el `::before` del área táctil infla el scrollWidth
      // sin que haya nada cortado.
      !(getComputedStyle(el, '::before').content !== 'none' &&
        parseFloat(getComputedStyle(el, '::before').top) < 0)
    ) {
      problemas.push({
        tipo: 'texto-cortado',
        detalle: `necesita ${el.scrollWidth}px y tiene ${el.clientWidth}px`,
        clase: clase(el),
        texto: texto(el),
      });
    }
  }

  // Botones y encabezados de columna partidos en dos renglones: decisión del
  // dueño, tienen que entrar en una línea.
  for (const el of document.querySelectorAll('button, th, [role="columnheader"]')) {
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    const t = texto(el);
    if (!t) continue;

    // Se cuentan los RENGLONES de verdad: cada nodo de texto se mide con un Range
    // y sus rects se agrupan por coordenada vertical. Medir "alto vs. altura de
    // línea" marcaba como partido cualquier botón cuadrado con un ícono adentro.
    // Se mide CADA nodo de texto por separado: lo que hay que detectar es UNA
    // frase partida al medio ("Exportar / Excel"), no un botón que a propósito
    // apila dos datos distintos (nombre arriba, correo abajo).
    const paseo = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    let nodo;
    while ((nodo = paseo.nextNode())) {
      const contenido = nodo.textContent.trim();
      if (!contenido) continue;
      // Los íconos son ligaduras tipográficas: un glifo, no una línea de texto.
      if (nodo.parentElement?.classList.contains('material-symbols-outlined')) continue;
      const rango = document.createRange();
      rango.selectNodeContents(nodo);
      const filas = new Set();
      for (const rect of rango.getClientRects()) {
        if (rect.width > 0) filas.add(Math.round(rect.top));
      }
      if (filas.size > 1) {
        problemas.push({
          tipo: 'dos-renglones',
          detalle: `"${contenido.slice(0, 30)}" se parte en ${filas.size} renglones`,
          clase: clase(el),
          texto: t,
        });
        break;
      }
    }
  }

  // Área táctil chica (solo tiene sentido en pantallas de dedo).
  if (anchoV <= 768) {
    for (const el of document.querySelectorAll('button, a[href], [role="button"], input, select')) {
      const r = el.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) continue;
        // Un `::before` con inset negativo ES el área táctil: el rect del elemento
      // se queda corto a propósito (un ícono chico incrustado en texto que no se
      // puede agrandar sin desacomodar el párrafo).
      const antes = getComputedStyle(el, '::before');
      const insetAmpliado = antes.content !== 'none' && parseFloat(antes.top) < 0;
      if (insetAmpliado) continue;
      // Un control dentro de un <label> se activa tocando el label entero: el área
      // real es la del label, no la del cuadradito.
      const etiqueta = el.closest('label');
      if (etiqueta && etiqueta.getBoundingClientRect().height >= 24) continue;
      // 24px es el mínimo de WCAG 2.2 AA (2.5.8 Target Size Minimum).
      if (r.height < 24) {
        problemas.push({
          tipo: 'tactil-chico',
          detalle: `${Math.round(r.width)}x${Math.round(r.height)}px`,
          clase: clase(el),
          texto: texto(el),
        });
      }
    }
  }

  return problemas;
}

async function entrar(page, rol) {
  const { usuario, clave } = CUENTAS[rol];
  await page.goto(`${BASE}/login`, { waitUntil: 'networkidle' });
  await page.locator("input[type='text']").first().fill(usuario);
  await page.locator("input[type='password']").first().fill(clave);
  await page.locator("button:has-text('Iniciar sesión')").click();
  await page.waitForTimeout(2500);
}

/** Saca una captura de UNA pantalla con el rol indicado: para mirar con ojos lo
 *  que la medición marcó como sospechoso. */
async function capturar(rol, ruta, ancho, salida) {
  const browser = await chromium.launch({
    channel: 'chrome',
    args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'],
  });
  const context = await browser.newContext({ permissions: ['camera'] });
  const page = await context.newPage();
  await entrar(page, rol);
  await page.setViewportSize({ width: Number(ancho), height: 900 });
  await page.goto(BASE + ruta, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2500);
  await page.screenshot({ path: salida, fullPage: true });
  console.log(`captura en ${salida} (${ruta} @${ancho}px como ${rol})`);
  await browser.close();
}

/** Imprime la cadena de padres de un elemento con sus anchos: para entender POR QUÉ
 *  algo quedó comprimido, en vez de adivinar leyendo clases. */
async function inspeccionar(rol, ruta, ancho, texto) {
  const browser = await chromium.launch({ channel: 'chrome' });
  const context = await browser.newContext({ permissions: ['camera'] });
  const page = await context.newPage();
  await entrar(page, rol);
  await page.setViewportSize({ width: Number(ancho), height: 900 });
  await page.goto(BASE + ruta, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2500);
  const cadena = await page.evaluate((txt) => {
    const el = [...document.querySelectorAll('*')].find(
      (e) => e.children.length === 0 && (e.textContent || '').trim() === txt,
    );
    if (!el) return 'no encontré ese texto';
    const salida = [];
    for (let p = el; p && p !== document.body; p = p.parentElement) {
      const r = p.getBoundingClientRect();
      const s = getComputedStyle(p);
      salida.push({
        tag: p.tagName,
        cls: (p.className || '').toString().slice(0, 60),
        ancho: Math.round(r.width),
        display: s.display,
        cols: s.gridTemplateColumns,
        flex: s.flex,
        minW: s.minWidth,
      });
    }
    return salida;
  }, texto);
  console.log(JSON.stringify(cadena, null, 2));
  await browser.close();
}

async function main() {
  const args = process.argv.slice(2);
  if (args.includes('--medir')) {
    const i = args.indexOf('--medir');
    await inspeccionar(args[i + 1], args[i + 2], args[i + 3], args[i + 4]);
    return;
  }
  if (args.includes('--captura')) {
    const i = args.indexOf('--captura');
    await capturar(args[i + 1], args[i + 2], args[i + 3] ?? 320, args[i + 4] ?? 'captura.png');
    return;
  }
  const rolPedido = args.includes('--rol') ? args[args.indexOf('--rol') + 1] : null;
  const roles = rolPedido ? [rolPedido] : ['alumno', 'admin'];

  // El chromium que trae Playwright acá no coincide con la versión que espera la
  // librería, y descargarlo no aporta nada a esta auditoría: se usa el Chrome del
  // sistema, que además es el navegador con el que la gente va a rendir de verdad.
  const browser = await chromium.launch({
    channel: 'chrome',
    args: [
      '--use-fake-device-for-media-stream',
      '--use-fake-ui-for-media-stream',
      '--autoplay-policy=no-user-gesture-required',
    ],
  });

  const hallazgos = [];

  for (const rol of roles) {
    const context = await browser.newContext({ permissions: ['camera'] });
    const page = await context.newPage();
    await entrar(page, rol);

    for (const ruta of RUTAS[rol]) {
      for (const { w, h, nombre } of ANCHOS) {
        await page.setViewportSize({ width: w, height: h });
        try {
          await page.goto(BASE + ruta, { waitUntil: 'networkidle', timeout: 20000 });
        } catch {
          // networkidle no llega en pantallas que sondean sin parar: alcanza con el DOM.
          await page.goto(BASE + ruta, { waitUntil: 'domcontentloaded', timeout: 20000 });
        }
        await page.waitForTimeout(900);

        const urlFinal = new URL(page.url()).pathname;
        if (urlFinal !== ruta && urlFinal === '/login') {
          hallazgos.push({ rol, ruta, ancho: nombre, tipo: 'sin-acceso', detalle: 'redirigió al login' });
          continue;
        }

        const problemas = await page.evaluate(medir);
        for (const p of problemas) hallazgos.push({ rol, ruta, ancho: nombre, ...p });
      }
    }
    await context.close();
  }

  await browser.close();

  // Reporte agrupado por gravedad y pantalla.
  const porTipo = {};
  for (const h of hallazgos) (porTipo[h.tipo] ??= []).push(h);

  console.log('\n===== RESUMEN =====');
  for (const [tipo, lista] of Object.entries(porTipo)) {
    console.log(`${tipo}: ${lista.length}`);
  }

  console.log('\n===== DETALLE =====');
  const orden = ['scroll-horizontal', 'fuera-de-pantalla', 'texto-cortado', 'dos-renglones', 'tactil-chico', 'sin-acceso'];
  for (const tipo of orden) {
    const lista = porTipo[tipo];
    if (!lista) continue;
    console.log(`\n--- ${tipo.toUpperCase()} (${lista.length}) ---`);
    const vistos = new Set();
    for (const h of lista) {
      const clave = `${h.ruta}|${h.ancho}|${h.clase}|${h.texto}`;
      if (vistos.has(clave)) continue;
      vistos.add(clave);
      console.log(
        `[${h.rol}] ${h.ruta} @${h.ancho}: ${h.detalle}` +
          (h.texto ? ` | "${h.texto}"` : '') +
          (h.clase ? ` | .${h.clase}` : ''),
      );
    }
  }
  console.log(`\nTOTAL: ${hallazgos.length} hallazgos`);
}

main().catch((e) => {
  console.error('la auditoría falló:', e.message);
  process.exit(1);
});
