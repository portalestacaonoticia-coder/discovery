import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/hooks/useAuth";
import { consultaDiscovery, salvaDiscovery, type DiscoveryEdicao } from "@/lib/discovery";

// O sites.yaml só muda por commit (aqui ou no editor): pode ficar fresco por
// mais tempo que os dados do radar.
const FRESCOR = 5 * 60 * 1000;

export function useDiscoveryConfig() {
  const { session } = useAuth();
  return useQuery({
    queryKey: ["discovery", "config"],
    queryFn: () => consultaDiscovery(session!.access_token),
    enabled: !!session,
    staleTime: FRESCOR,
  });
}

export function useSalvarDiscovery() {
  const { session } = useAuth();
  const fila = useQueryClient();
  return useMutation({
    mutationFn: (edicao: DiscoveryEdicao) => salvaDiscovery(edicao, session!.access_token),
    // o commit muda o sha: recarrega para a próxima edição partir do arquivo novo
    onSettled: () => fila.invalidateQueries({ queryKey: ["discovery", "config"] }),
  });
}
