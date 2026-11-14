// Проверка сайта в настоящем браузере (необязательный шаг).
// Открывает страницу на ширине 375, 768, 1280 и 1440 px, листает её до конца,
// ловит ошибки консоли, упавшие запросы и элементы, которые вылезают за правый край,
// и сохраняет скриншоты в папку proverka-brauzer рядом со страницей.
//
// Нужно: Node.js 18+ и пакет playwright (npm i -D playwright). Браузер берётся установленный
// Chrome, если его нет, то Chromium из playwright (npx playwright install chromium).
// Скрипт ничего не скачивает сам, открывает только указанную страницу и то, что она грузит.
//
// Запуск: node scripts/proverka_v_brauzere.mjs путь/к/index.html   (или https://адрес)
// Код выхода: 0 всё чисто, 1 есть замечания.

import { chromium } from 'playwright';
import { existsSync, mkdirSync } from 'node:fs';
import { resolve, dirname, join } from 'node:path';
import { pathToFileURL } from 'node:url';

const target = process.argv[2];
if (!target) {
  console.log('Использование: node scripts/proverka_v_brauzere.mjs путь/к/index.html');
  process.exit(2);
}
const isUrl = /^https?:\/\//.test(target);
const url = isUrl ? target : pathToFileURL(resolve(target)).href;
const outDir = isUrl ? resolve('proverka-brauzer') : join(dirname(resolve(target)), 'proverka-brauzer');
mkdirSync(outDir, { recursive: true });

const sizes = [
  { name: '375', width: 375, height: 812, mobile: true },
  { name: '768', width: 768, height: 1024, mobile: true },
  { name: '1280', width: 1280, height: 800 },
  { name: '1440', width: 1440, height: 900 },
];

let browser;
try {
  browser = await chromium.launch({ channel: 'chrome' });
} catch {
  browser = await chromium.launch();
}

let problems = 0;
for (const s of sizes) {
  const ctx = await browser.newContext({ viewport: { width: s.width, height: s.height }, isMobile: !!s.mobile, hasTouch: !!s.mobile, deviceScaleFactor: s.mobile ? 2 : 1 });
  const page = await ctx.newPage();
  const errors = [];
  page.on('console', m => { if (m.type() === 'error') errors.push('консоль: ' + m.text()); });
  page.on('pageerror', e => errors.push('скрипт: ' + e.message));
  page.on('requestfailed', r => errors.push('не загрузилось: ' + r.url()));
  await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
  const height = await page.evaluate(() => document.documentElement.scrollHeight);
  for (let y = 0; y < height; y += 400) {
    await page.evaluate(v => window.scrollTo(0, v), y);
    await page.waitForTimeout(60);
  }
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(800);
  const wide = await page.evaluate(() => {
    const w = document.documentElement.clientWidth;
    return [...document.querySelectorAll('body *')]
      .filter(e => { const r = e.getBoundingClientRect(); const st = getComputedStyle(e); return r.width > 0 && r.right > w + 1 && st.position !== 'fixed' && !e.closest('[aria-hidden="true"]'); })
      .slice(0, 5)
      .map(e => `${e.tagName.toLowerCase()}${e.className && typeof e.className === 'string' ? '.' + e.className.trim().split(/\s+/).join('.') : ''}`);
  });
  const scroll = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  const small = s.mobile ? await page.evaluate(() => [...document.querySelectorAll('a,button')]
      .filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && (r.height < 40 || r.width < 40) && getComputedStyle(e).display !== 'inline'; })
      .slice(0, 5).map(e => (e.innerText || e.getAttribute('aria-label') || e.tagName).trim().slice(0, 30))) : [];
  await page.screenshot({ path: join(outDir, `${s.name}.png`), fullPage: true });

  const notes = [...errors];
  if (scroll) notes.push('есть горизонтальная прокрутка');
  if (wide.length) notes.push('за правым краем: ' + wide.join(', '));
  if (small.length) notes.push('мелкие кнопки или ссылки (меньше 40 px): ' + small.join(' | '));
  problems += notes.length;
  console.log(`${s.name} px: ${notes.length ? notes.join('; ') : 'чисто'}`);
  await ctx.close();
}
await browser.close();
console.log(`Скриншоты: ${outDir}`);
console.log(problems ? `Итог: замечаний ${problems}` : 'Итог: всё чисто');
process.exit(problems ? 1 : 0);
