import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, withObservation } from "../api/client";
import type { DashboardData, Window } from "../types/weather";
import { useWeatherSocket } from "../ws/useWeatherSocket";

export function dashboardQueryKey(cityA: string, cityB: string, window: Window) {
  return ["dashboard", cityA, cityB, window] as const;
}

export function useDashboardData(cityA: string | null, cityB: string | null, window: Window) {
  const queryClient = useQueryClient();
  const enabled = Boolean(cityA && cityB);
  const key = dashboardQueryKey(cityA ?? "", cityB ?? "", window);

  const query = useQuery<DashboardData>({
    queryKey: key,
    queryFn: ({ signal }) => api.dashboardData([cityA as string, cityB as string], window, { signal }),
    enabled,
    refetchInterval: 60_000,
    staleTime: 30_000,
    placeholderData: keepPreviousData,
  });

  const refresh = useMutation<DashboardData, Error, void>({
    mutationFn: () => api.refreshWeather([cityA as string, cityB as string]),
    onSuccess: (payload) => {
      queryClient.setQueryData(key, payload);
      void queryClient.invalidateQueries({ queryKey: ["observations"] });
    },
  });

  const socketStatus = useWeatherSocket({
    cities: enabled ? [cityA as string, cityB as string] : null,
    enabled,
    onSnapshot: (payload) => {
      queryClient.setQueryData<DashboardData>(key, payload);
    },
    onObservation: (observation) => {
      queryClient.setQueryData<DashboardData>(key, (current) =>
        current ? withObservation(current, observation) : current,
      );
      // The comparison updates instantly; the series and table refetch so the
      // chart point and paginated row appear without a reload.
      void queryClient.invalidateQueries({ queryKey: key });
      void queryClient.invalidateQueries({ queryKey: ["observations"] });
    },
  });

  return { query, refresh, socketStatus };
}
