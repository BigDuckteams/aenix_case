// Запуск dev-сервера в режиме моков: NEXT_PUBLIC_MOCK=1 без зависимости от оболочки (Windows/Linux).
// Использование: pnpm dev:mock [аргументы next dev]
import { spawn } from "node:child_process";

const child = spawn("pnpm", ["exec", "next", "dev", ...process.argv.slice(2)], {
  stdio: "inherit",
  shell: process.platform === "win32",
  env: { ...process.env, NEXT_PUBLIC_MOCK: "1" },
});
child.on("exit", (code) => process.exit(code ?? 0));
