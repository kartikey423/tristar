import { NextRequest, NextResponse } from 'next/server';

/**
 * Server-side proxy for customer offer acceptance.
 * Routes through API_URL (server-side env) instead of NEXT_PUBLIC_API_URL
 * so all developers hit the same shared backend regardless of their local setup.
 *
 * Fixes: "Could not activate offer — Not Found" when NEXT_PUBLIC_API_URL
 * is missing or points to a different backend than API_URL.
 */
export async function POST(
  _request: NextRequest,
  { params }: { params: Promise<{ offerId: string }> },
) {
  const { offerId } = await params;
  const backendUrl = `${process.env.API_URL ?? 'http://localhost:8000'}/api/hub/offers/${encodeURIComponent(offerId)}/customer-accept`;

  try {
    const res = await fetch(backendUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });

    const body = await res.json().catch(() => ({}));

    if (!res.ok) {
      return NextResponse.json(body, { status: res.status });
    }

    return NextResponse.json(body, { status: res.status });
  } catch (err) {
    return NextResponse.json(
      { detail: `Hub unreachable: ${err}` },
      { status: 503 },
    );
  }
}
