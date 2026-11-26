import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, withObservation } from "../api/client";
import type { DashboardData, Window } from "../types/weather";
import { useWeatherSocket } from "../ws/useWeatherSocket";

export function dashboardQueryKey(cityA: string, cityB: string, window: Window) {
  return ["dashboard", cityA, cityB, window] as const;
}

export function useDashboardData(cityA: string | null, cityB: string | null, window: Window) {
  const queryClient = useQueryClient();
  const pair = cityA && cityB ? ([cityA, cityB] as [string, string]) : null;
  // With no pair selected the backend returns the stored defaults, so "/" is
  // never an empty screen. A half-selected pair still waits for the user.
  const enabled = pair !== null || (!cityA && !cityB);
  const key = dashboardQueryKey(cityA ?? "", cityB ?? "", window);

  const query = useQuery<DashboardData>({
    queryKey: key,
    queryFn: ({ signal }) => api.dashboardData(pair, window, { signal }),
    enabled,
    refetchInterval: 60_000,
    staleTime: 30_000,
    placeholderData: keepPreviousData,
  });

  const refresh = useMutation<DashboardData, Error, void>({
    mutationFn: () => {
      if (!pair) throw new Error("Selecciona dos ciudades para actualizar.");
      return api.refreshWeather(pair);
    },
    onSuccess: (payload) => {
      queryClient.setQueryData(key, payload);
      void queryClient.invalidateQueries({ queryKey: ["observations"] });
    },
  });

  const socketStatus = useWeatherSocket({
    cities: pair,
    enabled: pair !== null,
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
