import { controlPlaneManifest } from "../../generated/controlPlaneSchema";
import type { PartialOptions } from "overlayscrollbars";
import type { ControlPlaneManifest } from "../../types/controlPlane";

export const controlPlane: ControlPlaneManifest = controlPlaneManifest;

export const SETUP_TAB_ID = "app:setup-guide";
export const SETUP_KIND = "SetupGuide";
export const SETTINGS_TAB_ID = "app:settings";
export const SETTINGS_KIND = "Settings";

export const DEFAULT_CONTROL_PLANE_ARGS = `--node-id
cp-local
--data-dir
/tmp/xenage/cp-local
--endpoint
http://127.0.0.1:8734
serve
--host
127.0.0.1
--port
8734`;

export const DEFAULT_RUNTIME_ARGS = `--node-id
rt-local
--data-dir
/tmp/xenage/rt-local
serve`;

export const DEFAULT_GUI_CONNECTION_YAML = `apiVersion: xenage.io/v1alpha1
kind: ClusterConnection
metadata:
  name: demo-admin
spec:
  clusterName: demo
  controlPlaneUrls:
    - http://127.0.0.1:8734
  user:
    id: admin
    role: admin
    publicKey: REPLACE_WITH_GENERATED_PUBLIC_KEY
    privateKey: REPLACE_WITH_GENERATED_PRIVATE_KEY`;

export const OVERLAY_SCROLLBAR_OPTIONS: PartialOptions = {
  scrollbars: {
    autoHide: "leave",
    autoHideDelay: 120,
    clickScroll: true,
    dragScroll: true,
    theme: "os-theme-xenage",
  },
};

export const TAB_SCROLLBAR_OPTIONS: PartialOptions = {
  overflow: {
    x: "scroll",
    y: "hidden",
  },
  scrollbars: {
    autoHide: "leave",
    autoHideDelay: 120,
    clickScroll: true,
    dragScroll: true,
    theme: "os-theme-xenage os-theme-xenage-tabs",
  },
};
