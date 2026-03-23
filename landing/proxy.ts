import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

export function proxy(request: NextRequest): NextResponse {
  const { pathname } = request.nextUrl;
  if (pathname !== "/") {
    return NextResponse.next();
  }

  const userAgent = request.headers.get("user-agent") ?? "";
  const acceptsHtml = (request.headers.get("accept") ?? "").includes("text/html");
  const isCurl = /(^|\s)curl\//i.test(userAgent) || userAgent.toLowerCase() === "curl";

  if (isCurl && !acceptsHtml) {
    const installUrl = request.nextUrl.clone();
    installUrl.pathname = "/install.sh";
    return NextResponse.rewrite(installUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/"],
};
