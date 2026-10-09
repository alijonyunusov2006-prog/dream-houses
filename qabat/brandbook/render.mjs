// HTML → PDF через Chromium (как build_pdf_chromium.py из навыка personal-brandbook; шрифты встроены в HTML)
import { chromium } from '/opt/node22/lib/node_modules/playwright/index.mjs';
import path from 'node:path';
const dir = path.dirname(new URL(import.meta.url).pathname);
const b = await chromium.launch();
const p = await b.newPage();
await p.goto('file://' + path.join(dir, 'brandbook.html'), { waitUntil: 'networkidle' });
await p.addStyleTag({ content: '@page{size:A4;margin:0}*{-webkit-print-color-adjust:exact;print-color-adjust:exact}.page{page-break-after:always}.page:last-child{page-break-after:auto}' });
await p.pdf({ path: path.join(dir, process.argv[2] || 'Qabat-brandbook.pdf'), format: 'A4', printBackground: true, preferCSSPageSize: true });
await b.close();
console.log('PDF готов');
