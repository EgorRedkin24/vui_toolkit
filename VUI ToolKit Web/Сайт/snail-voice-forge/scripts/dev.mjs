/**
 * Локальный запуск VUI ToolKit: бэкенд (FastAPI, порт 8000) + фронтенд (vite).
 * Все CLI-аргументы (например --host, --port) передаются в vite dev.
 *
 * Python для бэкенда ищется так:
 *   1. переменная окружения VUI_PYTHON
 *   2. py -3.10
 *   3. python из PATH
 */
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";
import http from "node:http";

const frontendRoot = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const backendRoot = path.resolve(frontendRoot, "..", "vui-toolkit-backend");
const apiPort = process.env.VUI_PORT || "8000";
const apiUrl = `http://localhost:${apiPort}`;

const viteArgs = process.argv.slice(2);

function run(cmd, args, options = {}) {
  return new Promise((resolve, reject) => {
    const p = spawn(cmd, args, { ...options, stdio: ["ignore", "pipe", "pipe"] });
    let out = "";
    p.stdout.on("data", (d) => (out += d));
    p.stderr.on("data", (d) => (out += d));
    p.on("error", reject);
    p.on("close", (code) => resolve({ code, out }));
  });
}

async function findPython() {
  if (process.env.VUI_PYTHON) return process.env.VUI_PYTHON;
  const candidates = [["py", ["-3.10"]], ["python", []]];
  for (const [cmd, args] of candidates) {
    try {
      const { code } = await run(cmd, [...args, "-c", "import fastapi, uvicorn"]);
      if (code === 0) return cmd === "py" ? "py" : "python";
    } catch {
      /* пробуем следующего кандидата */
    }
  }
  console.error("[vui] Не найден Python с fastapi/uvicorn.\n" +
    "       Установите зависимости: pip install -r ../vui-toolkit-backend/requirements.txt\n" +
    "       или задайте путь через переменную окружения VUI_PYTHON.");
  process.exit(1);
}

function waitForApi(timeoutMs = 60000) {
  return new Promise((resolve, reject) => {
    const started = Date.now();
    const tick = () => {
      const req = http.get(`${apiUrl}/api/health`, (res) => {
        res.resume();
        resolve();
      });
      req.on("error", () => {
        if (Date.now() - started > timeoutMs) reject(new Error("API не ответил за 60 с"));
        else setTimeout(tick, 500);
      });
    };
    tick();
  });
}

const children = [];
function shutdown(code = 0) {
  for (const child of children) {
    try {
      child.kill();
    } catch {
      /* уже завершён */
    }
  }
  process.exit(code);
}
process.on("SIGINT", () => shutdown(0));
process.on("SIGTERM", () => shutdown(0));

const python = await findPython();
const pyArgs = python === "py" ? ["-3.10", "run.py"] : ["run.py"];
console.log(`[vui] Запускаю бэкенд: ${python} run.py (порт ${apiPort})`);
const backend = spawn(python, pyArgs, {
  cwd: backendRoot,
  stdio: "inherit",
  env: { ...process.env, VUI_PORT: apiPort, VUI_HOST: process.env.VUI_HOST || "127.0.0.1" },
});
children.push(backend);
backend.on("exit", (code) => {
  console.error(`[vui] Бэкенд завершился (код ${code}) — останавливаю фронтенд.`);
  shutdown(code ?? 1);
});

try {
  await waitForApi();
  console.log(`[vui] API готов: ${apiUrl}`);
} catch (e) {
  console.error(`[vui] ${e.message}`);
  shutdown(1);
}

console.log(`[vui] Запускаю фронтенд: vite dev ${viteArgs.join(" ")}`.trim());
const viteBin = path.join(frontendRoot, "node_modules", "vite", "bin", "vite.js");
const vite = spawn(process.execPath, [viteBin, "dev", ...viteArgs],
  { cwd: frontendRoot, stdio: "inherit" });
children.push(vite);
vite.on("exit", (code) => shutdown(code ?? 0));
