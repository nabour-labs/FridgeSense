import { tvUrl } from "../src/site";

// Loads #tv
test("the TV dashboard is the site URL with #tv", () => {
  expect(tvUrl("https://d1example.cloudfront.net")).toBe("https://d1example.cloudfront.net/#tv");
});

// URL already ends with a slash or hash
test("a trailing slash or another hash is replaced by /#tv", () => {
  expect(tvUrl("https://d1example.cloudfront.net/")).toBe("https://d1example.cloudfront.net/#tv");
  expect(tvUrl("https://d1example.cloudfront.net/#fridge")).toBe("https://d1example.cloudfront.net/#tv");
  expect(tvUrl("https://example.com/app")).toBe("https://example.com/app/#tv");
});

// Bad site URL
test("a missing or non-HTTPS site URL is refused", () => {
  for (const bad of [undefined, "", "http://d1example.cloudfront.net", "d1example.cloudfront.net", "not a url"]) {
    expect(() => tvUrl(bad)).toThrow("FridgeSense site URL must be https");
  }
});
