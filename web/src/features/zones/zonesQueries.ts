import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "react-hot-toast";

import { zonesApi } from "@/api/endpoints/zones";
import { qk } from "@/api/queryKeys";
import type { ZoneCreateRequest, ZoneResponse, ZoneUpdateRequest } from "@/api/types";
import { getErrorMessage } from "@/lib/errorMessages";
import { log } from "@/lib/log";

export const useZonesQuery = () =>
  useQuery<ZoneResponse[]>({
    queryKey: qk.zones.list(),
    queryFn: () => zonesApi.list(),
  });

export const useCreateZone = () => {
  const queryClient = useQueryClient();
  return useMutation<ZoneResponse, unknown, ZoneCreateRequest>({
    mutationFn: (req) => zonesApi.create(req),
    onSuccess: (zone) => {
      log.info("[zones.create] success", { id: zone.id });
      queryClient.invalidateQueries({ queryKey: qk.zones._all });
      toast.success(`Зона «${zone.name}» создана`);
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });
};

export const useUpdateZone = (id: number) => {
  const queryClient = useQueryClient();
  return useMutation<ZoneResponse, unknown, ZoneUpdateRequest>({
    mutationFn: (patch) => zonesApi.update(id, patch),
    onSuccess: () => {
      log.info("[zones.update] success", { id });
      queryClient.invalidateQueries({ queryKey: qk.zones._all });
      toast.success("Изменения сохранены");
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });
};

export const useDeleteZone = () => {
  const queryClient = useQueryClient();
  return useMutation<void, unknown, number>({
    mutationFn: (id) => zonesApi.delete(id),
    onSuccess: () => {
      log.info("[zones.delete] success");
      queryClient.invalidateQueries({ queryKey: qk.zones._all });
      queryClient.invalidateQueries({ queryKey: qk.calibration._all });
      toast.success("Зона удалена");
    },
    onError: (error) => {
      log.warn("[zones.delete] failed");
      toast.error(getErrorMessage(error));
    },
  });
};
