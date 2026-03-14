export type LogLevel = "debug" | "info" | "warn" | "error";

const STORAGE_KEY = "xenage-log-level";

const levelPriority: Record<LogLevel, number> = {
  debug: 10,
  info: 20,
  warn: 30,
  error: 40,
};

function normalizeLogLevel(value: string | null): LogLevel {
  if (value === "debug" || value === "info" || value === "warn" || value === "error") {
    return value;
  }

  return "info";
}

export function getLogLevel(): LogLevel {
  return normalizeLogLevel(localStorage.getItem(STORAGE_KEY));
}

export function setLogLevel(level: LogLevel) {
  localStorage.setItem(STORAGE_KEY, level);
}

function shouldLog(level: LogLevel) {
  return levelPriority[level] >= levelPriority[getLogLevel()];
}

function write(level: LogLevel, message: string, ...args: unknown[]) {
  if (!shouldLog(level)) {
    return;
  }

  const prefix = `[xenage:${level}] ${message}`;
  if (level === "debug" || level === "info") {
    console.log(prefix, ...args);
    return;
  }

  if (level === "warn") {
    console.warn(prefix, ...args);
    return;
  }

  console.error(prefix, ...args);
}

export const logger = {
  debug(message: string, ...args: unknown[]) {
    write("debug", message, ...args);
  },
  info(message: string, ...args: unknown[]) {
    write("info", message, ...args);
  },
  warn(message: string, ...args: unknown[]) {
    write("warn", message, ...args);
  },
  error(message: string, ...args: unknown[]) {
    write("error", message, ...args);
  },
};
