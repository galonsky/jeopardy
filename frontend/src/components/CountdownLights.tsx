const LIGHTS = 9;

export function CountdownLights({ seconds, total }: { seconds: number; total: number }) {
  const lit = total > 0 ? Math.ceil((Math.min(seconds, total) / total) * LIGHTS) : 0;
  return (
    <div className="lights" role="img" aria-label={`${seconds} seconds left`}>
      {Array.from({ length: LIGHTS }, (_, index) => (
        <i key={index} className={index < lit ? "" : "off"} />
      ))}
    </div>
  );
}
