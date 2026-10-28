import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

test('all four Forge HTML dialogs carry an explicit dialog role for the macOS AX subrole', () => {
  const dialogs=[];
  for (const file of ['Forge.sys.mjs','ControlCenter.sys.mjs','Shortcuts.sys.mjs']) {
    const code=readFileSync(new URL(`../overlay/${file}`,import.meta.url),'utf8');
    for (const match of code.matchAll(/el\("dialog",\s*\{([^}]+)\}/g)) {
      assert.match(match[1],/role:\s*"dialog"/,file);
      assert.match(match[1],/"aria-labelledby":/,file);
      dialogs.push(match[1].match(/id:\s*"([^"]+)"/)[1]);
    }
  }
  assert.deepEqual(dialogs.sort(),['forge-control-center','forge-editor','forge-palette','forge-shortcuts']);
});
