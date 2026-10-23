import { CircleAlert, CircleCheck, LoaderCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ru } from "@/lib/i18n/ru";
import type { components } from "@/lib/api/schema";

type Health = components["schemas"]["HealthResponse"];

type Props = {
  data?: Health;
  error?: Error | null;
  isLoading?: boolean;
};

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-6 text-sm">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-mono">{value}</dd>
    </div>
  );
}

// Чисто презентационный компонент: данные приходят снаружи, поэтому его просто тестировать.
export function HealthStatus({ data, error, isLoading }: Props) {
  const t = ru.health;

  if (isLoading) {
    return (
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <LoaderCircle className="size-4 animate-spin" aria-hidden />
            {t.loading}
          </CardTitle>
        </CardHeader>
      </Card>
    );
  }

  if (error || !data) {
    return (
      <Card className="w-full max-w-md border-destructive/50">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-destructive">
            <CircleAlert className="size-4" aria-hidden />
            {t.unavailable}
          </CardTitle>
          <CardDescription>{t.unavailableHint}</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const healthy = data.status === "ok";

  return (
    <Card className="w-full max-w-md">
      <CardHeader>
        <CardTitle className="flex items-center justify-between gap-2">
          <span>{t.title}</span>
          <Badge variant={healthy ? "secondary" : "destructive"} className="gap-1">
            {healthy ? (
              <CircleCheck className="size-3" aria-hidden />
            ) : (
              <CircleAlert className="size-3" aria-hidden />
            )}
            {healthy ? t.ok : t.degraded}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <dl className="space-y-2">
          <Row label={t.version} value={data.version} />
          <Row label={t.javac} value={data.javac ?? t.notFound} />
          <Row label={t.java} value={data.java ?? t.notFound} />
          <Row label={t.db} value={data.db === "ok" ? t.dbOk : t.dbError} />
        </dl>
        {data.problems && data.problems.length > 0 && (
          <ul className="list-disc space-y-1 pl-5 text-sm text-destructive">
            {data.problems.map((problem) => (
              <li key={problem}>{problem}</li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
