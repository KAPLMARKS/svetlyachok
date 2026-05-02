export const ROUTES = {
  login: "/login",
  home: "/",
  dashboard: "/attendance",
  employees: "/employees",
  zones: "/zones",
  radiomap: "/radiomap",
  attendance: "/attendance",
  attendanceEmployee: "/attendance/:employeeId",
  notFound: "*",
} as const;

export const toEmployeeAttendanceUrl = (employeeId: number): string =>
  `/attendance/${employeeId}`;
