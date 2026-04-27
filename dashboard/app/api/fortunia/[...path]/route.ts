/**
 * Server-side proxy for Fortunia API.
 *
 * Injects FORTUNIA_API_KEY (server-only env var) so it is never
 * exposed in the browser bundle.
 *
 * Browser calls /api/fortunia/<path> → this route → http://fortunia-api:8000/<path>
 */
import { NextRequest, NextResponse } from 'next/server';

const API_URL = process.env.FORTUNIA_API_URL || 'http://fortunia-api:8000';
const API_KEY = process.env.FORTUNIA_API_KEY || '';

async function proxy(request: NextRequest, path: string[], method: string) {
  const url = new URL(`/${path.join('/')}`, API_URL);

  // Forward all query params
  request.nextUrl.searchParams.forEach((value, key) => {
    url.searchParams.set(key, value);
  });

  const headers: Record<string, string> = {
    'X-Internal-Key': API_KEY,
  };

  const contentType = request.headers.get('content-type');
  if (contentType) headers['Content-Type'] = contentType;

  const options: RequestInit = { method, headers };

  if (method !== 'GET' && method !== 'HEAD') {
    options.body = await request.text();
  }

  try {
    const response = await fetch(url.toString(), options);
    const text = await response.text();
    let body: unknown;
    try {
      body = JSON.parse(text);
    } catch {
      body = { detail: text };
    }
    return NextResponse.json(body, { status: response.status });
  } catch {
    return NextResponse.json({ detail: 'Fortunia API no disponible' }, { status: 503 });
  }
}

type RouteContext = { params: Promise<{ path: string[] }> };

export async function GET(req: NextRequest, ctx: RouteContext) {
  const { path } = await ctx.params;
  return proxy(req, path, 'GET');
}

export async function POST(req: NextRequest, ctx: RouteContext) {
  const { path } = await ctx.params;
  return proxy(req, path, 'POST');
}

export async function PATCH(req: NextRequest, ctx: RouteContext) {
  const { path } = await ctx.params;
  return proxy(req, path, 'PATCH');
}

export async function DELETE(req: NextRequest, ctx: RouteContext) {
  const { path } = await ctx.params;
  return proxy(req, path, 'DELETE');
}
