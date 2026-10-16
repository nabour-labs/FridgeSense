import { createReadStream, readdirSync, statSync } from "node:fs";
import type { IncomingMessage, ServerResponse } from "node:http";
import { join, resolve, sep } from "node:path";
import type { Plugin } from "vite";

/** Local fridge recordings: FRIDGESENSE_VIDEOS, or the repo's gitignored tmp/. */
const DEFAULT_DIR = new URL("../../tmp", import.meta.url).pathname;
const CLIP_NAME = /^[\w-][\w.-]*\.mp4$/;

/**
 * Dev-only clip routes for the Mock video switch: GET / lists the clips, GET /<name> streams one
 * (with Range, so the player can seek). Never part of the production build.
 */
export function videosHandler({ dir, upload }: { dir: string; upload: boolean }) {
  const root = resolve(dir);
  const notFound = (res: ServerResponse) => {
    res.statusCode = 404;
    res.end();
  };

  return (req: IncomingMessage, res: ServerResponse) => {
    const path = (req.url ?? "/").split("?")[0];
    if (path === "/" || path === "") {
      let names: string[] = [];
      try {
        names = readdirSync(root).filter((n) => CLIP_NAME.test(n));
      } catch {
        // No folder: no clips.
      }
      const clips = names
        .sort()
        .reverse()
        .map((name) => ({ name, size: statSync(join(root, name)).size, url: `/__dev/videos/${name}` }));
      res.setHeader("content-type", "application/json");
      return res.end(JSON.stringify({ clips, upload }));
    }

    let name: string;
    try {
      name = decodeURIComponent(path.slice(1));
    } catch {
      return notFound(res);
    }
    const file = resolve(root, name);
    if (!CLIP_NAME.test(name) || name.includes("..") || !file.startsWith(root + sep)) return notFound(res);
    let size: number;
    try {
      const stat = statSync(file);
      if (!stat.isFile()) return notFound(res);
      size = stat.size;
    } catch {
      return notFound(res);
    }

    res.setHeader("content-type", "video/mp4");
    res.setHeader("accept-ranges", "bytes");
    const range = /^bytes=(\d*)-(\d*)$/.exec(req.headers.range ?? "");
    if (!range || (!range[1] && !range[2])) {
      res.setHeader("content-length", size);
      return createReadStream(file).pipe(res);
    }
    const start = range[1] ? Number(range[1]) : Math.max(0, size - Number(range[2]));
    const end = range[1] && range[2] ? Math.min(Number(range[2]), size - 1) : size - 1;
    if (start > end || start >= size) {
      res.statusCode = 416;
      res.setHeader("content-range", `bytes */${size}`);
      return res.end();
    }
    res.statusCode = 206;
    res.setHeader("content-range", `bytes ${start}-${end}/${size}`);
    res.setHeader("content-length", end - start + 1);
    createReadStream(file, { start, end }).pipe(res);
  };
}

/** Serves the clip routes under /__dev/videos on the dev server, with the mock API or a proxied backend. */
export function devVideos(): Plugin {
  return {
    name: "fridgesense-dev-videos",
    apply: "serve",
    configureServer(server) {
      const dir = process.env.FRIDGESENSE_VIDEOS || DEFAULT_DIR;
      const upload = Boolean(process.env.FRIDGESENSE_URL) && !process.env.FRIDGESENSE_MOCK;
      server.middlewares.use("/__dev/videos", videosHandler({ dir, upload }));
    },
  };
}
