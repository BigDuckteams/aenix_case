import Link from "next/link";

import { HealthCard } from "@/components/health-card";
import { Button } from "@/components/ui/button";
import { ru } from "@/lib/i18n/ru";

// Временная главная страница: проверка связки frontend ↔ backend и вход в предпросмотр контракта (S1).
// Список проектов и импорт появятся на этапе S4 (задача S4.2).
export default function Home() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-8 p-8">
      <div className="space-y-2 text-center">
        <h1 className="text-3xl font-semibold tracking-tight">{ru.app.title}</h1>
        <p className="text-muted-foreground">{ru.app.subtitle}</p>
      </div>
      <HealthCard />
      <Button asChild variant="outline">
        <Link href="/preview">{ru.preview.open}</Link>
      </Button>
    </main>
  );
}
