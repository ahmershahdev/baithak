export function textField(form: FormData, name: string): string {
  const value = form.get(name);
  return typeof value === "string" ? value : "";
}

/** The honeypot value, sent with every anonymous form so the API can drop bots. */
export function honeypot(form: FormData): { website: string } {
  return { website: textField(form, "website") };
}
