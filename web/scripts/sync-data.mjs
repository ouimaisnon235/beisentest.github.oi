// 把仓库根部的 data/ 同步到 web/public/data/，让 dev 和 build 都能直接取到。
// 放在 predev / prebuild 里自动执行，使用者不需要手动操作。
import { cpSync, existsSync, mkdirSync, statSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const src = resolve(here, "../../data");
const dest = resolve(here, "../public/data");

if (!existsSync(src)) {
  console.error(`[sync-data] 找不到 ${src}`);
  console.error("[sync-data] 请先运行解析器: python parser/parse_pdf.py --input <pdf> --out data/questions.json");
  process.exit(1);
}
if (!existsSync(resolve(src, "questions.json"))) {
  console.error("[sync-data] data/questions.json 不存在，请先运行解析器。");
  process.exit(1);
}

mkdirSync(dirname(dest), { recursive: true });
cpSync(src, dest, { recursive: true, force: true });
const n = statSync(resolve(dest, "questions.json")).size;
console.log(`[sync-data] 已同步 data/ -> web/public/data/ (questions.json ${(n / 1e6).toFixed(1)} MB)`);
