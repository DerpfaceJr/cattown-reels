// patch6v.mjs - registers hooks6v.mjs so live/record.mjs (v6 kit, unchanged on disk) is patched in memory.
// usage: node --import ./live/patch6v.mjs live/record.mjs live/reels/<reel>.json
import { register } from 'node:module';
register('./hooks6v.mjs', import.meta.url);
