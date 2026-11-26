import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { api } from "../api/client";
import type { PaginatedObservations } from "../types/weather";

export interface ObservationsParams {
  page: number;
  pageSize: number;
  city?: string;
}

export function observationsQueryKey(params: ObservationsParams) {
  return ["observations", params.page, params.pageSize, params.city ?? ""] as const;
}

export function useObservations(params: ObservationsParams, enabled = true) {
  return useQuery<PaginatedObservations>({
    queryKey: observationsQueryKey(params),
    queryFn: ({ signal }) =>
      api.listObservations(
        { page: params.page, pageSize: params.pageSize, city: params.city },
        signal,
      ),
    enabled,
    placeholderData: keepPreviousData,
    staleTime: 15_000,
  });
}
