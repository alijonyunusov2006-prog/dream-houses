import { chromium } from '/opt/node22/lib/node_modules/playwright/index.mjs';
import fs from 'node:fs'; import path from 'node:path';
const dir = path.join(path.dirname(new URL(import.meta.url).pathname), process.argv[2] || 'stories');
const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1080, height: 1920 } });
for (const f of fs.readdirSync(dir).filter(f => f.endsWith('.html'))) {
  await p.goto('file://' + path.join(dir, f)); await p.waitForTimeout(300);
  await p.screenshot({ path: path.join(dir, f.replace('.html', '.jpg')), type: 'jpeg', quality: 90 });
}
await b.close();
