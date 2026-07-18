import { useEffect, useRef, useState } from "react";
import * as pdfjsLib from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import type { FieldValue } from "../api";

pdfjsLib.GlobalWorkerOptions.workerSrc = workerUrl;

interface Props {
  fileUrl: string;
  documentId: string;
  fields: FieldValue[];
  /** field name to highlight; null highlights all */
  focusField: string | null;
}

/** Renders page 1 of the source PDF with the evidence source-boxes overlaid.
 * The same information is available as text in the fields table next to it,
 * so the canvas is marked as an image with a descriptive label. */
export default function EvidenceViewer({ fileUrl, documentId, fields, focusField }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [dims, setDims] = useState<{ w: number; h: number; scale: number; pageH: number } | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const doc = await pdfjsLib.getDocument(fileUrl).promise;
        const page = await doc.getPage(1);
        const scale = 0.9;
        const viewport = page.getViewport({ scale });
        const canvas = canvasRef.current;
        if (!canvas || cancelled) return;
        canvas.width = viewport.width;
        canvas.height = viewport.height;
        const ctx = canvas.getContext("2d")!;
        await page.render({ canvasContext: ctx, viewport }).promise;
        if (!cancelled) {
          setDims({ w: viewport.width, h: viewport.height, scale, pageH: viewport.height / scale });
          setError("");
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Could not render the PDF preview.");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [fileUrl]);

  const boxes = fields.filter(
    (f) => f.bbox && (focusField === null || f.field === focusField),
  );

  return (
    <figure aria-label={`Preview of document ${documentId} with evidence boxes highlighted`} style={{ margin: 0 }}>
      {error ? (
        <p role="alert" className="banner alert">
          PDF preview unavailable: {error}. All extracted values and their page/box citations remain
          listed in the table.
        </p>
      ) : (
        <div className="pdf-stage">
          <canvas ref={canvasRef} role="img" aria-label={`Page 1 of ${documentId}. Highlighted evidence: ${boxes.map((b) => b.field).join(", ") || "none"}.`} />
          {dims &&
            boxes.map((f) => {
              const [x1, y1, x2, y2] = f.bbox!;
              return (
                <div
                  key={f.field}
                  className="evidence-box"
                  style={{
                    left: x1 * dims.scale,
                    top: (dims.pageH - y2) * dims.scale,
                    width: (x2 - x1) * dims.scale,
                    height: (y2 - y1) * dims.scale,
                  }}
                />
              );
            })}
        </div>
      )}
      <figcaption className="visually-hidden">
        Evidence locations, also listed as text:{" "}
        {boxes
          .map((f) => `${f.field} on page ${f.page} in box ${f.bbox?.map((n) => Math.round(n)).join(", ")}`)
          .join("; ")}
      </figcaption>
    </figure>
  );
}
