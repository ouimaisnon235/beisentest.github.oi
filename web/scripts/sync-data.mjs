// 把题库数据同步到 web/public/data/，让 dev / build / 部署都能直接取到。
// 挂在 predev / prebuild 上自动执行，使用者不需要手动操作。
//
// 数据的唯一来源是仓库根部的 data/（解析器的输出）。这里向上逐级搜索，
// 因此无论从仓库根目录还是从 web/ 触发构建都能找到。
import { cpSync, existsSync, mkdirSync, statSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const dest = resolve(here, "../public/data");

// web/scripts -> web -> 仓库根 -> 再上一级（应对被额外嵌套的情况）
const candidates = [
  resolve(here, "../../data"),
  resolve(here, "../data"),
  resolve(here, "../../../data"),
];

const src = candidates.find((d) => existsSync(resolve(d, "questions.json")));

if (!src) {
  console.error("[sync-data] 找不到题库数据 data/questions.json。");
  console.error("[sync-data] 已搜索以下位置：");
  for (const d of candidates) console.error(`[sync-data]   - ${d}`);
  console.error("");
  console.error("[sync-data] 如果这是在本地：先运行解析器");
  console.error("[sync-data]   python parser/parse_pdf.py --input raw/<你的PDF> --out data/questions.json");
  console.error("");
  console.error("[sync-data] 如果这是在 Vercel / CI 上：题库数据在仓库根部的 data/，");
  console.error("[sync-data] 但当前构建看不到它。请把 Vercel 项目的 Root Directory 设回");
  console.error("[sync-data] 仓库根目录（默认的 ./），仓库根部的 vercel.json 会接管构建；");
  console.error("[sync-data] 或者在项目设置里打开 \"Include source files outside of the");
  console.error("[sync-data] Root Directory in the Build Step\"。");
  process.exit(1);
}

mkdirSync(dirname(dest), { recursive: true });
cpSync(src, dest, { recursive: true, force: true });
const bytes = statSync(resolve(dest, "questions.json")).size;
console.log(`[sync-data] ${src} -> ${dest} (questions.json ${(bytes / 1e6).toFixed(1)} MB)`);
