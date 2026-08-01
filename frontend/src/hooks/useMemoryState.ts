import { useState, useEffect } from 'react';

// Global in-memory cache that persists across unmounts 
// but is automatically cleared on full page refresh.
const memoryStore: Record<string, any> = {};

export function useMemoryState<T>(key: string, initialValue: T): [T, (val: T | ((prev: T) => T)) => void] {
  const [state, setState] = useState<T>(() => {
    return key in memoryStore ? memoryStore[key] : initialValue;
  });

  useEffect(() => {
    memoryStore[key] = state;
  }, [key, state]);

  return [state, setState];
}
