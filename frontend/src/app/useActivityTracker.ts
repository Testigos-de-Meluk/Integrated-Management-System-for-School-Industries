import { useEffect } from "react";

import { authApi } from "@/features/auth/api";
import { endSession } from "@/shared/auth/session";

const INACTIVITY_LIMIT_MS = 15 * 60 * 1000; // FR-01-06
const REPORT_EVERY_MS = 60 * 1000;
const CHECK_EVERY_MS = 15 * 1000;

/**
 * FR-01-06: activity means clicks or scrolling (keys are counted too, so typing a long form does
 * not log the user out). At most once a minute the backend is told about it, which keeps the
 * server-side session alive. After 15 minutes without activity the tab returns to the login
 * screen; the backend has expired the session by then anyway.
 */
export function useActivityTracker(): void {
  useEffect(() => {
    let lastActivity = Date.now();
    let lastReport = Date.now();

    const onActivity = () => {
      lastActivity = Date.now();
      if (lastActivity - lastReport >= REPORT_EVERY_MS) {
        lastReport = lastActivity;
        authApi.reportActivity().catch(() => {
          // A failed report is handled by the HTTP client (expired session → login screen).
        });
      }
    };

    const options = { passive: true, capture: true } as const;
    window.addEventListener("click", onActivity, options);
    window.addEventListener("scroll", onActivity, options);
    window.addEventListener("keydown", onActivity, options);

    const timer = window.setInterval(() => {
      if (Date.now() - lastActivity >= INACTIVITY_LIMIT_MS) {
        endSession("Su sesión ha caducado por inactividad");
      }
    }, CHECK_EVERY_MS);

    return () => {
      window.removeEventListener("click", onActivity, options);
      window.removeEventListener("scroll", onActivity, options);
      window.removeEventListener("keydown", onActivity, options);
      window.clearInterval(timer);
    };
  }, []);
}
