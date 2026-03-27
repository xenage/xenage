import type { EventLogEntry } from "../../types/guiConnection";

export type ClusterEntry = {
  id: string;
  name: string;
  accent: string;
};

export type ClusterUiPrefs = {
  name: string;
  accent: string;
};

export type ClusterEventCache = {
  hasMore: boolean;
  items: EventLogEntry[];
  loading: boolean;
  oldestSequence: number | null;
};

export type EventFetchMode = "initial" | "older" | "refresh";
