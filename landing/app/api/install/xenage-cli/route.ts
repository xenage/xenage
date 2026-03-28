import { createInstallHandler } from "../_lib/resolver";

export const runtime = "nodejs";

export const GET = createInstallHandler("latest_cli");
