import { useCallback, useRef, useState } from "react";

export function useDataFetchIndicator() {
  const pendingFetchCountRef = useRef(0);
  const pendingFetchHadErrorRef = useRef(false);
  const [isDataFetching, setIsDataFetching] = useState(false);
  const [hasDataFetchError, setHasDataFetchError] = useState(false);

  const beginDataFetch = useCallback(() => {
    pendingFetchCountRef.current += 1;
    setIsDataFetching(true);
  }, []);

  const markDataFetchError = useCallback(() => {
    pendingFetchHadErrorRef.current = true;
  }, []);

  const endDataFetch = useCallback(() => {
    pendingFetchCountRef.current = Math.max(0, pendingFetchCountRef.current - 1);
    if (pendingFetchCountRef.current !== 0) {
      return;
    }
    setIsDataFetching(false);
    setHasDataFetchError(pendingFetchHadErrorRef.current);
    pendingFetchHadErrorRef.current = false;
  }, []);

  return {
    beginDataFetch,
    endDataFetch,
    hasDataFetchError,
    isDataFetching,
    markDataFetchError,
  };
}
