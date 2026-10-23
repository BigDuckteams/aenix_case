"use client";

import { useQuery } from "@tanstack/react-query";

import { HealthStatus } from "@/components/health-status";
import { healthQuery } from "@/lib/api/queries";

export function HealthCard() {
  const { data, error, isLoading } = useQuery(healthQuery);
  return <HealthStatus data={data} error={error} isLoading={isLoading} />;
}
