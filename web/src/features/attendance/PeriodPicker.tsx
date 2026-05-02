import { useState } from "react";

import { type DateRange, dayPresets } from "./helpers";

interface Props {
  value: DateRange;
  onChange: (range: DateRange) => void;
}

type Preset = "today" | "week" | "month" | "custom";

const btnStyle = (active: boolean): React.CSSProperties => ({
  padding: "var(--space-2) var(--space-3)",
  background: active ? "var(--color-primary)" : "transparent",
  color: active ? "var(--color-primary-fg)" : "var(--color-fg)",
  border: "1px solid var(--color-border)",
  borderRadius: "var(--radius-md)",
  cursor: "pointer",
  fontSize: 13,
});

export const PeriodPicker = ({ value, onChange }: Props): JSX.Element => {
  const [preset, setPreset] = useState<Preset>("week");
  const presets = dayPresets();

  const apply = (next: Preset): void => {
    setPreset(next);
    if (next === "today") onChange(presets.today);
    else if (next === "week") onChange(presets.week);
    else if (next === "month") onChange(presets.month);
  };

  return (
    <div style={{ display: "flex", gap: "var(--space-2)", flexWrap: "wrap", alignItems: "center" }}>
      <button type="button" onClick={() => apply("today")} style={btnStyle(preset === "today")}>
        Сегодня
      </button>
      <button type="button" onClick={() => apply("week")} style={btnStyle(preset === "week")}>
        Неделя
      </button>
      <button type="button" onClick={() => apply("month")} style={btnStyle(preset === "month")}>
        Месяц
      </button>
      <button type="button" onClick={() => setPreset("custom")} style={btnStyle(preset === "custom")}>
        Период
      </button>
      {preset === "custom" && (
        <>
          <input
            type="date"
            value={value.from.slice(0, 10)}
            onChange={(e) => {
              const next = `${e.target.value}T00:00:00.000Z`;
              onChange({ from: next, to: value.to });
            }}
            style={{
              padding: "var(--space-2)",
              border: "1px solid var(--color-border)",
              borderRadius: "var(--radius-md)",
            }}
          />
          <input
            type="date"
            value={value.to.slice(0, 10)}
            onChange={(e) => {
              const next = `${e.target.value}T23:59:59.999Z`;
              onChange({ from: value.from, to: next });
            }}
            style={{
              padding: "var(--space-2)",
              border: "1px solid var(--color-border)",
              borderRadius: "var(--radius-md)",
            }}
          />
        </>
      )}
    </div>
  );
};
