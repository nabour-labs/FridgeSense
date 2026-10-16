import type { Api } from "../AppContext";

/** Debug mode: on whenever the app runs on the Vite dev server, never in the production build. */
export const isDebug = (): boolean => import.meta.env.DEV;

/** The owner closed the clip picker without picking a frame: not an error. */
export class PickCancelled extends Error {
  constructor() {
    super("clip pick cancelled");
    this.name = "PickCancelled";
  }
}

/** `api` with `cameraSnapshot` swapped; every other method still runs on the original client. */
export function withSnapshot(api: Api, cameraSnapshot: Api["cameraSnapshot"]): Api {
  return new Proxy(api, {
    get(target, key) {
      if (key === "cameraSnapshot") return cameraSnapshot;
      const value = Reflect.get(target, key);
      return typeof value === "function" ? value.bind(target) : value;
    },
  });
}
