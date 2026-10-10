import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';

const source = await readFile(
  new URL('../src/sentio/static/js/core/tutor_runtime.js', import.meta.url),
  'utf8',
);
const functions = source.slice(
  source.indexOf('function renderMarkdown('),
  source.indexOf('function showTyping('),
);
const context = vm.createContext({});
vm.runInContext(functions, context);
assert.equal(
  context.renderMarkdown('<img src=x onerror="alert(1)">'),
  '&lt;img src=x onerror="alert(1)"&gt;',
);
assert.equal(context.renderMarkdown('**Safe**'), '<strong>Safe</strong>');
assert.equal(
  context.renderMarkdown('```html\n<b>example</b>\n```'),
  '<pre><code>&lt;b&gt;example&lt;/b&gt;</code></pre>',
);
console.log('Tutor rendering escapes HTML and preserves formatting.');
