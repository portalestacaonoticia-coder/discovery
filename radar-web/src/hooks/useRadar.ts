import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/hooks/useAuth";
import {
  consultaRadar,
  mudaStatusPautaRadar,
  salvaConfigRadar,
  type RadarConfig,
  type RadarDoSite,
  type StatusTriagem,
} from "@/lib/radar";

// Os dados mudam no ritmo dos crons do radar (30 min), não do clique:
// staleTime curto o bastante para acompanhar, longo o bastante para não
// martelar a função serverless.
const FRESCOR = 60 * 1000;

export function useRadarSites() {
  const { session } = useAuth();
  return useQuery({
    queryKey: ["radar", "sites"],
    queryFn: () => consultaRadar<{ sites: string[] }>("", session!.access_token),
    enabled: !!session,
    staleTime: FRESCOR,
    select: (r) => r.sites,
  });
}

export function useRadarDoSite(site: string | null) {
  const { session } = useAuth();
  return useQuery({
    queryKey: ["radar", "site", site],
    queryFn: () => consultaRadar<RadarDoSite>(`?site=${encodeURIComponent(site!)}`, session!.access_token),
    enabled: !!session && !!site,
    staleTime: FRESCOR,
  });
}

export function useTriarPauta(site: string | null) {
  const { session } = useAuth();
  const fila = useQueryClient();
  return useMutation({
    mutationFn: ({ pautaId, status }: { pautaId: number; status: StatusTriagem }) =>
      mudaStatusPautaRadar(pautaId, status, session!.access_token),
    onSuccess: () => fila.invalidateQueries({ queryKey: ["radar", "site", site] }),
  });
}

export function useSalvarConfig(site: string | null) {
  const { session } = useAuth();
  const fila = useQueryClient();
  return useMutation({
    mutationFn: (config: RadarConfig) => salvaConfigRadar(site!, config, session!.access_token),
    onSuccess: () => fila.invalidateQueries({ queryKey: ["radar", "site", site] }),
  });
}
