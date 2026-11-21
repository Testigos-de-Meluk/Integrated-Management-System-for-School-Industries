import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "danger" | "link";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-red-700 text-white hover:bg-red-800 disabled:bg-red-300",
  secondary:
    "border border-slate-300 bg-white text-slate-800 hover:bg-slate-50 disabled:text-slate-400",
  danger: "border border-red-300 bg-white text-red-700 hover:bg-red-50 disabled:text-red-300",
  link: "px-0 text-red-700 underline-offset-2 hover:underline disabled:text-slate-400",
};

export function Button({
  variant = "primary",
  className = "",
  type = "button",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      type={type}
      className={`inline-flex items-center justify-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed ${VARIANTS[variant]} ${className}`}
      {...props}
    />
  );
}
