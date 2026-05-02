import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "react-hot-toast";

import { calibrationApi } from "@/api/endpoints/calibration";
import { qk } from "@/api/queryKeys";
import type { FingerprintResponse } from "@/api/types";
import { getErrorMessage } from "@/lib/errorMessages";
import { log } from "@/lib/log";

export const useCalibrationPointsQuery = (zoneId?: number) =>
  useQuery<FingerprintResponse[]>({
    queryKey: qk.calibration.list(zoneId),
    queryFn: () => calibrationApi.list(zoneId),
  });

export const useDeleteCalibrationPoint = () => {
  const queryClient = useQueryClient();
  return useMutation<void, unknown, number>({
    mutationFn: (id) => calibrationApi.delete(id),
    onSuccess: () => {
      log.info("[calibration.delete]");
      queryClient.invalidateQueries({ queryKey: qk.calibration._all });
      toast.success("Точка удалена");
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });
};
