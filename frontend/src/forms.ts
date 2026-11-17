export function textField(form: FormData, name: string): string {
  const value = form.get(name);
  return typeof value === "string" ? value : "";
}

export function honeypot(form: FormData): { website: string } {
  return { website: textField(form, "website") };
}
