import { useMemo } from "react";
import { encode } from "uqr";

/** Dark cells drawn as one SVG path; always black on white, since scanners need that contrast
 * even in dark mode. Four cells of quiet zone, as the QR standard asks. */
export function QrCode({
  text,
  label,
  size = 192,
}: {
  text: string;
  label: string;
  size?: number;
}) {
  const { cells, path } = useMemo(() => {
    const code = encode(text, { ecc: "M", border: 4 });
    const parts: string[] = [];
    code.data.forEach((row, y) => {
      row.forEach((dark, x) => {
        if (dark) parts.push(`M${String(x)} ${String(y)}h1v1h-1z`);
      });
    });
    return { cells: code.size, path: parts.join("") };
  }, [text]);
  return (
    <svg
      role="img"
      aria-label={label}
      viewBox={`0 0 ${String(cells)} ${String(cells)}`}
      width={size}
      height={size}
      shapeRendering="crispEdges"
      className="shrink-0 rounded-xl border border-border"
    >
      <rect width={cells} height={cells} fill="#ffffff" />
      <path d={path} fill="#000000" />
    </svg>
  );
}
