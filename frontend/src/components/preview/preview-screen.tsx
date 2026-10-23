"use client";

import { useQuery } from "@tanstack/react-query";
import { CircleAlert } from "lucide-react";
import { useMemo, useState } from "react";

import { FlowOutline } from "@/components/preview/flow-outline";
import { MethodList } from "@/components/preview/method-list";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { MOCK_MODE } from "@/lib/api/client";
import { flowQuery, structureQuery } from "@/lib/api/queries";
import { methodGroups } from "@/lib/graph/outline";
import { ru } from "@/lib/i18n/ru";

// Проект, на который смотрит экран предпросмотра. Выбор проекта появится вместе с рабочей областью (S4).
const PROJECT_ID = 1;

function LoadError({ error }: { error: Error }) {
  return (
    <Alert variant="destructive">
      <CircleAlert />
      <AlertTitle>{ru.preview.loadError}</AlertTitle>
      <AlertDescription>
        <p>{error.message}</p>
        <p>{ru.preview.loadErrorHint}</p>
      </AlertDescription>
    </Alert>
  );
}

export function PreviewScreen() {
  const [filter, setFilter] = useState("");
  const [chosen, setChosen] = useState<string | null>(null);
  const structure = useQuery(structureQuery(PROJECT_ID));

  const groups = useMemo(
    () => (structure.data ? methodGroups(structure.data, filter) : []),
    [structure.data, filter],
  );
  // По умолчанию открыт самый длинный метод с оценкой сложности: на нём видны циклы, условия и вызовы.
  const defaultId = useMemo(() => {
    const methods = structure.data?.nodes.filter((n) => n.method_id !== null) ?? [];
    const heavy = methods.filter((n) => n.complexity).sort((a, b) => b.lines - a.lines);
    return (heavy[0] ?? methods[0])?.method_id ?? null;
  }, [structure.data]);
  const selectedId = chosen ?? defaultId;
  const flow = useQuery(flowQuery(PROJECT_ID, selectedId));

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-4 p-6">
      <header className="flex items-start justify-between gap-4">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight">{ru.preview.title}</h1>
          <p className="text-sm text-muted-foreground">{ru.preview.subtitle}</p>
        </div>
        {MOCK_MODE && <Badge variant="secondary">{ru.preview.mockBadge}</Badge>}
      </header>

      <div className="grid min-h-0 flex-1 gap-4 md:grid-cols-[minmax(240px,320px)_1fr]">
        <Card className="min-h-0">
          <CardHeader className="gap-3">
            <CardTitle>{ru.preview.methods}</CardTitle>
            <Input
              value={filter}
              onChange={(event) => setFilter(event.target.value)}
              placeholder={ru.preview.filter}
              aria-label={ru.preview.filter}
            />
          </CardHeader>
          <CardContent className="min-h-0">
            {structure.isLoading && <Skeleton className="h-40 w-full" />}
            {structure.error && <LoadError error={structure.error} />}
            {structure.data && groups.length === 0 && (
              <p className="text-sm text-muted-foreground">{ru.preview.nothingFound}</p>
            )}
            {groups.length > 0 && (
              <ScrollArea className="h-[60vh] pr-3">
                <MethodList
                  groups={groups}
                  selectedId={selectedId}
                  onSelect={(method) => setChosen(method.method_id)}
                />
              </ScrollArea>
            )}
          </CardContent>
        </Card>

        <Card className="min-h-0">
          <CardHeader>
            <CardTitle>{ru.preview.flow}</CardTitle>
          </CardHeader>
          <CardContent>
            {selectedId === null && !structure.isLoading && (
              <p className="text-sm text-muted-foreground">{ru.preview.pickMethod}</p>
            )}
            {flow.isFetching && !flow.data && <Skeleton className="h-60 w-full" />}
            {flow.error && <LoadError error={flow.error} />}
            {flow.data && !flow.error && (
              <ScrollArea className="h-[60vh] pr-3">
                <FlowOutline flow={flow.data} />
              </ScrollArea>
            )}
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
