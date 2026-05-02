import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "react-hot-toast";

import type { ListEmployeesParams } from "@/api/endpoints/employees";
import { employeesApi } from "@/api/endpoints/employees";
import { qk } from "@/api/queryKeys";
import type {
  EmployeeCreateRequest,
  EmployeeResponse,
  EmployeesPageResponse,
  EmployeeUpdateRequest,
  SetPasswordRequest,
} from "@/api/types";
import { getErrorMessage } from "@/lib/errorMessages";
import { log } from "@/lib/log";

export const useEmployeesQuery = (params: ListEmployeesParams = {}) =>
  useQuery<EmployeesPageResponse>({
    queryKey: qk.employees.list(params),
    queryFn: () => employeesApi.list(params),
  });

export const useEmployeeQuery = (id: number | undefined) =>
  useQuery<EmployeeResponse>({
    queryKey: id !== undefined ? qk.employees.detail(id) : ["employees", "detail", "skip"],
    queryFn: () => employeesApi.get(id!),
    enabled: id !== undefined,
  });

export const useCreateEmployee = () => {
  const queryClient = useQueryClient();
  return useMutation<EmployeeResponse, unknown, EmployeeCreateRequest>({
    mutationFn: (req) => employeesApi.create(req),
    onSuccess: (employee) => {
      log.info("[employees.create] success", { id: employee.id });
      queryClient.invalidateQueries({ queryKey: qk.employees._all });
      toast.success(`Сотрудник ${employee.full_name} создан`);
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });
};

export const useUpdateEmployee = (id: number) => {
  const queryClient = useQueryClient();
  return useMutation<EmployeeResponse, unknown, EmployeeUpdateRequest>({
    mutationFn: (patch) => employeesApi.update(id, patch),
    onSuccess: () => {
      log.info("[employees.update] success", { id });
      queryClient.invalidateQueries({ queryKey: qk.employees._all });
      toast.success("Изменения сохранены");
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });
};

export const useDeactivateEmployee = (id: number) => {
  const queryClient = useQueryClient();
  return useMutation<EmployeeResponse, unknown, void>({
    mutationFn: () => employeesApi.deactivate(id),
    onSuccess: () => {
      log.info("[employees.deactivate] success", { id });
      queryClient.invalidateQueries({ queryKey: qk.employees._all });
      toast.success("Сотрудник деактивирован");
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });
};

export const useActivateEmployee = (id: number) => {
  const queryClient = useQueryClient();
  return useMutation<EmployeeResponse, unknown, void>({
    mutationFn: () => employeesApi.activate(id),
    onSuccess: () => {
      log.info("[employees.activate] success", { id });
      queryClient.invalidateQueries({ queryKey: qk.employees._all });
      toast.success("Сотрудник активирован");
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });
};

export const useChangePassword = (id: number) =>
  useMutation<void, unknown, SetPasswordRequest>({
    mutationFn: (req) => employeesApi.setPassword(id, req),
    onSuccess: () => {
      log.info("[employees.password.changed]", { id });
      toast.success("Пароль обновлён");
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });
