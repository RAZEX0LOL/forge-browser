import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { ValidationError, parseCommandBindings, parseSettingsTransfer, validateProject } from "../overlay/core.sys.mjs";
import { formatError, createStrings, uiLocale } from "../overlay/Localization.sys.mjs";
import vm from "node:vm";
const source = locale => readFileSync(new URL(`../overlay/locales/${locale}/forge.ftl`, import.meta.url), "utf8");
const messages = text => new Map([...text.matchAll(/^(forge-[\w-]+)\s*=([^]*?)(?=^forge-|$(?![^]))/gm)].map(match => [match[1], match[2]]));

test("Russian and English Fluent resources have matching message IDs and variables", () => {
  const ru = messages(source("ru")), en = messages(source("en-US"));
  assert.ok(ru.size > 60);
  assert.deepEqual([...ru.keys()].sort(), [...en.keys()].sort());
  for (const [id, value] of ru) {
    const variables = text => [...new Set([...text.matchAll(/\$([\w-]+)/g)].map(match => match[1]))].sort();
    assert.deepEqual(variables(value), variables(en.get(id)), id);
  }
});

test("every command and command section has a Fluent label in both locales", () => {
  const commands = readFileSync(new URL("../overlay/Commands.sys.mjs", import.meta.url), "utf8");
  const ids = [...commands.matchAll(/^\s*\["([\w-]+)",/gm)].map(match => match[1]);
  for (const locale of ["ru", "en-US"]) {
    const resource = messages(source(locale));
    for (const id of ids) { assert.ok(resource.has(`forge-command-${id}`), `${locale}:${id}`); }
    for (const group of ["space", "library", "browser"]) { assert.ok(resource.has(`forge-section-${group}`)); }
  }
});

test("catalogues have no duplicate IDs and cover every explicit formatter and HTML marker", () => {
  const directory = new URL('../overlay/', import.meta.url);
  const files = readdirSync(directory).filter(name => /\.(mjs|html)$/.test(name));
  const used = new Set();
  for (const name of files) {
    const code = readFileSync(new URL(name, directory), 'utf8');
    for (const match of code.matchAll(/(?:\b(?:t|text|ValidationError)\("|data-forge-l10n=")(forge-[\w-]+)/g)) { used.add(match[1]); }
  }
  for (const locale of ['ru', 'en-US']) {
    const text = source(locale), resource = messages(text);
    assert.equal([...text.matchAll(/^forge-[\w-]+\s*=/gm)].length, resource.size, 'Duplicate ID');
    for (const id of used) { assert.ok(resource.has(id), `${locale}: missing ${id}`); }
  }
});

test("Forge UI modules keep Russian prose only in Fluent, not hardcoded labels or errors", () => {
  const directory = new URL('../overlay/', import.meta.url);
  for (const name of readdirSync(directory).filter(name => name.endsWith('.mjs'))) {
    let code = readFileSync(new URL(name, directory), 'utf8');
    // Search aliases are intentionally multilingual and are not UI labels.
    for (const alias of ['keyboard shortcuts горячие клавиши', 'tab вкладки ', 'theme custom css дизайн тема', 'split view два окна']) {
      code = code.replace(alias, 'search-alias');
    }
    assert.equal(/[А-Яа-яЁё]/u.test(code), false, `${name}: unlocalized prose`);
  }
});

test("validation errors use stable Fluent IDs/args and unknown errors do not leak details", () => {
  const formatter = (id, args) => ({id,args});
  for (const run of [()=>parseCommandBindings('broken'),()=>parseSettingsTransfer('broken'),()=>validateProject(null)]) {
    assert.throws(run, error => error instanceof ValidationError && /^forge-error-/.test(error.l10nId));
  }
  assert.deepEqual(formatError(formatter, new ValidationError('forge-error-shortcuts-conflict',{key:'R'})),
    {id:'forge-error-shortcuts-conflict',args:{key:'R'}});
  assert.deepEqual(formatError(formatter, new Error('private diagnostic detail')),
    {id:'forge-error-unexpected',args:undefined});
});

test("page localization preserves controls and cannot assign executable or navigation attributes", () => {
  const node = (id, attribute = null) => ({
    textContent:'fallback', attributes:{'data-forge-l10n':id,'data-forge-l10n-attr':attribute},
    getAttribute(name) { return this.attributes[name]; },
    setAttribute(name, value) { this.attributes[name] = value; },
  });
  const title = node('title'), button = node('button','aria-label');
  const unsafe = node('untrusted','onclick'), navigation = node('navigation','href');
  const document = { readyState:'complete', querySelectorAll:()=>[title,button,unsafe,navigation],
    documentElement:{setAttribute(){} } };
  vm.runInNewContext(readFileSync(new URL('../overlay/localize.js',import.meta.url),'utf8'), {
    document, window:{}, console,
    ChromeUtils:{importESModule:()=>({createStrings:()=>id=>`<not markup: ${id}>`,uiLocale:()=>'ru'})},
  });
  assert.equal(title.textContent,'<not markup: title>');
  assert.equal(button.attributes['aria-label'],'<not markup: button>');
  assert.equal(button.textContent,'fallback', 'Do not replace a button’s SVG children');
  assert.equal(unsafe.attributes.onclick,undefined);
  assert.equal(navigation.attributes.href,undefined);
});

test("built-in locale packages follow app language while legacy builds retain Russian UI", () => {
  const previous=globalThis.Services;
  let follow=false, locale='en-US';
  globalThis.Services={prefs:{getBoolPref:()=>follow},locale:{get appLocaleAsBCP47(){return locale;}}};
  try {
    class Registry { registerSources(){} }
    class Localization {
      constructor(_ids,_sync,_registry,locales){this.locales=locales;}
      formatValueSync(id){return `${this.locales[0]}:${id}`;}
    }
    const win={L10nRegistry:Registry,L10nFileSource:class{},Localization};
    assert.equal(uiLocale(),'ru');
    const ru=createStrings(win);assert.equal(ru('key'),'ru:key');
    follow=true;
    const en=createStrings(win);assert.equal(uiLocale(),'en-US');assert.equal(en('key'),'en-US:key');
    assert.equal(createStrings(win),en);
    locale='ru';assert.equal(createStrings(win),ru);
    assert.equal(createStrings(win,'en-US'),en);
  } finally {
    if(previous===undefined){delete globalThis.Services;}else{globalThis.Services=previous;}
  }
});
