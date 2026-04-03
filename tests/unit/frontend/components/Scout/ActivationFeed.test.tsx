/**
 * Unit tests for ActivationFeed — AC-019.
 */

import { render, screen, waitFor } from '@testing-library/react';
import { ActivationFeed } from '../../../../../src/frontend/components/Scout/ActivationFeed';
import type { ActivationLogEntry } from '../../../../../src/frontend/lib/scout-api';

jest.mock('../../../../../src/frontend/lib/scout-api', () => ({
  fetchActivationLog: jest.fn(),
}));

import { fetchActivationLog } from '../../../../../src/frontend/lib/scout-api';
const mockFetchActivationLog = fetchActivationLog as jest.MockedFunction<typeof fetchActivationLog>;

const sampleEntries: ActivationLogEntry[] = [
  {
    member_id: 'demo-001',
    offer_id: 'offer-abc-123',
    score: 78.5,
    scoring_method: 'claude',
    outcome: 'activated',
    timestamp: '2026-03-28T10:30:00Z',
  },
  {
    member_id: 'demo-001',
    offer_id: 'offer-def-456',
    score: 65.0,
    scoring_method: 'fallback',
    outcome: 'queued',
    timestamp: '2026-03-28T09:00:00Z',
  },
];

describe('ActivationFeed', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('shows loading placeholder while fetching', async () => {
    mockFetchActivationLog.mockImplementation(() => new Promise<ActivationLogEntry[]>(() => {}));
    render(<ActivationFeed memberId="demo-001" />);

    await waitFor(() => {
      expect(screen.getByText('Loading activation history...')).toBeInTheDocument();
    });
  });

  test('renders activation rows when fetchActivationLog resolves', async () => {
    mockFetchActivationLog.mockResolvedValue(sampleEntries);
    render(<ActivationFeed memberId="demo-001" />);

    await waitFor(() => {
      expect(screen.getByText('offer-abc-123')).toBeInTheDocument();
    });
    expect(screen.getByText('offer-def-456')).toBeInTheDocument();
    // Score column
    expect(screen.getByText('78.5')).toBeInTheDocument();
    // Outcome badges
    expect(screen.getByText('activated')).toBeInTheDocument();
    expect(screen.getByText('queued')).toBeInTheDocument();
    // Scoring method
    expect(screen.getByText('claude')).toBeInTheDocument();
  });

  test('renders nothing (null) when entries are empty', async () => {
    mockFetchActivationLog.mockResolvedValue([]);
    render(<ActivationFeed memberId="demo-001" />);

    await waitFor(() => {
      expect(screen.queryByText('Loading activation history...')).not.toBeInTheDocument();
    });
    expect(screen.queryByRole('list')).not.toBeInTheDocument();
  });

  test('re-fetches when memberId prop changes', async () => {
    mockFetchActivationLog.mockResolvedValue([]);
    const { rerender } = render(<ActivationFeed memberId="demo-001" />);

    await waitFor(() => {
      expect(mockFetchActivationLog).toHaveBeenCalledWith('demo-001');
    });

    rerender(<ActivationFeed memberId="demo-002" />);

    await waitFor(() => {
      expect(mockFetchActivationLog).toHaveBeenCalledWith('demo-002');
    });
    expect(mockFetchActivationLog).toHaveBeenCalledTimes(2);
  });

  test('re-fetches when refreshTrigger prop changes', async () => {
    mockFetchActivationLog.mockResolvedValue([]);
    const { rerender } = render(<ActivationFeed memberId="demo-001" refreshTrigger={0} />);

    await waitFor(() => {
      expect(mockFetchActivationLog).toHaveBeenCalledTimes(1);
    });

    rerender(<ActivationFeed memberId="demo-001" refreshTrigger={1} />);

    await waitFor(() => {
      expect(mockFetchActivationLog).toHaveBeenCalledTimes(2);
    });
  });

  test('handles fetch failure silently without crashing', async () => {
    mockFetchActivationLog.mockRejectedValue(new Error('Network error'));

    expect(() => render(<ActivationFeed memberId="demo-001" />)).not.toThrow();

    await waitFor(() => {
      expect(mockFetchActivationLog).toHaveBeenCalledTimes(1);
    });
    // No error displayed to user
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
});
