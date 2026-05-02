import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { AttendanceLogResponse } from "@/api/types";

import { formatDuration, groupSessionsByDay } from "./helpers";

interface Props {
  sessions: AttendanceLogResponse[];
}

export const WorkHoursChart = ({ sessions }: Props): JSX.Element => {
  const grouped = groupSessionsByDay(sessions);
  const data = Array.from(grouped.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([day, secs]) => ({
      date: day.slice(5).replace("-", "."),
      hours: Math.round((secs / 3600) * 100) / 100,
      seconds: secs,
    }));

  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={data} margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="date" />
        <YAxis label={{ value: "часы", angle: -90, position: "insideLeft" }} />
        <Tooltip
          formatter={(_value, _name, item) =>
            formatDuration((item.payload as { seconds: number }).seconds)
          }
        />
        <Bar dataKey="hours" fill="var(--color-primary)" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
};
