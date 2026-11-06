// Turn dist/teto.html into src/card/teto.gif: one screenshot per sprite frame,
// glued by ffmpeg with the original GIF's frame lengths.
// Usage: node scripts/render_teto.cjs <teto.html> <out.gif>   (needs playwright + ffmpeg)
const { chromium } = require(process.env.PW || 'playwright');
const { execFileSync } = require('child_process');
const fs = require('fs'), os = require('os'), path = require('path');
const FRAMES = [2, 1, 1, 1, 1, 1], TICK = 0.1, SCALE = 2;
(async () => {
  const [src, out] = process.argv.slice(2);
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'teto-'));
  const b = await chromium.launch(process.env.CH ? { executablePath: process.env.CH } : {});
  const p = await b.newPage({ deviceScaleFactor: SCALE });
  await p.goto('file://' + path.resolve(src));
  const strip = await p.$('.strip');
  // One image per 100 ms tick, so a frame that lasts two ticks is written twice.
  let n = 0;
  for (let i = 0; i < FRAMES.length; i++) {
    await p.evaluate(i => document.querySelector('.teto-img').style.backgroundPosition = `${-210 * i}px 0`, i);
    const shot = await strip.screenshot();
    for (let k = 0; k < FRAMES[i]; k++) fs.writeFileSync(path.join(tmp, `f${String(n++).padStart(2, '0')}.png`), shot);
  }
  await b.close();
  execFileSync('ffmpeg', ['-v', 'error', '-y', '-framerate', String(1 / TICK), '-i', path.join(tmp, 'f%02d.png'),
    '-filter_complex', 'split[a][b];[a]palettegen=max_colors=256:stats_mode=full[p];[b][p]paletteuse=dither=none',
    '-loop', '0', out]);
  console.log('wrote', out, fs.statSync(out).size >> 10, 'KB');
})();
