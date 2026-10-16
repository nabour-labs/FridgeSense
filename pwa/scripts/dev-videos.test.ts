// @vitest-environment node
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { Writable } from "node:stream";
import { videosHandler } from "./dev-videos";

/** A stand-in for Node's ServerResponse: records status, headers and body. */
class FakeRes extends Writable {
  statusCode = 200;
  headers: Record<string, string | number> = {};
  chunks: Buffer[] = [];
  setHeader(name: string, value: string | number) {
    this.headers[name.toLowerCase()] = value;
  }
  _write(chunk: Buffer, _enc: BufferEncoding, done: () => void) {
    this.chunks.push(Buffer.from(chunk));
    done();
  }
  get body() {
    return Buffer.concat(this.chunks);
  }
}

async function call(handler: ReturnType<typeof videosHandler>, url: string, headers: Record<string, string> = {}) {
  const res = new FakeRes();
  const finished = new Promise((resolve) => res.on("finish", resolve));
  handler({ url, method: "GET", headers } as never, res as never);
  await finished;
  return res;
}

let dir: string;
beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), "dev-videos-"));
  writeFileSync(join(dir, "a.mp4"), "0123456789");
  writeFileSync(join(dir, "b.mp4"), "abcdefghijklmnopqrst");
  writeFileSync(join(dir, "notes.txt"), "secret");
  writeFileSync(join(dir, "..env-not-here"), "x");
});
afterEach(() => rmSync(dir, { recursive: true, force: true }));

it("Listing: mp4 clips newest name first, with size and url", async () => {
  const res = await call(videosHandler({ dir, upload: false }), "/");
  expect(res.statusCode).toBe(200);
  expect(res.headers["content-type"]).toBe("application/json");
  expect(JSON.parse(res.body.toString())).toEqual({
    clips: [
      { name: "b.mp4", size: 20, url: "/__dev/videos/b.mp4" },
      { name: "a.mp4", size: 10, url: "/__dev/videos/a.mp4" },
    ],
    upload: false,
  });
});

it("Listing: upload is true when /api goes to a deployed backend", async () => {
  const res = await call(videosHandler({ dir, upload: true }), "/");
  expect(JSON.parse(res.body.toString()).upload).toBe(true);
});

it("Missing folder: an empty list", async () => {
  const res = await call(videosHandler({ dir: join(dir, "nope"), upload: false }), "/");
  expect(res.statusCode).toBe(200);
  expect(JSON.parse(res.body.toString())).toEqual({ clips: [], upload: false });
});

it("Range request: 206 with the asked bytes", async () => {
  const res = await call(videosHandler({ dir, upload: false }), "/a.mp4", { range: "bytes=2-5" });
  expect(res.statusCode).toBe(206);
  expect(res.headers["content-range"]).toBe("bytes 2-5/10");
  expect(res.headers["content-type"]).toBe("video/mp4");
  expect(res.headers["content-length"]).toBe(4);
  expect(res.body.toString()).toBe("2345");
});

it("Range request: an open-ended range runs to the end", async () => {
  const res = await call(videosHandler({ dir, upload: false }), "/a.mp4", { range: "bytes=7-" });
  expect(res.statusCode).toBe(206);
  expect(res.headers["content-range"]).toBe("bytes 7-9/10");
  expect(res.body.toString()).toBe("789");
});

it("Whole file: 200 with Accept-Ranges", async () => {
  const res = await call(videosHandler({ dir, upload: false }), "/a.mp4");
  expect(res.statusCode).toBe(200);
  expect(res.headers["accept-ranges"]).toBe("bytes");
  expect(res.headers["content-type"]).toBe("video/mp4");
  expect(res.body.toString()).toBe("0123456789");
});

it.each(["/..%2Fa.mp4", "/..%2F..%2Fetc%2Fpasswd", "/notes.txt", "/sub%2Fa.mp4", "/..env-not-here"])(
  "Path escape refused: %s is 404",
  async (url) => {
    const res = await call(videosHandler({ dir, upload: false }), url);
    expect(res.statusCode).toBe(404);
    expect(res.body.length).toBe(0);
  },
);

it("Unknown clip: 404", async () => {
  const res = await call(videosHandler({ dir, upload: false }), "/missing.mp4");
  expect(res.statusCode).toBe(404);
});
