/**
 * Spinner — inline loading indicator for buttons.
 * White border for use on coloured button backgrounds.
 */

interface SpinnerProps {
  className?: string;
}

export function Spinner({ className = 'h-4 w-4' }: SpinnerProps) {
  return (
    <span
      className={`${className} animate-spin rounded-full border-2 border-white border-t-transparent`}
      aria-hidden="true"
    />
  );
}
