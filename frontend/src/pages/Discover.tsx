import { useEffect, useMemo, useState } from "react";
import { api } from "../api";

type Property = Record<string, string>;

/** Discover (stretch goal): transparent browsing of the public HUD LIHTC
 * teaching subset. Availability is ALWAYS "unknown" (the dataset cannot
 * support vacancy claims), filters are renter-selected only, and the
 * unfiltered total is always shown — nothing is silently suppressed. */
export default function Discover() {
  const [data, setData] = useState<{ disclaimer: string; total_unfiltered: number; properties: Property[] } | null>(null);
  const [error, setError] = useState("");
  const [city, setCity] = useState("all");
  const [minBedrooms, setMinBedrooms] = useState("0");

  useEffect(() => {
    api.getProperties().then(setData).catch((e) => setError(e instanceof Error ? e.message : "Could not load properties."));
  }, []);

  const cities = useMemo(
    () => Array.from(new Set((data?.properties ?? []).map((p) => p.project_city))).sort(),
    [data],
  );

  const filtered = useMemo(() => {
    let rows = data?.properties ?? [];
    if (city !== "all") rows = rows.filter((p) => p.project_city === city);
    if (minBedrooms === "2") rows = rows.filter((p) => Number(p.two_bedroom_units || 0) + Number(p.three_bedroom_units || 0) + Number(p.four_bedroom_units || 0) > 0);
    if (minBedrooms === "3") rows = rows.filter((p) => Number(p.three_bedroom_units || 0) + Number(p.four_bedroom_units || 0) > 0);
    return rows;
  }, [data, city, minBedrooms]);

  return (
    <>
      <h1>Discover — public LIHTC locations, transparently</h1>
      <p className="lede">
        These are the {data?.total_unfiltered ?? "…"} public HUD LIHTC project records in the frozen
        teaching subset. This list can never rank you, filter you out, or predict acceptance — the only
        filters are the ones <em>you</em> choose below.
      </p>
      {data && (
        <p className="banner" role="note">
          <strong>Dataset limit (rule HUD-DATA-001):</strong> {data.disclaimer}
        </p>
      )}
      {error && (
        <p role="alert" className="banner alert">
          {error}
        </p>
      )}

      <div className="panel" role="group" aria-labelledby="filters-heading">
        <h2 id="filters-heading" style={{ marginTop: 0 }}>
          Your filters (optional)
        </h2>
        <div style={{ display: "flex", gap: "1.5rem", flexWrap: "wrap" }}>
          <div>
            <label htmlFor="city-filter">City</label>
            <select
              id="city-filter"
              value={city}
              onChange={(e) => setCity(e.target.value)}
              style={{ font: "inherit", padding: "0.5rem", minHeight: 40, border: "2px solid var(--muted)", borderRadius: 6 }}
            >
              <option value="all">All cities</option>
              {cities.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="bed-filter">Bedrooms needed</label>
            <select
              id="bed-filter"
              value={minBedrooms}
              onChange={(e) => setMinBedrooms(e.target.value)}
              style={{ font: "inherit", padding: "0.5rem", minHeight: 40, border: "2px solid var(--muted)", borderRadius: 6 }}
            >
              <option value="0">Any</option>
              <option value="2">2 or more</option>
              <option value="3">3 or more</option>
            </select>
          </div>
        </div>
        <p role="status" style={{ marginBottom: 0 }}>
          Showing <strong>{filtered.length}</strong> of <strong>{data?.total_unfiltered ?? 0}</strong>{" "}
          records (the full unfiltered set is always available — choose “All cities” and “Any”).
        </p>
      </div>

      <table>
        <caption>Public HUD LIHTC project records — availability is always unknown</caption>
        <thead>
          <tr>
            <th scope="col">Project</th>
            <th scope="col">Location</th>
            <th scope="col">Total / low-income units</th>
            <th scope="col">Bedrooms (2/3/4+)</th>
            <th scope="col">Availability</th>
            <th scope="col">Location precision</th>
          </tr>
        </thead>
        <tbody>
          {filtered.map((p) => (
            <tr key={p.hud_id}>
              <th scope="row">{p.project_name}</th>
              <td>
                {p.project_address}, {p.project_city}, {p.project_state} {p.project_zip}
              </td>
              <td>
                {p.total_units} / {p.low_income_units}
              </td>
              <td>
                {p.two_bedroom_units}/{p.three_bedroom_units}/{p.four_bedroom_units}
              </td>
              <td>
                <span className="chip neutral">Unknown — not a vacancy feed</span>
              </td>
              <td>
                {p.geocode_precision_code === "R" || p.geocode_precision_code === "4" ? (
                  <span className="chip ok">
                    <span aria-hidden="true">✓ </span>address-level
                  </span>
                ) : (
                  <span className="chip warn">
                    <span aria-hidden="true">≈ </span>approximate area only
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
