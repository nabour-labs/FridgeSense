// React Native's URL has no protocol/pathname/origin, so the site URL is parsed by hand.
const HTTPS = /^https:\/\/([^/?#\s]+)([^?#\s]*)/;

/** The FridgeSense site's TV dashboard: the site URL (from site.config.json) with #tv. */
export function tvUrl(siteUrl: string | undefined): string {
  const match = HTTPS.exec(siteUrl ?? '');
  if (!match) {
    throw new Error('FridgeSense site URL must be https');
  }
  const [, host, path] = match;
  return `https://${host}${path.endsWith('/') ? path : `${path}/`}#tv`;
}
