import { hello_web_count } from './hello_web.mjs';
// CPU work runs in a real module worker, entirely in the compiled MoonBit port.
self.onmessage = ({data: {generation, index, start, end}}) => {
  const count = hello_web_count(start, end);
  self.postMessage({generation, index, count, start, end});
};
