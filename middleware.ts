import { NextRequest, NextResponse } from "next/server"

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl

  // Allow login page and auth API without session
  if (pathname === "/admin/login" || pathname === "/api/admin/auth") {
    return NextResponse.next()
  }

  // Protect admin pages (not API routes - those check auth internally)
  if (pathname.startsWith("/admin")) {
    const session = request.cookies.get("admin_session")?.value

    if (!session) {
      const loginUrl = new URL("/admin/login", request.url)
      return NextResponse.redirect(loginUrl)
    }
  }

  return NextResponse.next()
}

export const config = {
  matcher: ["/admin/:path*"],
}
