import { useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useWebSocket } from "./useWebSocket";

export function useRealtimeSync() {
  const client = useQueryClient();
  const onMessage = useCallback(
    (event: unknown) => {
      if (!event || typeof event !== "object" || !("type" in event)) return;
      const type = String(event.type);
      if (type.startsWith("classification.")) {
        void client.invalidateQueries({ queryKey: ["classification-jobs"] });
        void client.invalidateQueries({ queryKey: ["dashboard"] });
      }
    },
    [client],
  );
  useWebSocket(onMessage);
}
