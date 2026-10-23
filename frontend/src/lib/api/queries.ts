import { queryOptions } from "@tanstack/react-query";

import { api } from "./client";

export const healthQuery = queryOptions({
  queryKey: ["health"],
  queryFn: async () => {
    const { data, error } = await api.GET("/api/health");
    if (error || !data) {
      throw new Error(error?.error?.message ?? "Backend недоступен");
    }
    return data;
  },
  retry: false,
  refetchInterval: 15_000,
});
