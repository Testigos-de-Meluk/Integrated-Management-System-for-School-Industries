/** Calls of the login flow and the session (see backend /api/auth/). */
import { api, type SessionPayload } from "@/shared/api/http";

export type LoginChallenge = {
  step: "VERIFY_CODE" | "ENROLL_AUTHENTICATOR";
  pre_auth_token: string;
  expires_at: string;
};

export type Enrollment = {
  qr_code: string;
  secret: string;
  account_name: string;
  expires_at: string;
};

export const authApi = {
  login: (email: string, password: string) =>
    api.postAnonymous<LoginChallenge>("/auth/login/", { email, password }),
  startEnrollment: (preAuthToken: string) =>
    api.postAnonymous<Enrollment>("/auth/enrollment/", { pre_auth_token: preAuthToken }),
  confirmEnrollment: (preAuthToken: string, code: string) =>
    api.postAnonymous<SessionPayload>("/auth/enrollment/confirm/", {
      pre_auth_token: preAuthToken,
      code,
    }),
  verifyCode: (preAuthToken: string, code: string) =>
    api.postAnonymous<SessionPayload>("/auth/verify/", { pre_auth_token: preAuthToken, code }),
  logout: () => api.post<void>("/auth/logout/"),
  reportActivity: () => api.post<void>("/auth/activity/"),
};
