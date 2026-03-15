export interface ClusterNodeTableRow {
  node_id: string;
  role: "control-plane" | "runtime";
  leader: boolean;
  public_key: string;
  endpoints: string[];
  status?: string;
  name?: string;
  version?: string;
  age?: string;
  last_poll_at?: string;
}

export interface GroupConfigKeyTableRow {
  key: string;
  value: string;
}

export interface EventLogEntry {
  sequence: number;
  happened_at: string;
  actor_id: string;
  actor_type: "node" | "user" | "system";
  action: string;
  details: Record<string, string>;
}

export interface UserRecord {
  user_id: string;
  public_key: string;
  enabled: boolean;
}

export interface GuiClusterSnapshot {
  group_id: string;
  state_version: number;
  leader_epoch: number;
  nodes: ClusterNodeTableRow[];
  group_config: GroupConfigKeyTableRow[];
  users: UserRecord[];
}

export interface GuiEventPage {
  items: EventLogEntry[];
  has_more: boolean;
  next_before_sequence: number;
}
