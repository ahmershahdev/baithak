import { useState, type SubmitEvent } from "react";
import { Link, useOutletContext, useSearchParams } from "react-router";

import { useChannels } from "../../api/chat";
import {
  useFileSearch,
  useIssueSearch,
  useMessageSearch,
  type FileHit,
  type IssueHit,
  type MessageHit,
  type SearchKind,
  type SearchParams,
} from "../../api/search";
import { useMembers } from "../../api/workspaces";
import { channelTitle } from "../../chat/conversations";
import { formatSize } from "../../chat/files";
import { highlight, resultHref } from "../../chat/search";
import { preview } from "../../chat/notifications";
import { STATUS_LABELS } from "../../issues";
import { Select } from "../../components/Select";
import { ErrorMessage } from "../../components/ui";
import { Avatar, PageHeader, Panel } from "../../components/workspace";
import type { WorkspaceContext } from "./Shell";

const when = new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" });

const TAB_LABELS: Record<SearchKind, string> = {
  messages: "Messages",
  files: "Files",
  issues: "Issues",
};

const inputClass =
  "h-10 rounded-lg border border-border-strong bg-bg px-3 text-sm outline-none focus-visible:border-focus-ring focus-visible:ring-4 focus-visible:ring-focus-ring/20";

function Highlighted({ text, terms }: { text: string; terms: string[] }) {
  return (
    <>
      {highlight(text, terms).map((part, index) =>
        part.hit ? (
          <mark key={index} className="rounded bg-mention px-0.5 text-text">
            {part.text}
          </mark>
        ) : (
          part.text
        ),
      )}
    </>
  );
}

function readParams(search: URLSearchParams): SearchParams {
  const channel = Number(search.get("channel"));
  return {
    q: search.get("q") ?? "",
    ...(Number.isInteger(channel) && channel > 0 ? { channel } : {}),
    ...(search.get("author") ? { author: search.get("author") ?? "" } : {}),
    ...(search.get("after") ? { after: search.get("after") ?? "" } : {}),
    ...(search.get("before") ? { before: search.get("before") ?? "" } : {}),
  };
}

export function Search() {
  const { workspace, me } = useOutletContext<WorkspaceContext>();
  const slug = workspace.slug;
  const [search, setSearch] = useSearchParams();
  const params = readParams(search);
  const canSeeIssues = workspace.role !== "guest";
  const tabs: SearchKind[] = canSeeIssues ? ["messages", "files", "issues"] : ["messages", "files"];
  const asked = search.get("kind");
  const kind: SearchKind = tabs.find((tab) => tab === asked) ?? "messages";
  const [draft, setDraft] = useState(params.q);
  const channels = useChannels(slug);
  const members = useMembers(slug);
  const titles = new Map((channels.data ?? []).map((c) => [c.id, channelTitle(c, me.id)]));

  function update(changes: Record<string, string | null>) {
    const next = new URLSearchParams(search);
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    setSearch(next);
  }

  function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    update({ q: draft.trim() || null });
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Search"
        intro={
          canSeeIssues
            ? "Messages and files in the channels and conversations you can read, and issues."
            : "Messages and files in the channels and conversations you can read."
        }
      />
      <form role="search" onSubmit={submit} className="flex flex-col gap-3">
        <div className="flex gap-2">
          <label htmlFor="search-words" className="sr-only">
            Search words
          </label>
          <input
            id="search-words"
            type="search"
            value={draft}
            onChange={(event) => {
              setDraft(event.target.value);
            }}
            placeholder="Words to find"
            className={`${inputClass} h-12 flex-1 text-base`}
          />
          <button
            type="submit"
            className="btn-lamp h-12 rounded-xl bg-accent px-5 font-semibold text-on-accent hover:bg-accent-hover"
          >
            Search
          </button>
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <Select
            aria-label="In channel"
            value={params.channel ? String(params.channel) : ""}
            onChange={(value) => {
              update({ channel: value || null });
            }}
            options={[
              { value: "", label: "Any channel" },
              ...(channels.data ?? []).map((c) => ({
                value: String(c.id),
                label: titles.get(c.id) ?? c.name,
              })),
            ]}
          />
          <Select
            aria-label="From person"
            value={params.author ?? ""}
            onChange={(value) => {
              update({ author: value || null });
            }}
            options={[
              { value: "", label: "Anyone" },
              ...(members.data ?? []).map((m) => ({
                value: m.username,
                label: m.display_name || m.username,
              })),
            ]}
          />
          <label className="flex flex-col gap-1 text-xs font-semibold text-text-muted">
            From day
            <input
              type="date"
              value={params.after ?? ""}
              onChange={(event) => {
                update({ after: event.target.value || null });
              }}
              className={inputClass}
            />
          </label>
          <label className="flex flex-col gap-1 text-xs font-semibold text-text-muted">
            To day
            <input
              type="date"
              value={params.before ?? ""}
              onChange={(event) => {
                update({ before: event.target.value || null });
              }}
              className={inputClass}
            />
          </label>
        </div>
      </form>

      <div role="tablist" aria-label="What to find" className="flex gap-1">
        {tabs.map((tab) => (
          <button
            key={tab}
            type="button"
            role="tab"
            aria-selected={kind === tab}
            onClick={() => {
              update({ kind: tab === "messages" ? null : tab });
            }}
            className="rounded-lg px-3 py-1.5 text-sm font-semibold text-text-muted hover:bg-surface aria-selected:bg-surface aria-selected:text-text aria-selected:shadow-sm"
          >
            {TAB_LABELS[tab]}
          </button>
        ))}
      </div>

      {!params.q ? (
        <p className="text-text-muted">Type a few words and press Enter.</p>
      ) : kind === "messages" ? (
        <MessageResults slug={slug} params={params} titles={titles} />
      ) : kind === "files" ? (
        <FileResults slug={slug} params={params} titles={titles} />
      ) : (
        <IssueResults slug={slug} params={params} />
      )}
    </div>
  );
}

function MoreButton({
  results,
}: {
  results: { hasNextPage: boolean; isFetchingNextPage: boolean; fetchNextPage: () => unknown };
}) {
  if (!results.hasNextPage) return null;
  return (
    <div className="flex justify-center border-t border-border p-3">
      <button
        type="button"
        disabled={results.isFetchingNextPage}
        onClick={() => void results.fetchNextPage()}
        className="rounded-lg border border-border-strong px-3 py-1 text-sm font-semibold hover:bg-bg-subtle disabled:opacity-60"
      >
        {results.isFetchingNextPage ? "Loading" : "More results"}
      </button>
    </div>
  );
}

/** What to show instead of results while searching, after a failure or when nothing matched. */
function resultState(pending: boolean, failed: boolean, count: number, terms: string[]) {
  if (pending)
    return (
      <p role="status" className="text-text-muted">
        Searching
      </p>
    );
  if (failed) return <ErrorMessage>Search did not work. Try again.</ErrorMessage>;
  if (count === 0) return <Empty terms={terms} />;
  return null;
}

function Empty({ terms }: { terms: string[] }) {
  return (
    <p className="text-text-muted">
      {terms.length === 0
        ? "Search words need at least three letters, and very common words like “the” are skipped."
        : "Nothing found."}
    </p>
  );
}

function MessageResults({
  slug,
  params,
  titles,
}: {
  slug: string;
  params: SearchParams;
  titles: Map<number, string>;
}) {
  const results = useMessageSearch(slug, params);
  const pages = results.data?.pages ?? [];
  const hits: MessageHit[] = pages.flatMap((page) => page.results);
  const terms = pages[0]?.terms ?? [];

  const shown = resultState(results.isPending, results.isError, hits.length, terms);
  if (shown) return shown;
  return (
    <Panel className="settle">
      <ul aria-label="Results" className="divide-y divide-border">
        {hits.map((hit) => {
          const author = hit.message.author;
          const name = author
            ? author.display_name || author.username
            : hit.message.sender_name || "Deleted account";
          return (
            <li key={hit.message.id}>
              <Link
                to={resultHref(slug, hit.channel, hit.message.parent_seq)}
                className="flex gap-3 px-5 py-4 hover:bg-bg-subtle"
              >
                <Avatar name={name} colorKey={author?.username ?? "?"} size="sm" />
                <span className="min-w-0 flex-1">
                  <span className="flex flex-wrap items-baseline gap-x-2 text-sm">
                    <span className="font-semibold">{name}</span>
                    <span className="text-text-subtle">
                      in {titles.get(hit.channel) ?? "a channel"}
                      {hit.message.parent_seq !== null && ", in a thread"}
                    </span>
                    <time dateTime={hit.message.created_at} className="text-xs text-text-subtle">
                      {when.format(new Date(hit.message.created_at))}
                    </time>
                  </span>
                  <span className="mt-0.5 block break-words whitespace-pre-wrap">
                    <Highlighted text={hit.message.body} terms={terms} />
                  </span>
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
      <MoreButton results={results} />
    </Panel>
  );
}

function FileResults({
  slug,
  params,
  titles,
}: {
  slug: string;
  params: SearchParams;
  titles: Map<number, string>;
}) {
  const results = useFileSearch(slug, params);
  const pages = results.data?.pages ?? [];
  const hits: FileHit[] = pages.flatMap((page) => page.results);
  const terms = pages[0]?.terms ?? [];

  const shown = resultState(results.isPending, results.isError, hits.length, terms);
  if (shown) return shown;
  return (
    <Panel className="settle">
      <ul aria-label="Results" className="divide-y divide-border">
        {hits.map((hit) => (
          <li key={hit.file.id} className="flex flex-wrap items-center gap-3 px-5 py-4">
            <span className="min-w-0 flex-1">
              <a
                href={hit.file.url}
                download={hit.file.name}
                className="block truncate font-semibold hover:underline"
              >
                <Highlighted text={hit.file.name} terms={terms} />
              </a>
              <span className="text-sm text-text-subtle">
                {formatSize(hit.file.size)} in {titles.get(hit.channel) ?? "a channel"}
              </span>
            </span>
            <Link
              to={resultHref(slug, hit.channel, hit.parent_seq)}
              className="rounded-lg px-3 py-1.5 text-sm font-semibold text-accent-text hover:bg-bg-subtle"
            >
              Open conversation
            </Link>
          </li>
        ))}
      </ul>
      <MoreButton results={results} />
    </Panel>
  );
}

function IssueResults({ slug, params }: { slug: string; params: SearchParams }) {
  const results = useIssueSearch(slug, params);
  const pages = results.data?.pages ?? [];
  const hits: IssueHit[] = pages.flatMap((page) => page.results);
  const terms = pages[0]?.terms ?? [];

  const shown = resultState(results.isPending, results.isError, hits.length, terms);
  if (shown) return shown;
  return (
    <Panel className="settle">
      <ul aria-label="Results" className="divide-y divide-border">
        {hits.map((hit) => (
          <li key={hit.ref}>
            <Link
              to={`/w/${slug}/projects/${hit.project}/issues/${String(hit.number)}`}
              className="flex flex-col gap-0.5 px-5 py-4 hover:bg-bg-subtle"
            >
              <span className="flex flex-wrap items-baseline gap-x-2 text-sm">
                <span className="font-mono text-text-subtle">{hit.ref}</span>
                <span className="font-semibold">
                  <Highlighted text={hit.title} terms={terms} />
                </span>
                <span className="text-xs text-text-subtle">{STATUS_LABELS[hit.status]}</span>
              </span>
              {hit.description && (
                <span className="text-sm text-text-muted">
                  <Highlighted text={preview(hit.description, 200)} terms={terms} />
                </span>
              )}
            </Link>
          </li>
        ))}
      </ul>
      <MoreButton results={results} />
    </Panel>
  );
}
