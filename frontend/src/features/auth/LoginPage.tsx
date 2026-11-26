import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { useForm } from "react-hook-form";
import { Link, Navigate, useLocation, useNavigate } from "react-router";
import { z } from "zod";

import { ApiError, type SessionPayload } from "@/shared/api/http";
import { clearNotice, startSession, useSession } from "@/shared/auth/session";
import { Button } from "@/shared/ui/Button";
import { TextField } from "@/shared/ui/TextField";

import { authApi, type Enrollment } from "./api";
import { CodeInput } from "./CodeInput";

type Step =
  | { kind: "credentials" }
  | { kind: "verify"; preAuthToken: string }
  | { kind: "enroll"; preAuthToken: string; enrollment: Enrollment };

const credentialsSchema = z.object({
  email: z.string().trim().min(1, "Ingrese su correo electrónico."),
  password: z.string().min(1, "Ingrese su contraseña."),
});
type Credentials = z.infer<typeof credentialsSchema>;

const CONNECTION_ERROR = "No fue posible conectar con el servidor. Intente de nuevo.";

function messageOf(error: unknown): string {
  return error instanceof ApiError ? error.message : CONNECTION_ERROR;
}

/** Two-step login (FR-01-01 … FR-01-03): password, then the authenticator code or its linking. */
export function LoginPage() {
  const session = useSession();
  const navigate = useNavigate();
  const location = useLocation();
  const redirectTo = (location.state as { from?: string } | null)?.from ?? "/";

  const [step, setStep] = useState<Step>({ kind: "credentials" });
  const [error, setError] = useState<string | null>(null);

  if (session.status === "authenticated") {
    return <Navigate to={redirectTo} replace />;
  }

  const finish = (payload: SessionPayload) => {
    startSession(payload.access_token, payload.user);
    navigate(redirectTo, { replace: true });
  };

  const backToCredentials = (message: string | null) => {
    setError(message);
    setStep({ kind: "credentials" });
  };

  return (
    <div className="flex min-h-screen bg-slate-50">
      <aside className="hidden w-[38%] flex-col justify-between bg-slate-800 p-10 text-white lg:flex">
        <div>
          <p className="text-xl font-bold text-red-400">Industrias Escolares</p>
          <p className="text-xs tracking-wide text-slate-300 uppercase">Sistema de gestión</p>
        </div>
        <div>
          <p className="text-4xl leading-tight font-semibold">Cada pedido, en buenas manos.</p>
          <p className="mt-4 text-slate-300">
            De la cotización al despacho, con información clara y decisiones trazables.
          </p>
        </div>
        <ol className="space-y-1 text-sm text-slate-300">
          <li>01 · Correo y contraseña</li>
          <li>02 · Código de su autenticador</li>
        </ol>
      </aside>

      <main className="flex flex-1 items-center justify-center p-6">
        <div className="w-full max-w-md">
          {session.notice && step.kind === "credentials" && (
            <Notice tone="warning">{session.notice}</Notice>
          )}
          {error && <Notice tone="error">{error}</Notice>}

          {step.kind === "credentials" && (
            <CredentialsStep
              onStart={() => {
                setError(null);
                clearNotice();
              }}
              onChallenge={async (challenge) => {
                if (challenge.step === "VERIFY_CODE") {
                  setStep({ kind: "verify", preAuthToken: challenge.pre_auth_token });
                  return;
                }
                const enrollment = await authApi.startEnrollment(challenge.pre_auth_token);
                setStep({ kind: "enroll", preAuthToken: challenge.pre_auth_token, enrollment });
              }}
              onError={setError}
            />
          )}

          {step.kind === "verify" && (
            <VerifyStep
              preAuthToken={step.preAuthToken}
              onSuccess={finish}
              onRestart={backToCredentials}
              onError={setError}
            />
          )}

          {step.kind === "enroll" && (
            <EnrollStep
              preAuthToken={step.preAuthToken}
              enrollment={step.enrollment}
              onRenew={(enrollment) => setStep({ ...step, enrollment })}
              onSuccess={finish}
              onRestart={backToCredentials}
              onError={setError}
            />
          )}

          <p className="mt-6 text-center text-sm">
            <Link to="/cotizar" className="text-red-700 hover:underline">
              ¿Necesita una cotización? Solicítela aquí, sin crear una cuenta
            </Link>
          </p>
          <p className="mt-4 text-center text-xs text-slate-500">
            Equipo compartido: cierre sesión al terminar. ¿Necesita ayuda? Contacte al administrador
            del sistema.
          </p>
        </div>
      </main>
    </div>
  );
}

// --- Step 1: email + password -------------------------------------------------------------------

function CredentialsStep({
  onStart,
  onChallenge,
  onError,
}: {
  onStart: () => void;
  onChallenge: (challenge: Awaited<ReturnType<typeof authApi.login>>) => Promise<void>;
  onError: (message: string) => void;
}) {
  const [showPassword, setShowPassword] = useState(false);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<Credentials>({ resolver: zodResolver(credentialsSchema) });

  const onSubmit = async (values: Credentials) => {
    onStart();
    try {
      await onChallenge(await authApi.login(values.email, values.password));
    } catch (error) {
      onError(messageOf(error));
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
      <StepHeader label="Acceso · Paso 1 de 2" title="Bienvenido de nuevo">
        Ingrese sus credenciales para continuar con la verificación.
      </StepHeader>
      <TextField
        label="Correo electrónico"
        type="email"
        autoComplete="username"
        autoFocus
        error={errors.email?.message}
        {...register("email")}
      />
      <TextField
        label="Contraseña"
        type={showPassword ? "text" : "password"}
        autoComplete="current-password"
        error={errors.password?.message}
        {...register("password")}
      />
      <label className="flex items-center gap-2 text-sm text-slate-600">
        <input type="checkbox" onChange={(e) => setShowPassword(e.target.checked)} />
        Mostrar contraseña
      </label>
      <Button type="submit" disabled={isSubmitting} className="w-full">
        {isSubmitting ? "Verificando…" : "Continuar"}
      </Button>
      <p className="rounded-md bg-slate-100 p-3 text-xs text-slate-600">
        Una sola sesión por usuario: un nuevo inicio cierra la sesión anterior. Cierre tras 15
        minutos de inactividad y bloqueo temporal después de 3 intentos fallidos.
      </p>
    </form>
  );
}

// --- Step 2: 6-digit code (every login except the first) ----------------------------------------

function VerifyStep({
  preAuthToken,
  onSuccess,
  onRestart,
  onError,
}: {
  preAuthToken: string;
  onSuccess: (payload: SessionPayload) => void;
  onRestart: (message: string | null) => void;
  onError: (message: string | null) => void;
}) {
  const [code, setCode] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (code.length !== 6) {
      onError("El código debe contener 6 dígitos.");
      return;
    }
    setSubmitting(true);
    onError(null);
    try {
      onSuccess(await authApi.verifyCode(preAuthToken, code));
    } catch (error) {
      setCode("");
      if (error instanceof ApiError && ["ACCOUNT_LOCKED", "PRE_AUTH_EXPIRED"].includes(error.code ?? "")) {
        onRestart(error.message);
      } else {
        onError(`${messageOf(error)}. Espere el siguiente código de su aplicación e intente de nuevo.`);
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-4">
      <StepHeader label="Acceso · Paso 2 de 2" title="Verifica que eres tú">
        Abre tu aplicación autenticadora e ingresa el código de seis dígitos de Industrias
        Escolares.
      </StepHeader>
      <CodeInput value={code} onChange={setCode} />
      <div className="flex gap-2">
        <Button type="submit" disabled={submitting} className="flex-1">
          {submitting ? "Verificando…" : "Verificar y entrar"}
        </Button>
        <Button variant="secondary" onClick={() => onRestart(null)}>
          Volver al acceso
        </Button>
      </div>
    </form>
  );
}

// --- Step 2 (first login): link the authenticator app -------------------------------------------

function EnrollStep({
  preAuthToken,
  enrollment,
  onRenew,
  onSuccess,
  onRestart,
  onError,
}: {
  preAuthToken: string;
  enrollment: Enrollment;
  onRenew: (enrollment: Enrollment) => void;
  onSuccess: (payload: SessionPayload) => void;
  onRestart: (message: string | null) => void;
  onError: (message: string | null) => void;
}) {
  const [code, setCode] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const secondsLeft = useSecondsUntil(enrollment.expires_at);
  const expired = secondsLeft <= 0;

  const renew = async () => {
    onError(null);
    setCode("");
    try {
      onRenew(await authApi.startEnrollment(preAuthToken));
    } catch (error) {
      onRestart(messageOf(error));
    }
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (code.length !== 6) {
      onError("El código debe contener 6 dígitos.");
      return;
    }
    setSubmitting(true);
    onError(null);
    try {
      onSuccess(await authApi.confirmEnrollment(preAuthToken, code));
    } catch (error) {
      setCode("");
      if (
        error instanceof ApiError &&
        ["ACCOUNT_LOCKED", "PRE_AUTH_EXPIRED", "ENROLLMENT_EXPIRED"].includes(error.code ?? "")
      ) {
        onRestart(error.message);
      } else {
        onError(messageOf(error));
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-4">
      <StepHeader label="Primer acceso · Configurar autenticador" title="Vincula tu autenticador">
        Solo necesitas realizar esta configuración en tu primer ingreso.
      </StepHeader>

      <ol className="space-y-1 text-sm text-slate-700">
        <li>1. Abre tu aplicación autenticadora y elige «Agregar cuenta».</li>
        <li>2. Escanea el código QR o escribe la clave.</li>
        <li>3. Ingresa los seis dígitos que muestra la aplicación.</li>
      </ol>

      <div className="flex flex-col items-center gap-3 rounded-lg border border-slate-200 bg-white p-4 sm:flex-row">
        <img
          src={enrollment.qr_code}
          alt="Código QR para vincular la aplicación autenticadora"
          className={`h-40 w-40 shrink-0 ${expired ? "opacity-20" : ""}`}
        />
        <div className="min-w-0 text-sm">
          <p className="font-medium">Clave para ingresarla manualmente</p>
          <p className="mt-1 font-mono break-all text-slate-800">
            {enrollment.secret.match(/.{1,4}/g)?.join(" ")}
          </p>
          <p className="mt-2 text-xs text-slate-500">Cuenta: {enrollment.account_name}</p>
          <p className={`mt-1 text-xs ${expired ? "text-red-700" : "text-slate-500"}`}>
            {expired
              ? "Código vencido"
              : `Vigencia: ${Math.floor(secondsLeft / 60)}:${String(secondsLeft % 60).padStart(2, "0")}`}
          </p>
        </div>
      </div>

      {expired ? (
        <>
          <Notice tone="error">
            El tiempo de vinculación ha expirado. Por favor, genere un nuevo código
          </Notice>
          <Button onClick={renew} className="w-full">
            Generar un nuevo código
          </Button>
        </>
      ) : (
        <>
          <CodeInput value={code} onChange={setCode} />
          <Button type="submit" disabled={submitting} className="w-full">
            {submitting ? "Vinculando…" : "Vincular autenticador"}
          </Button>
        </>
      )}
      <Button variant="secondary" onClick={() => onRestart(null)} className="w-full">
        Volver al acceso
      </Button>
    </form>
  );
}

// --- Helpers ------------------------------------------------------------------------------------

function useSecondsUntil(isoDate: string): number {
  const compute = () => Math.max(0, Math.ceil((new Date(isoDate).getTime() - Date.now()) / 1000));
  const [seconds, setSeconds] = useState(compute);
  useEffect(() => {
    setSeconds(compute());
    const timer = window.setInterval(() => setSeconds(compute()), 1000);
    return () => window.clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isoDate]);
  return seconds;
}

function StepHeader({ label, title, children }: { label: string; title: string; children: ReactNode }) {
  return (
    <header className="mb-2">
      <p className="text-xs font-medium tracking-wide text-red-700 uppercase">{label}</p>
      <h1 className="mt-1 text-2xl font-semibold text-slate-900">{title}</h1>
      <p className="mt-1 text-sm text-slate-600">{children}</p>
    </header>
  );
}

function Notice({ tone, children }: { tone: "warning" | "error"; children: ReactNode }) {
  const styles =
    tone === "warning" ? "bg-amber-50 text-amber-900" : "bg-red-50 text-red-800";
  return (
    <p role="alert" className={`mb-4 rounded-md p-3 text-sm ${styles}`}>
      {children}
    </p>
  );
}
