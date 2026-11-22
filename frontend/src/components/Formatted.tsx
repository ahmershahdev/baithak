import { useState, type ReactNode } from "react";

import { parse, type Block, type Inline } from "../chat/format";
import { mentionSegments } from "../chat/mentions";
import type { Message } from "../chat/timeline";

const mentionClass = {
  person: "font-semibold text-accent-text",
  me: "rounded bg-mention px-0.5 font-semibold ring-1 ring-mention-edge",
  channel: "rounded bg-mention px-0.5 font-semibold ring-1 ring-mention-edge",
};

const codeClass = "rounded bg-surface-sunken px-1 py-0.5 font-mono text-[0.9em]";

interface Context {
  message: Message;
  meId: number;
}

function Spoiler({ children }: { children: ReactNode }) {
  const [shown, setShown] = useState(false);
  if (shown) return <span className="rounded bg-surface-sunken px-0.5">{children}</span>;
  return (
    <button
      type="button"
      onClick={() => {
        setShown(true);
      }}
      aria-label="Spoiler, select to show"
      className="rounded bg-text px-0.5 text-transparent select-none hover:opacity-80 focus-visible:ring-2 focus-visible:ring-focus-ring focus-visible:outline-none"
    >
      <span aria-hidden="true">{children}</span>
    </button>
  );
}

function Text({ text, context }: { text: string; context: Context }) {
  return (
    <>
      {mentionSegments(text, context.message, context.meId).map((part, index) =>
        "mention" in part ? (
          <span key={index} className={mentionClass[part.mention]}>
            {part.text}
          </span>
        ) : (
          part.text
        ),
      )}
    </>
  );
}

function Inlines({ nodes, context }: { nodes: Inline[]; context: Context }) {
  return (
    <>
      {nodes.map((node, index) => {
        switch (node.type) {
          case "text":
            return <Text key={index} text={node.text} context={context} />;
          case "code":
            return (
              <code key={index} className={codeClass}>
                {node.text}
              </code>
            );
          case "link":
            return (
              <a
                key={index}
                href={node.href}
                target="_blank"
                rel="noreferrer noopener"
                className="text-info underline"
              >
                <Inlines nodes={node.children} context={context} />
              </a>
            );
          case "spoiler":
            return (
              <Spoiler key={index}>
                <Inlines nodes={node.children} context={context} />
              </Spoiler>
            );
          default: {
            const Tag = { bold: "strong", italic: "em", underline: "u", strike: "s" }[node.type] as
              "strong" | "em" | "u" | "s";
            return (
              <Tag key={index}>
                <Inlines nodes={node.children} context={context} />
              </Tag>
            );
          }
        }
      })}
    </>
  );
}

function Blocks({
  blocks,
  context,
  trailing,
}: {
  blocks: Block[];
  context: Context;
  trailing?: ReactNode;
}) {
  const lastParagraph = blocks.at(-1)?.type === "paragraph";
  return (
    <>
      {blocks.map((block, index) => {
        const end = index === blocks.length - 1 && lastParagraph ? trailing : null;
        switch (block.type) {
          case "paragraph":
            return (
              <p key={index} className="break-words whitespace-pre-wrap">
                <Inlines nodes={block.children} context={context} />
                {end}
              </p>
            );
          case "heading": {
            const size = { 1: "text-xl", 2: "text-lg", 3: "text-base" }[block.level];
            return (
              <p key={index} className={`font-display font-semibold ${size}`}>
                <Inlines nodes={block.children} context={context} />
              </p>
            );
          }
          case "code":
            return (
              <pre
                key={index}
                className="my-1 overflow-x-auto rounded-lg border border-border bg-surface-sunken p-3 font-mono text-sm"
              >
                <code>{block.text}</code>
              </pre>
            );
          case "quote":
            return (
              <blockquote
                key={index}
                className="border-l-4 border-border-strong pl-3 text-text-muted"
              >
                <Blocks blocks={block.children} context={context} />
              </blockquote>
            );
          case "list": {
            const items = block.items.map((item, at) => (
              <li key={at}>
                <Inlines nodes={item} context={context} />
              </li>
            ));
            return block.ordered ? (
              <ol key={index} start={block.start} className="list-decimal pl-6">
                {items}
              </ol>
            ) : (
              <ul key={index} className="list-disc pl-6">
                {items}
              </ul>
            );
          }
        }
      })}
      {!lastParagraph && trailing}
    </>
  );
}

/** A message body with its formatting and the mentions the server confirmed. */
export function Formatted({
  message,
  meId,
  trailing,
}: {
  message: Message;
  meId: number;
  trailing?: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1">
      <Blocks blocks={parse(message.body)} context={{ message, meId }} trailing={trailing} />
    </div>
  );
}
