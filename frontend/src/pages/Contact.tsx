import { useMutation } from "@tanstack/react-query";
import { useRef, useState, type SubmitEvent } from "react";

import { api, readErrors, type ApiErrors } from "../api/client";
import { useCaptcha } from "../captcha";
import { CaptchaBox, CaptchaNotice } from "../components/CaptchaBox";
import {
  AuthLayout,
  Button,
  ErrorMessage,
  Field,
  Honeypot,
  inputClass,
  Notice,
} from "../components/ui";
import { SITE_URL, SUPPORT_EMAIL } from "../contact";
import { honeypot, textField } from "../forms";

export function Contact() {
  const captchaBox = useRef<HTMLDivElement>(null);
  const captcha = useCaptcha("contact", captchaBox);
  const [errors, setErrors] = useState<ApiErrors>({ fields: {} });
  const [sent, setSent] = useState(false);

  const send = useMutation({
    mutationFn: async (body: { name: string; email: string; message: string; website: string }) =>
      api.POST("/api/v1/contact/", { body: { ...body, ...(await captcha.tokens()) } }),
    onSuccess: ({ response, error }) => {
      if (response.status === 202) {
        setSent(true);
        return;
      }
      const problems = readErrors(error);
      setErrors(problems);
      if (problems.captcha) captcha.challenge();
    },
    onError: () => {
      setErrors({ detail: "Could not reach Baithak. Try again.", fields: {} });
    },
  });

  function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setErrors({ fields: {} });
    send.mutate({
      name: textField(form, "name"),
      email: textField(form, "email"),
      message: textField(form, "message"),
      ...honeypot(form),
    });
  }

  const intro = (
    <>
      Questions, ideas or trouble signing in: write here, or email{" "}
      <a className="font-semibold text-accent-text underline" href={`mailto:${SUPPORT_EMAIL}`}>
        {SUPPORT_EMAIL}
      </a>
      .
    </>
  );

  const trail = [{ label: "Baithak", to: "/" }, { label: "Contact" }];

  if (sent) {
    return (
      <AuthLayout title="Thank you" intro={intro} trail={trail}>
        <Notice>
          Your message is with us. We reply by email, usually within two working days.
        </Notice>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title="Talk to us" intro={intro} trail={trail}>
      <form onSubmit={submit} className="relative flex flex-col gap-5" noValidate>
        {errors.detail && <ErrorMessage>{errors.detail}</ErrorMessage>}
        <div className="grid gap-5 sm:grid-cols-2">
          <Field
            label="Your name"
            name="name"
            autoComplete="name"
            placeholder="Amna Khan"
            maxLength={80}
            required
            errors={errors.fields.name}
          />
          <Field
            label="Email"
            name="email"
            type="email"
            inputMode="email"
            autoComplete="email"
            placeholder="you@company.com"
            required
            errors={errors.fields.email}
          />
        </div>
        <div className="flex flex-col gap-2">
          <label htmlFor="contact-message" className="text-sm font-semibold">
            Message
          </label>
          <textarea
            id="contact-message"
            name="message"
            rows={6}
            minLength={10}
            maxLength={5000}
            required
            placeholder="How can we help?"
            aria-invalid={errors.fields.message ? true : undefined}
            aria-describedby={errors.fields.message ? "contact-message-error" : undefined}
            className={`${inputClass} h-auto py-3`}
          />
          {errors.fields.message && (
            <p id="contact-message-error" className="text-sm font-medium text-danger">
              {errors.fields.message.join(" ")}
            </p>
          )}
        </div>
        <Honeypot />
        <CaptchaBox
          box={captchaBox}
          shown={captcha.shown}
          challenged={captcha.challenged}
          solved={captcha.solved}
          failed={captcha.failed}
        />
        <Button type="submit" busy={send.isPending} busyLabel="Sending">
          Send message
        </Button>
        {captcha.enabled && <CaptchaNotice />}
        <p className="text-sm text-text-subtle">
          Baithak is made by{" "}
          <a className="underline hover:text-text" href={SITE_URL} target="_blank" rel="noreferrer">
            ahmershah.dev
          </a>
          .
        </p>
      </form>
    </AuthLayout>
  );
}
