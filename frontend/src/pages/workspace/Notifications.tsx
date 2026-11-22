import { Link, useOutletContext } from "react-router";

import { useChannels } from "../../api/chat";
import { useMarkNotificationsRead, useNotifications } from "../../api/notifications";
import { channelTitle } from "../../chat/conversations";
import { describe, notificationHref, notificationText, sender } from "../../chat/notifications";
import { ErrorMessage } from "../../components/ui";
import { Avatar, PageHeader, Panel } from "../../components/workspace";
import type { WorkspaceContext } from "./Shell";

const when = new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" });

export function Notifications() {
  const { workspace, me } = useOutletContext<WorkspaceContext>();
  const slug = workspace.slug;
  const notifications = useNotifications(slug);
  const markRead = useMarkNotificationsRead(slug);
  const channels = useChannels(slug);
  const titles = new Map((channels.data ?? []).map((c) => [c.id, channelTitle(c, me.id)]));
  const pages = notifications.data?.pages ?? [];
  const items = pages.flatMap((page) => page.results);
  const unread = pages[0]?.unread ?? 0;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Notifications"
        intro="Mentions, messages to you and issues assigned to you. Reading the conversation or opening the notice clears it."
        action={
          unread > 0 ? (
            <button
              type="button"
              disabled={markRead.isPending}
              onClick={() => {
                markRead.mutate({ all: true });
              }}
              className="rounded-lg border border-border-strong px-3 py-1.5 text-sm font-semibold hover:bg-bg-subtle disabled:opacity-60"
            >
              Mark all read
            </button>
          ) : null
        }
      />
      {notifications.isPending && (
        <p role="status" className="text-text-muted">
          Loading
        </p>
      )}
      {notifications.isError && <ErrorMessage>Could not load notifications.</ErrorMessage>}
      {notifications.data && items.length === 0 && (
        <p className="text-text-muted">
          Nothing yet. Mentions, direct messages and issues assigned to you show up here.
        </p>
      )}
      {items.length > 0 && (
        <Panel className="settle">
          <ul aria-label="Notifications" className="divide-y divide-border">
            {items.map((item) => {
              const author = sender(item);
              const name = author ? author.display_name || author.username : "Deleted account";
              const where =
                (item.channel === null ? undefined : titles.get(item.channel)) ?? "a channel";
              return (
                <li key={item.id}>
                  <Link
                    to={notificationHref(slug, item)}
                    onClick={() => {
                      if (!item.read) markRead.mutate({ ids: [item.id] });
                    }}
                    className={`flex gap-3 px-5 py-4 hover:bg-bg-subtle ${item.read ? "" : "bg-accent-soft/40"}`}
                  >
                    <Avatar name={name} colorKey={author?.username ?? "?"} size="sm" />
                    <span className="min-w-0 flex-1">
                      <span className="flex flex-wrap items-baseline gap-x-2 text-sm">
                        <span className={item.read ? "" : "font-semibold"}>
                          {describe(item, where)}
                        </span>
                        <time
                          dateTime={item.created_at}
                          className="text-xs text-text-subtle tabular-nums"
                        >
                          {when.format(new Date(item.created_at))}
                        </time>
                      </span>
                      <span className="mt-0.5 block text-sm text-text-muted">
                        {notificationText(item)}
                      </span>
                    </span>
                    {!item.read && (
                      <span className="mt-1.5 size-2 shrink-0 rounded-full bg-unread">
                        <span className="sr-only">Unread</span>
                      </span>
                    )}
                  </Link>
                </li>
              );
            })}
          </ul>
          {notifications.hasNextPage && (
            <div className="flex justify-center border-t border-border p-3">
              <button
                type="button"
                disabled={notifications.isFetchingNextPage}
                onClick={() => void notifications.fetchNextPage()}
                className="rounded-lg border border-border-strong px-3 py-1 text-sm font-semibold hover:bg-bg-subtle disabled:opacity-60"
              >
                {notifications.isFetchingNextPage ? "Loading" : "Older"}
              </button>
            </div>
          )}
        </Panel>
      )}
    </div>
  );
}
