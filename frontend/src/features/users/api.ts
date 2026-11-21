/** Data layer of user accounts (/api/users/). */
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type Paginated } from "@/shared/api/http";
import type { Role } from "@/shared/auth/session";

export type AccountStatus = "ACTIVE" | "INACTIVE";

export const STATUS_LABELS: Record<AccountStatus, string> = { ACTIVE: "Activo", INACTIVE: "Inactivo" };

export type UserAccount = {
  id: string;
  full_name: string;
  email: string;
  job_title: string;
  role: Role;
  status: AccountStatus;
  last_access_at: string | null;
  is_locked: boolean;
  locked_until: string | null;
};

export type UserFilters = {
  name?: string;
  email?: string;
  job_title?: string;
  role?: Role | "";
  status?: AccountStatus | "";
};

export type PasswordInput = { password?: string; generate_password: boolean };
export type CreateUserInput = {
  full_name: string;
  email: string;
  job_title: string;
  role: Role;
} & PasswordInput;
export type UpdateUserInput = { full_name: string; job_title: string; role: Role };

const keys = {
  all: ["users"] as const,
  list: (filters: UserFilters, page: number) => [...keys.all, "list", { ...filters, page }] as const,
};

export function useUsers(filters: UserFilters, page: number, pageSize = 20) {
  return useQuery({
    queryKey: keys.list(filters, page),
    queryFn: () => api.get<Paginated<UserAccount>>("/users/", { ...filters, page, page_size: pageSize }),
    placeholderData: keepPreviousData,
  });
}

function useUserMutation<TInput>(request: (input: TInput) => Promise<UserAccount>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: request,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.all }),
  });
}

export const useCreateUser = () =>
  useUserMutation((input: CreateUserInput) => api.post<UserAccount>("/users/", input));

export const useUpdateUser = () =>
  useUserMutation(({ id, ...input }: UpdateUserInput & { id: string }) =>
    api.patch<UserAccount>(`/users/${id}/`, input),
  );

export const useChangePassword = () =>
  useUserMutation(({ id, ...input }: PasswordInput & { id: string }) =>
    api.post<UserAccount>(`/users/${id}/password/`, input),
  );

export const useUserAction = () =>
  useUserMutation(({ id, action }: { id: string; action: "activate" | "deactivate" | "unlock" }) =>
    api.post<UserAccount>(`/users/${id}/${action}/`),
  );
