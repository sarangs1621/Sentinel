"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { FieldError, Input, Label } from "@/components/ui/Input";
import { PageSpinner } from "@/components/ui/Spinner";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

const schema = z
  .object({
    full_name: z.string().max(255).optional().or(z.literal("")),
    email: z.string().email("Enter a valid email address."),
    password: z
      .string()
      .min(8, "Password must be at least 8 characters.")
      .max(72, "Password must be at most 72 characters.")
      .regex(/[A-Za-z]/, "Password must contain at least one letter.")
      .regex(/\d/, "Password must contain at least one digit."),
    confirmPassword: z.string(),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: "Passwords do not match.",
    path: ["confirmPassword"],
  });

type FormValues = z.infer<typeof schema>;

export default function RegisterPage() {
  const { user, isLoading, register: registerUser } = useAuth();
  const router = useRouter();
  const [formError, setFormError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  useEffect(() => {
    if (!isLoading && user) router.replace("/workspaces");
  }, [isLoading, user, router]);

  if (isLoading || user) return <PageSpinner />;

  const onSubmit = async (values: FormValues) => {
    setFormError(null);
    try {
      await registerUser({
        email: values.email,
        password: values.password,
        full_name: values.full_name || undefined,
      });
      router.replace("/workspaces");
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Registration failed. Please try again.");
    }
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 text-center">
          <h1 className="text-2xl font-bold text-slate-900">Sentinel</h1>
          <p className="mt-1 text-sm text-slate-500">Create your account</p>
        </div>
        <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
          <form className="space-y-4" onSubmit={handleSubmit(onSubmit)}>
            {formError && <Alert tone="error">{formError}</Alert>}
            <div>
              <Label htmlFor="full_name">Full name</Label>
              <Input id="full_name" type="text" autoComplete="name" {...register("full_name")} />
              <FieldError>{errors.full_name?.message}</FieldError>
            </div>
            <div>
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" autoComplete="email" {...register("email")} />
              <FieldError>{errors.email?.message}</FieldError>
            </div>
            <div>
              <Label htmlFor="password">Password</Label>
              <Input id="password" type="password" autoComplete="new-password" {...register("password")} />
              <FieldError>{errors.password?.message}</FieldError>
              <p className="mt-1 text-xs text-slate-500">At least 8 characters, with one letter and one digit.</p>
            </div>
            <div>
              <Label htmlFor="confirmPassword">Confirm password</Label>
              <Input
                id="confirmPassword"
                type="password"
                autoComplete="new-password"
                {...register("confirmPassword")}
              />
              <FieldError>{errors.confirmPassword?.message}</FieldError>
            </div>
            <Button type="submit" className="w-full" isLoading={isSubmitting}>
              Create account
            </Button>
          </form>
        </div>
        <p className="mt-4 text-center text-sm text-slate-500">
          Already have an account?{" "}
          <Link href="/login" className="font-medium text-blue-600 hover:text-blue-700">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
