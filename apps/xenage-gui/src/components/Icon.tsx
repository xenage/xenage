import type { LucideProps } from "lucide-react";

import {
  ShieldCheck,
  Bot,
  AlertCircle,
  Webhook,
  ChevronRight,
  X,
  Hexagon,
  FileCode,
  Globe,
  Zap,
  Clock,
  MousePointer2,
  Briefcase,
  Scroll,
  Cpu,
  Box,
  Server,
  LayoutDashboard,
  PanelLeft,
  Plus,
  Package,
  Play,
  Search,
  Key,
  Share2,
  Settings,
  Terminal,
  Hammer,
  Activity,
} from "lucide-react";

export type IconName =
  | "access"
  | "agent"
  | "alert"
  | "api"
  | "close"
  | "cluster"
  | "chevron"
  | "customResource"
  | "environment"
  | "event"
  | "history"
  | "interface"
  | "job"
  | "log"
  | "mcp"
  | "model"
  | "nodes"
  | "overview"
  | "panel"
  | "plus"
  | "resourceType"
  | "run"
  | "search"
  | "secret"
  | "share"
  | "settings"
  | "session"
  | "tool"
  | "usage";

const icons: Record<IconName, React.ComponentType<LucideProps>> = {
  access: ShieldCheck,
  agent: Bot,
  alert: AlertCircle,
  api: Webhook,
  chevron: ChevronRight,
  close: X,
  cluster: Hexagon,
  customResource: FileCode,
  environment: Globe,
  event: Zap,
  history: Clock,
  interface: MousePointer2,
  job: Briefcase,
  log: Scroll,
  mcp: Cpu,
  model: Box,
  nodes: Server,
  overview: LayoutDashboard,
  panel: PanelLeft,
  plus: Plus,
  resourceType: Package,
  run: Play,
  search: Search,
  secret: Key,
  share: Share2,
  settings: Settings,
  session: Terminal,
  tool: Hammer,
  usage: Activity,
};

export function Icon({ name, ...props }: { name: IconName } & LucideProps) {
  const LucideIcon = icons[name];
  if (!LucideIcon) return null;

  return (
    <LucideIcon
      size={16}
      strokeWidth={1.5}
      className="ui-icon"
      aria-hidden
      {...props}
    />
  );
}

export function iconNameForItem(kind: string): IconName {
  const kindToIcon: Record<string, IconName> = {
    Cluster: "overview",
    Node: "nodes",
    Agent: "agent",
    Run: "run",
    Session: "session",
    Tool: "tool",
    MCP: "mcp",
    Job: "job",
    Event: "event",
    Log: "log",
    ResourceType: "resourceType",
    CustomResource: "customResource",
    ExecutionEnvironment: "environment",
    Secret: "secret",
    AccessControl: "access",
    Interface: "interface",
    Model: "model",
    APIAccess: "api",
    ConfigHistory: "history",
    Alert: "alert",
    Usage: "usage",
  };

  return kindToIcon[kind] ?? "overview";
}
