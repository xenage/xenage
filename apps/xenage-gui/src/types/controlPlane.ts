export interface ManifestField {
  name: string;
  type: string;
  required: boolean;
  isArray: boolean;
}

export interface ManifestSectionMap {
  metadata: ManifestField[];
  spec: ManifestField[];
  status: ManifestField[];
}

export interface ManifestSample {
  apiVersion: string;
  metadata: Record<string, unknown>;
  spec: Record<string, unknown>;
  status: Record<string, unknown>;
}

export interface ManifestResource {
  kind: string;
  title: string;
  fields: ManifestField[];
  sections: ManifestSectionMap;
  sample: ManifestSample;
}

export interface ManifestSort {
  field: string;
  direction: "asc" | "desc";
}

export interface ManifestTableColumn {
  key: string;
  label: string;
  path: string;
  type: string;
  isArray: boolean;
  width: number;
  minWidth: number;
  displayOnly: boolean;
}

export interface ManifestTable {
  kind: string;
  title: string;
  source: string;
  rowKind: string;
  rowKey: string;
  defaultSort: ManifestSort;
  pageSize?: number | null;
  columns: ManifestTableColumn[];
  sample: Record<string, unknown>;
}

export interface NavigationLeaf {
  label: string;
  kind: string;
}

export interface NavigationNode {
  label: string;
  children: NavigationLeaf[];
}

export interface ControlPlaneManifest {
  apiVersion: string;
  kind: string;
  generatedAt: string;
  product: {
    name: string;
    tagline: string;
  };
  navigation: NavigationNode;
  resources: ManifestResource[];
  tables: ManifestTable[];
}
