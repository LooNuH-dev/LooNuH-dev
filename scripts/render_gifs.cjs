// Render the hero row GIFs from the jobs that `build_card.py --render DIR` writes.
// Each frame is one 100 ms tick; equal neighbours are encoded by ffmpeg as tiny frames.
// Usage: node scripts/render_gifs.cjs <render-dir> <out-dir>   (needs playwright + ffmpeg)
const { chromium } = require(process.env.PW || 'playwright');
const { execFileSync } = require('child_process');
const fs = require('fs'), os = require('os'), path = require('path');
const TICK = 0.1, SCALE = 2;
(async () => {
  const [dir, outDir] = process.argv.slice(2);
  const jobs = JSON.parse(fs.readFileSync(path.join(dir, 'jobs.json'), 'utf8'));
  const b = await chromium.launch(process.env.CH ? { executablePath: process.env.CH } : {});
  for (const [name, job] of Object.entries(jobs)) {
    const tmp = fs.mkdtempSync(path.join(os.tmpdir(), `${name}-`));
    const p = await b.newPage({ deviceScaleFactor: SCALE });
    await p.goto('file://' + path.resolve(dir, job.page));
    const strip = await p.$('.strip');
    const cache = new Map();
    for (let i = 0; i < job.frames.length; i++) {
      const js = job.frames[i];
      if (!cache.has(js)) { await p.evaluate(js); cache.set(js, await strip.screenshot()); }
      fs.writeFileSync(path.join(tmp, `f${String(i).padStart(4, '0')}.png`), cache.get(js));
    }
    await p.close();
    const out = path.join(outDir, `${name}.gif`);
    execFileSync('ffmpeg', ['-v', 'error', '-y', '-framerate', String(1 / TICK), '-i', path.join(tmp, 'f%04d.png'),
      '-filter_complex', 'split[a][b];[a]palettegen=max_colors=256:stats_mode=full[p];[b][p]paletteuse=dither=none',
      '-loop', '0', out]);
    console.log('wrote', out, `${job.frames.length} ticks`, fs.statSync(out).size >> 10, 'KB');
  }
  await b.close();
})();
