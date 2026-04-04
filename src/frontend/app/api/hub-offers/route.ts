import { NextRequest, NextResponse } from 'next/server';

/** Server-side proxy for Hub offers — lets client components poll without exposing MARKETER_JWT. */
export async function GET(request: NextRequest) {
  const status = request.nextUrl.searchParams.get('status');

  const apiUrl = new URL(
    `${process.env.API_URL ?? 'http://localhost:8000'}/api/hub/offers`,
  );
  if (status) apiUrl.searchParams.set('status', status);

  try {
    const res = await fetch(apiUrl.toString(), {
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${process.env.MARKETER_JWT ?? ''}`,
      },
      cache: 'no-store',
    });

    if (!res.ok) {
      return NextResponse.json({ offers: [], count: 0 }, { status: res.status });
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ offers: [], count: 0 }, { status: 503 });
  }
}
