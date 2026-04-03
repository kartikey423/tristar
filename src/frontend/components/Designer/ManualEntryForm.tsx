'use client';

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
      className="btn-primary w-full"
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
          <label htmlFor="objective" className="input-label">
            Marketing Objective
          </label>
          <textarea
            id="objective"
            name="objective"
            rows={4}
            defaultValue={initialObjective}
            placeholder="e.g., Reactivate lapsed high-value members with a compelling winter sports offer"
            className="input resize-none"
            aria-describedby={validationError ? 'objective-error' : 'objective-hint'}
            aria-invalid={!!validationError}
            required
            minLength={10}
            maxLength={500}
          />
          {validationError ? (
            <p id="objective-error" className="mt-1.5 text-xs text-red-600" role="alert">
              {validationError}
            </p>
          ) : (
            <p id="objective-hint" className="mt-1.5 text-xs text-gray-400">
              Describe your marketing goal in 1-2 sentences (10-500 characters).
            </p>
          )}
        </div>

        <SubmitButton />
      </form>

      {error && (
        <div className="card border-l-2 border-red-500 px-4 py-3" role="alert">
          <p className="text-sm text-red-700">{error}</p>
          <button
            onClick={() => setError(null)}
            className="mt-1.5 text-xs text-red-500 hover:text-red-700"
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
