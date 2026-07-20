import { useEffect, useState } from "react";

export function useRotatingValue(values, { enabled = true, intervalMs = 4200, resetKey = "" } = {}) {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    setIndex(0);
  }, [resetKey, values]);

  useEffect(() => {
    if (!enabled || values.length < 2) return undefined;
    const intervalId = window.setInterval(() => {
      setIndex((current) => (current + 1) % values.length);
    }, intervalMs);
    return () => window.clearInterval(intervalId);
  }, [enabled, intervalMs, resetKey, values]);

  return {
    index,
    value: values[index] ?? values[0],
  };
}
