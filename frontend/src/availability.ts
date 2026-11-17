import { useEffect, useState } from "react";

import { api } from "./api/client";

export interface Availability {
  available: boolean;
  message: string;
}

/**
 * Whether an email or handle is free, checked 400 ms after typing stops. The answer is kept
 * with the value it was for, so a slow reply never labels what the person has typed since.
 */
export function useAvailability(field: "email" | "username", value: string): Availability | null {
  const [answer, setAnswer] = useState<{ value: string; result: Availability } | null>(null);
  const wanted = value.trim().toLowerCase();

  useEffect(() => {
    if (!wanted || (field === "email" && !wanted.includes("@"))) return;
    let current = true;
    const timer = window.setTimeout(() => {
      void api
        .POST("/api/v1/auth/availability/", { body: { [field]: wanted } })
        .then(({ data }) => {
          const result = data?.[field];
          if (current && result) setAnswer({ value: wanted, result });
        });
    }, 400);
    return () => {
      current = false;
      window.clearTimeout(timer);
    };
  }, [field, wanted]);

  return answer?.value === wanted ? answer.result : null;
}
