'use client';

import { useFormStatus } from 'react-dom';
import { useState } from 'react';
import { generateOfferAction, updateConstructValueAction } from '../../app/designer/actions';
import { GenerateOfferInputSchema } from '../../../shared/types/offer-brief';
import type { OfferBrief } from '../../../shared/types/offer-brief';
import { OfferBriefCard } from './OfferBriefCard';
import { Spinner } from './Spinner';

function SubmitButton({ alreadyGenerated }: { alreadyGenerated: boolean }) {
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      disabled={pending || alreadyGenerated}
      className="btn-primary w-full disabled:opacity-50 disabled:cursor-not-allowed"
      aria-label="Generate offer brief"
    >
      {pending ? (
        <>
          <Spinner />
          Generating...
        </>
      ) : alreadyGenerated ? (
        'Offer Sent to Hub'
      ) : (
        'Generate Offer'
      )}
    </button>
  );
}

interface ManualEntryFormProps {
  initialObjective?: string;
  aiSuggestedConstructValue?: number;
  onOfferGenerated?: (objective: string) => void;
}

export function ManualEntryForm({ initialObjective, aiSuggestedConstructValue, onOfferGenerated }: ManualEntryFormProps) {
  const [generatedOffer, setGeneratedOffer] = useState<OfferBrief | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  // construct_value: the discount percentage the marketer can override
  const [constructValue, setConstructValue] = useState<string>(
    aiSuggestedConstructValue !== undefined ? String(aiSuggestedConstructValue) : ''
  );
  // Tracks fields the marketer has manually edited — AI suggestions cannot overwrite these
  const [overriddenFields, setOverriddenFields] = useState<Set<string>>(new Set());

  function markOverridden(fieldName: string) {
    setOverriddenFields((prev) => new Set(prev).add(fieldName));
  }

  async function handleConstructValueBlur() {
    if (!generatedOffer || !constructValue) return;
    const parsedValue = parseFloat(constructValue);
    if (isNaN(parsedValue)) return;
    if (parsedValue === generatedOffer.construct.value) return;
    // Replace old discount % in objective text so Hub shows the updated value
    const oldPct = generatedOffer.construct.value;
    const pctRegex = new RegExp(String(oldPct).replace('.', '\\.') + '(\\.0)?%', 'g');
    const newObjective = generatedOffer.objective.replace(pctRegex, `${parsedValue}%`);
    const objectiveChanged = newObjective !== generatedOffer.objective;
    try {
      await updateConstructValueAction(
        generatedOffer.offer_id,
        parsedValue,
        objectiveChanged ? newObjective : undefined,
      );
      setGeneratedOffer({
        ...generatedOffer,
        construct: { ...generatedOffer.construct, value: parsedValue },
        ...(objectiveChanged ? { objective: newObjective } : {}),
      });
    } catch {
      // Best-effort — Hub PATCH failed silently
    }
  }

  async function handleSubmit(formData: FormData) {
    const objective = formData.get('objective') as string;

    const parsed = GenerateOfferInputSchema.safeParse({ objective });
    if (!parsed.success) {
      setValidationError(parsed.error.errors[0].message);
      return;
    }
    setValidationError(null);
    setError(null);

    // Attach marketer's construct_value to formData if set
    if (constructValue) {
      formData.set('construct_value', constructValue);
    }

    const result = await generateOfferAction(formData);
    if (result.success) {
      let finalOffer = result.offer;
      // If marketer manually overrode the discount, apply it now and persist to Hub
      const parsedValue = constructValue ? parseFloat(constructValue) : NaN;
      if (overriddenFields.has('construct_value') && !isNaN(parsedValue)) {
        // Also update the objective text so Hub reflects the new discount %
        const oldPct = finalOffer.construct.value;
        const pctRegex = new RegExp(String(oldPct).replace('.', '\\.') + '(\\.0)?%', 'g');
        const newObjective = finalOffer.objective.replace(pctRegex, `${parsedValue}%`);
        const objectiveChanged = newObjective !== finalOffer.objective;
        try {
          await updateConstructValueAction(
            finalOffer.offer_id,
            parsedValue,
            objectiveChanged ? newObjective : undefined,
          );
        } catch {
          // Best-effort — if PATCH fails, still show offer with local override applied
        }
        finalOffer = {
          ...finalOffer,
          construct: { ...finalOffer.construct, value: parsedValue },
          ...(objectiveChanged ? { objective: newObjective } : {}),
        };
      }
      setGeneratedOffer(finalOffer);
      onOfferGenerated?.(finalOffer.objective);
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

        <div>
          <label htmlFor="construct_value" className="input-label">
            Offer Discount % <span className="text-gray-400 font-normal">(optional — overrides AI suggestion)</span>
          </label>
          <input
            id="construct_value"
            name="construct_value"
            type="number"
            min={1}
            max={100}
            value={constructValue}
            placeholder="e.g., 20"
            className="input"
            aria-describedby="construct-value-hint"
            onChange={(e) => {
              setConstructValue(e.target.value);
              markOverridden('construct_value');
            }}
            onBlur={handleConstructValueBlur}
          />
          <p id="construct-value-hint" className="mt-1.5 text-xs text-gray-400">
            {overriddenFields.has('construct_value')
              ? 'Your value will be used — AI suggestions will not override this field.'
              : 'Leave blank to let AI determine the optimal discount.'}
          </p>
        </div>

        <SubmitButton alreadyGenerated={generatedOffer !== null} />
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
