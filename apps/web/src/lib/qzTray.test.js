import test from "node:test";
import assert from "node:assert/strict";

import { CASH_DRAWER_PULSE } from "./printing.js";
import { bytesToBase64, createQzTransport, loadQzScript } from "./qzTray.js";

function fakeQz({ active = false } = {}) {
  const calls = { print: [], connect: 0, certificate: null, signature: null };
  const state = { active };
  const lib = {
    websocket: {
      isActive: () => state.active,
      connect: async () => { calls.connect += 1; state.active = true; },
    },
    security: {
      setCertificatePromise: (fn) => { calls.certificate = fn; },
      setSignaturePromise: (fn) => { calls.signature = fn; },
    },
    print: async (config, data) => { calls.print.push({ config, data }); },
  };
  return { lib, calls, state };
}

test("isAvailable: false without a QZ global, true once the socket is active", () => {
  const idle = fakeQz({ active: false });
  assert.equal(createQzTransport({ qz: idle.lib }).isAvailable(), false);
  const live = fakeQz({ active: true });
  assert.equal(createQzTransport({ qz: live.lib }).isAvailable(), true);
  assert.equal(createQzTransport({ resolveGlobal: () => undefined }).isAvailable(), false);
});

test("print: connects lazily, prints the element to the named printer, no drawer", async () => {
  const { lib, calls, state } = fakeQz({ active: false });
  const transport = createQzTransport({ qz: lib });
  const element = { id: "sheet" };
  const result = await transport.print({ element, printer: "Front", cashDrawer: false });
  assert.equal(calls.connect, 1);
  assert.equal(state.active, true);
  assert.deepEqual(calls.print, [{ config: { type: "html", format: "plain", printer: "Front" }, data: [element] }]);
  assert.deepEqual(result, { ok: true, printer: "Front", cashDrawer: false });
});

test("print: reuses the connection and null printer means the OS/QZ default", async () => {
  const { lib, calls } = fakeQz({ active: true });
  const transport = createQzTransport({ qz: lib });
  await transport.print({ element: { id: "a" } });
  await transport.print({ element: { id: "b" } });
  assert.equal(calls.connect, 0);
  assert.equal(calls.print[0].config.printer, null);
});

test("print: a cash-drawer sale sends the ESC/POS pulse as raw base64", async () => {
  const { lib, calls } = fakeQz({ active: true });
  const transport = createQzTransport({ qz: lib });
  await transport.print({ element: { id: "sheet" }, printer: "Front", cashDrawer: true });
  assert.equal(calls.print.length, 2);
  assert.deepEqual(calls.print[1], {
    config: { type: "raw", format: "plain", printer: "Front" },
    data: [bytesToBase64(CASH_DRAWER_PULSE)],
  });
});

test("print: wires the injected certificate and signature into QZ security", async () => {
  const { lib, calls } = fakeQz({ active: true });
  const transport = createQzTransport({
    qz: lib,
    certificate: async () => "-----BEGIN CERTIFICATE-----",
    sign: async (toSign) => `sig:${toSign}`,
  });
  await transport.print({ element: { id: "sheet" } });
  const certificate = await new Promise((resolve, reject) => calls.certificate(resolve, reject));
  assert.equal(certificate, "-----BEGIN CERTIFICATE-----");
  assert.equal(await calls.signature("payload"), "sig:payload");
});

test("print: rejects when QZ is missing, then retries after the failure", async () => {
  const { lib } = fakeQz({ active: true });
  let available = false;
  const transport = createQzTransport({ resolveGlobal: () => (available ? lib : undefined) });
  await assert.rejects(() => transport.print({ element: { id: "x" } }), /not available/);
  available = true;
  await assert.doesNotReject(() => transport.print({ element: { id: "x" } }));
});

test("loadQzScript: rejects without a document", async () => {
  await assert.rejects(() => loadQzScript("/vendor/qz-tray.js", { doc: null }), /browser document/);
});

test("loadQzScript: injects the tag once and skips when it is already present", async () => {
  const scripts = [];
  const makeDoc = (existing) => ({
    querySelector: () => (existing ? {} : null),
    createElement: () => {
      const el = { dataset: {} };
      Object.defineProperty(el, "onload", { set(fn) { el._onload = fn; }, get() { return el._onload; } });
      Object.defineProperty(el, "onerror", { set(fn) { el._onerror = fn; }, get() { return el._onerror; } });
      return el;
    },
    head: { appendChild: (el) => { scripts.push(el); el.onload?.(); } },
  });
  await loadQzScript("/vendor/qz-tray.js", { doc: makeDoc(false) });
  assert.equal(scripts.length, 1);
  assert.equal(scripts[0].src, "/vendor/qz-tray.js");
  assert.equal(scripts[0].dataset.qzTray, "/vendor/qz-tray.js");
  await loadQzScript("/vendor/qz-tray.js", { doc: makeDoc(true) });
  assert.equal(scripts.length, 1, "an existing tag must not be injected twice");
});

test("bytesToBase64: encodes the drawer pulse and tolerates junk", () => {
  assert.equal(bytesToBase64(CASH_DRAWER_PULSE), "G3AAGfo=");
  assert.equal(bytesToBase64(null), "");
  assert.equal(bytesToBase64([200, 300]), "yCw=");
});
