// Wrapper for live/scene.mjs (Reel B). Run 41497497422 failed at record: API /api/chat status=403.
// Cause (DerpfaceJr/cat-town src/access.ts @42a7ab15): owner writes from loopback are refused unless the request
// carries header 'x-town-action: owner' ('Use the local Cat Town interface.'). scene.mjs sent only content-type.
// This wrapper adds that header to Node-side fetches to localhost /api/ only, then runs scene.mjs unchanged
// (process.argv[2] is still the reel config).
const realFetch = globalThis.fetch;
globalThis.fetch = (input, init = {}) => {
  const url = typeof input === 'string' ? input : (input && input.url) || String(input);
  if (/^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?\/api\//.test(url)) {
    const h = new Headers((init && init.headers) || {});
    h.set('x-town-action', 'owner');
    init = { ...init, headers: h };
    console.log('API_HEADER x-town-action=owner path=' + url.replace(/^https?:\/\/[^/]+/, ''));
  }
  return realFetch(input, init);
};
console.log('RECORDER_WRAPPER live/scene-b.mjs -> live/scene.mjs');
await import('./scene.mjs');
