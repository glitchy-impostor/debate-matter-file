// Copies the repo-root /data tree into frontend/public/data so Vite serves
// it as a static asset. Runs automatically before `dev` and `build` via
// the predev/prebuild npm scripts.
import { cpSync, existsSync, mkdirSync, rmSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const src = resolve(here, "..", "..", "data");
const dest = resolve(here, "..", "public", "data");

if (!existsSync(src)) {
  console.warn(`[copy-data] no data/ at ${src} — skipping`);
  process.exit(0);
}

if (existsSync(dest)) rmSync(dest, { recursive: true, force: true });
mkdirSync(dest, { recursive: true });
cpSync(src, dest, { recursive: true });
console.log(`[copy-data] ${src} -> ${dest}`);
