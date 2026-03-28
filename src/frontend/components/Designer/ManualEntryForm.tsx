'use client';

/**
 * ManualEntryForm — Client Component.
 *
 * Objective textarea with Zod validation. Calls generateOfferAction Server Action.
 * Uses useFormStatus for pending state (spinner + disabled button).
 * On success, renders OfferBriefCard with the generated offer.
 */

import { useFormStatus } from 'react-dom';
import { useState } from 'react';
import { generateOfferAction } from '../../app/designer/actions';
import { GenerateOfferInputSchema } from '../../../shared/types/offer-brief';
import type { OfferBrief } from '../../../shared/types/offer-brief';
import { OfferBriefCard } from './OfferBriefCard';
import { Spinner } from './Spinner';

function SubmitButton() {
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      disabled={pending}
      className="flex w-full items-center justify-center gap-2 rounded-md bg-blue-600 px-6 py-3 text-sm font-medium text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
      aria-label="Generate offer brief"
    >
      {pending ? (
        <>
          <Spinner />
          Generating...
        </>
      ) : (
        'Generate Offer'
      )}
    </button>
  );
}

interface ManualEntryFormProps {
  initialObjective?: string;
}

export function ManualEntryForm({ initialObjective }: ManualEntryFormProps) {
  const [generatedOffer, setGeneratedOffer] = useState<OfferBrief | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);

  async function handleSubmit(formData: FormData) {
    const objective = formData.get('objective') as string;

    // Client-side Zod validation before hitting the server
    const parsed = GenerateOfferInputSchema.safeParse({ objective });
    if (!parsed.success) {
      setValidationError(parsed.error.errors[0].message);
      return;
    }
    setValidationError(null);
    setError(null);

    const result = await generateOfferAction(formData);
    if (result.success) {
      setGeneratedOffer(result.offer);
    } else {
      setError(result.error);
    }
  }

  return (
    <div className="space-y-6">
      <form action={handleSubmit} className="space-y-4">
        <div>
          <label
            htmlFor="objective"
            className="block text-sm font-medium text-gray-700"
          >
            Marketing Objective
          </label>
          <textarea
            id="objective"
            name="objective"
            rows={4}
            defaultValue={initialObjective}
            placeholder="e.g., Reactivate lapsed high-value members with a compelling winter sports offer"
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            aria-describedby={validationError ? 'objective-error' : 'objective-hint'}
            aria-invalid={!!validationError}
            required
            minLength={10}
            maxLength={500}
          />
          {validationError ? (
            <p id="objective-error" className="mt-1.5 text-sm text-red-600" role="alert">
              {validationError}
            </p>
          ) : (
            <p id="objective-hint" className="mt-1.5 text-xs text-gray-500">
              Describe your marketing goal in 1–2 sentences (10–500 characters).
            </p>
          )}
        </div>

        <SubmitButton />
      </form>

      {error && (
        <div
          className="rounded-md border border-red-200 bg-red-50 px-4 py-3"
          role="alert"
        >
          <p className="text-sm text-red-700">{error}</p>
          <button
            onClick={() => setError(null)}
            className="mt-2 text-xs text-red-600 underline hover:no-underline"
          >
            Dismiss
          </button>
        </div>
      )}

      {generatedOffer && (
        <div className="mt-6">
          <OfferBriefCard offer={generatedOffer} />
        </div>
      )}
    </div>
  );
}
