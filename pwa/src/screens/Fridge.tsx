import { useCallback, useState } from "react";
import type { Inventory } from "../api/types";
import { useApp } from "../AppContext";
import { usePolling } from "../usePolling";

export function Fridge() {
  const { api, report, online } = useApp();
  const [inventory, setInventory] = useState<Inventory | null>(null);
  const load = useCallback(() => {
    api.inventory().then(
      (inv) => {
        setInventory(inv);
        online();
      },
      report,
    );
  }, [api, report, online]);
  usePolling(load, 10_000);

  return (
    <section>
      {inventory?.items.map((i) => <p key={i.key}>{i.name}</p>)}
    </section>
  );
}
