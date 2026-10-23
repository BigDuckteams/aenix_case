import type { Metadata } from "next";

import { PreviewScreen } from "@/components/preview/preview-screen";
import { ru } from "@/lib/i18n/ru";

export const metadata: Metadata = { title: `${ru.preview.title} — ${ru.app.title}` };

// Экран S1.2: показывает, что контракт API достаточен для списка методов и блок-схемы.
// Работает на моках (NEXT_PUBLIC_MOCK=1) и на настоящем backend, когда будут готовы эндпоинты S3.
export default function PreviewPage() {
  return <PreviewScreen />;
}
