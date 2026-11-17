import type { components } from "./api/schema";

export type Role = components["schemas"]["RoleEnum"];

// Mirrors backend/apps/core/roles.py so the screens only offer what the API will allow. The
// API still decides; a mismatch shows its error instead of doing the wrong thing.
const RANK: Record<Role, number> = { guest: 0, member: 1, admin: 2, owner: 3 };

export const ROLES: Role[] = ["owner", "admin", "member", "guest"];

export const ROLE_LABELS: Record<Role, string> = {
  owner: "Owner",
  admin: "Admin",
  member: "Member",
  guest: "Guest",
};

export function isAdmin(role: Role): boolean {
  return RANK[role] >= RANK.admin;
}

/** Roles this person may give to someone else. */
export function grantable(actor: Role): Role[] {
  if (!isAdmin(actor)) return [];
  return ROLES.filter((role) => RANK[role] <= RANK[actor]);
}

/** Roles this person may invite with: never owner. */
export function invitable(actor: Role): Role[] {
  return grantable(actor).filter((role) => role !== "owner");
}

/** Whether `actor` may change or remove someone with role `target`. */
export function canManage(actor: Role, target: Role): boolean {
  return isAdmin(actor) && RANK[actor] >= RANK[target];
}
