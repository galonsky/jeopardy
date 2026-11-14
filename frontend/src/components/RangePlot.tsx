export type RangeRow = {
  id: number;
  name: string;
  attempts: number;
  proficiency: number;
  lower_bound: number;
  upper_bound: number;
  subtopics?: RangeRow[];
};

const WEAK_BELOW = 0.45;
const THIN_BELOW = 30;
const percent = (value: number) => Math.round(value * 100);

function Row({ row, nested = false }: { row: RangeRow; nested?: boolean }) {
  const weak = row.proficiency < WEAK_BELOW;
  const thin = row.attempts < THIN_BELOW;
  const label = `${row.name} ${percent(row.proficiency)}%, range ${percent(row.lower_bound)}–${percent(row.upper_bound)}, ${row.attempts} attempts`;
  return (
    <div
      className={`range-row ${nested ? "nested" : ""} ${weak ? "weak" : ""} ${thin ? "thin" : ""}`}
      role="img"
      aria-label={label}
    >
      <span className="range-name">{row.name}</span>
      <span className="range-track">
        <span
          className="range-whisker"
          style={{
            left: `${percent(row.lower_bound)}%`,
            width: `${percent(row.upper_bound) - percent(row.lower_bound)}%`,
          }}
        />
        <span className="range-dot" style={{ left: `${percent(row.proficiency)}%` }} />
      </span>
      <span className="range-value">{percent(row.proficiency)}%</span>
      <small className="range-n">n={row.attempts}</small>
    </div>
  );
}

export function RangePlot({
  rows,
  overall,
  expanded = false,
}: {
  rows: RangeRow[];
  overall: number;
  expanded?: boolean;
}) {
  const sorted = rows
    .filter((row) => row.attempts > 0)
    .sort((a, b) => a.proficiency - b.proficiency);
  return (
    <div className="range-plot">
      <div className="range-axis" aria-hidden="true">
        <span />
        <span className="range-ticks">
          <span>0</span>
          <span>25</span>
          <span>50</span>
          <span>75</span>
          <span>100</span>
        </span>
        <span />
        <span />
      </div>
      <div className="range-body">
        <div className="range-overall-layer" aria-hidden="true">
          <span />
          <span className="range-overall-col">
            <span
              className="range-overall"
              style={{ left: `${percent(overall)}%` }}
              title={`Overall estimate ${percent(overall)}%`}
            />
          </span>
        </div>
        {sorted.map((row) => {
          const topics = (row.subtopics ?? [])
            .filter((topic) => topic.attempts > 0)
            .sort((a, b) => a.proficiency - b.proficiency);
          return topics.length ? (
            <details key={row.id} open={expanded}>
              <summary>
                <Row row={row} />
              </summary>
              {topics.map((topic) => (
                <Row key={topic.id} row={topic} nested />
              ))}
            </details>
          ) : (
            <Row key={row.id} row={row} />
          );
        })}
      </div>
    </div>
  );
}
