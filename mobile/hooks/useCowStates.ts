import { useState, useEffect, useRef } from "react";
import { BACKEND_URL } from "../constants/Config";

export interface CowState {
  posture: "STANDING" | "DOWN";
  down_duration_sec: number;
  alerted: boolean;
}

export type CowStatesMap = Record<string, CowState>;

export function useCowStates(intervalMs = 2000) {
  const [states, setStates] = useState<CowStatesMap>({});
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchStates = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/states`);
      if (res.ok) {
        const data: CowStatesMap = await res.json();
        setStates(data);
        setLastUpdated(new Date());
      }
    } catch {
      // backend not reachable — keep last known state
    }
  };

  useEffect(() => {
    fetchStates();
    timerRef.current = setInterval(fetchStates, intervalMs);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [intervalMs]);

  return { states, lastUpdated };
}
