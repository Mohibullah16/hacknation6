import { useEffect, useRef, useState } from "react";
import * as pdfjsLib from "pdfjs-dist";
import type { PDFPageProxy, RenderTask } from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import type { FieldValue } from "../api";

pdfjsLib.GlobalWorkerOptions.workerSrc = workerUrl;

const BASE_SCALE = 0.9;
const ZOOM_SCALE = 2.0;

interface Props {
  fileUrl: string;
  documentId: string;
  fields: FieldValue[];
  /** field name to highlight; null highlights all */
  focusField: string | null;
}

/** Renders page 1 of the source PDF with the evidence source-boxes overlaid.
 * Focusing a single field re-renders at ZOOM_SCALE and scrolls its cited box
 * to the center of the stage (instant, no animation). The same information is
 * available as text in the fields table next to it, so the canvas is marked
 * as an image with a descriptive label. */
export default function EvidenceViewer({ fileUrl, documentId, fields, focusField }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const stageRef = useRef<HTMLDivElement>(null);
  const [page, setPage] = useState<PDFPageProxy | null>(null);
  const [dims, setDims] = useState<{ w: number; h: number; scale: number; pageH: number } | null>(null);
  const [error, setError] = useState("");

  const focused = focusField ? fields.find((f) => f.field === focusField && f.bbox) : undefined;
  const scale = focused ? ZOOM_SCALE : BASE_SCALE;

  useEffect(() => {
    let cancelled = false;
    setPage(null);
    (async () => {
      try {
        const doc = await pdfjsLib.getDocument(fileUrl).promise;
        const p = await doc.getPage(1);
        if (!cancelled) {
          setPage(p);
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

  useEffect(() => {
    if (!page) return;
    let cancelled = false;
    let task: RenderTask | undefined;
    (async () => {
      try {
        const viewport = page.getViewport({ scale });
        const canvas = canvasRef.current;
        if (!canvas || cancelled) return;
        canvas.width = viewport.width;
        canvas.height = viewport.height;
        const ctx = canvas.getContext("2d")!;
        task = page.render({ canvasContext: ctx, viewport });
        await task.promise;
        if (cancelled) return;
        const pageH = viewport.height / scale;
        setDims({ w: viewport.width, h: viewport.height, scale, pageH });
        /* Center the focused citation box in the scrollable stage. Instant on
         * purpose: no motion, so no prefers-reduced-motion concern. */
        const stage = stageRef.current;
        if (stage && focused?.bbox) {
          const [x1, y1, x2, y2] = focused.bbox;
          stage.scrollLeft = ((x1 + x2) / 2) * scale - stage.clientWidth / 2;
          stage.scrollTop = (pageH - (y1 + y2) / 2) * scale - stage.clientHeight / 2;
        } else if (stage) {
          stage.scrollLeft = 0;
          stage.scrollTop = 0;
        }
      } catch (e) {
        if (!cancelled && !(e instanceof Error && e.name === "RenderingCancelledException")) {
          setError(e instanceof Error ? e.message : "Could not render the PDF preview.");
        }
      }
    })();
    return () => {
      cancelled = true;
      task?.cancel();
    };
  }, [page, scale, focused?.field]);

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
        <div ref={stageRef} className={`pdf-stage${focused ? " zoomed" : ""}`}>
          <canvas
            ref={canvasRef}
            role="img"
            aria-label={`Page 1 of ${documentId}${focused ? `, zoomed to the cited box for ${focused.field}` : ""}. Highlighted evidence: ${boxes.map((b) => b.field).join(", ") || "none"}.`}
          />
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
