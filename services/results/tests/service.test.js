import assert from "node:assert/strict";
import { randomBytes, randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";
import test from "node:test";
import { handleRequest } from "../src/index.js";
import { sha256 } from "../src/http.js";
import { registrationSql } from "../scripts/register.mjs";

class LocalD1 {
  constructor() {
    this.sqlite = new DatabaseSync(":memory:");
    this.sqlite.exec("PRAGMA foreign_keys = ON");
    this.sqlite.exec(readFileSync(new URL("../migrations/0001_results.sql", import.meta.url), "utf8"));
    this.failReportInsert = false;
    this.beforeReportInsert = null;
    this.beforeDeviceInsert = null;
  }
  prepare(sql) {
    const database = this.sqlite;
    const adapter = this;
    let values = [];
    return {
      bind(...parameters) { values = parameters; return this; },
      async first() { return database.prepare(sql).get(...values) ?? null; },
      async run() {
        if (adapter.failReportInsert && sql.startsWith("INSERT INTO reports")) throw new Error("Synthetic database failure");
        if (adapter.beforeReportInsert && sql.startsWith("INSERT INTO reports")) adapter.beforeReportInsert();
        if (adapter.beforeDeviceInsert && sql.startsWith("INSERT INTO devices")) adapter.beforeDeviceInsert();
        return { success: true, meta: database.prepare(sql).run(...values) };
      },
      all() { return { success: true, results: database.prepare(sql).all(...values) }; },
    };
  }
  async batch(statements) {
    this.sqlite.exec("BEGIN");
    try {
      const results = statements.map(statement => statement.all());
      this.sqlite.exec("COMMIT");
      return results;
    } catch (error) {
      this.sqlite.exec("ROLLBACK");
      throw error;
    }
  }
}

function applyRegistration(database, sql) {
  // Mirror D1's execution transaction instead of emitting BEGIN/COMMIT in its SQL.
  database.exec("BEGIN");
  try {
    database.exec(sql);
    database.exec("COMMIT");
  } catch (error) {
    database.exec("ROLLBACK");
    throw error;
  }
}

async function setup(t) {
  const env = { DB: new LocalD1(), RESULTS_ORIGIN: "https://results.example" };
  const origin = env.RESULTS_ORIGIN;
  t.after(() => env.DB.sqlite.close());
  const run = request => handleRequest(request, env);
  const scope = { experiment_id: "test-faces", experiment_version: "1.0.0", protocol_sha256: "a".repeat(64) };
  let addressIndex = 0;
  async function register(identity = scope) {
    const code = `synthetic-invitation-${identity.experiment_id}-${identity.experiment_version}`;
    applyRegistration(env.DB.sqlite, registrationSql({
      "experiment-id": identity.experiment_id, "experiment-version": identity.experiment_version,
      "protocol-sha256": identity.protocol_sha256, title: "Synthetic fixation study",
      "invitation-code-sha256": await sha256(code),
    }));
    return code;
  }
  const code = await register();
  function client(identity = scope, invitation = code, token = randomBytes(32).toString("hex")) {
    const ip = `192.0.2.${++addressIndex}`;
    function request(path, method = "GET", body, headers = {}) {
      return new Request(`${origin}${path}`, {
        method, headers: { Authorization: `Bearer ${token}`, "CF-Connecting-IP": ip,
          "Content-Type": "application/json", ...headers },
        body: body === undefined ? undefined : typeof body === "string" ? body : JSON.stringify(body),
      });
    }
    const enrollment = (changed = {}) => request("/v1/enroll", "POST", {
      schema_version: "1.0", code: invitation, device_token: token, protocol_sha256: identity.protocol_sha256, ...changed,
    });
    const send = report => run(request(`/v1/experiments/${identity.experiment_id}/reports`, "POST", report));
    const comparison = (body = { schema_version: "1.0" }) => run(request(`/v1/experiments/${identity.experiment_id}/comparison`, "POST", body));
    return { identity, token, request, enrollment, send, comparison, async enroll() {
      const response = await run(enrollment());
      assert.equal(response.status, 200, await response.clone().text());
      return response.json();
    } };
  }
  return { env, scope, code, run, register, client };
}

function occurrence(changed = {}) {
  return { condition_id: "faces", occurrence_index: 1, total_targets: 10, hit_count: 8,
    miss_count: 2, false_alarm_count: 1, accuracy_percent: 80, mean_rt_ms: 300, rt_count: 8,
    scoring_source: "timestamps", refresh_hz: 60, response_window_ms: 1000, ...changed };
}

function report(scope, rows = [occurrence()], changes = {}) {
  return { schema_version: "1.0", report_id: randomUUID(), ...scope, completed_at: "2026-10-05T14:00:00.000Z",
    studio_version: "2.2.0", occurrences: rows, ...changes };
}

async function sendReports(clients, count, rows) {
  for (let index = 0; index < count; index++) {
    const client = clients[index % clients.length];
    const response = await client.send(report(client.identity, typeof rows === "function" ? rows(index) : rows));
    assert.equal(response.status, 200, await response.clone().text());
  }
}

test("enrollment is scoped, idempotent after a lost response, and stores only hashes", async t => {
  const { env, scope, run, client } = await setup(t);
  const device = client();
  assert.equal((await run(device.enrollment({ code: "invalid" }))).status, 403);
  assert.equal((await run(device.enrollment({ protocol_sha256: "b".repeat(64) }))).status, 409);
  const first = await device.enroll();
  assert.deepEqual(await device.enroll(), first);
  assert.deepEqual(Object.keys(first).sort(), ["schema_version", "experiment_id", "experiment_version", "protocol_sha256", "title", "device_id"].sort());
  assert.equal(first.experiment_id, scope.experiment_id);
  const stored = env.DB.sqlite.prepare("SELECT * FROM devices").get();
  assert.equal(stored.token_hash, await sha256(device.token));
  assert.ok(!JSON.stringify(stored).includes(device.token));
  assert.equal(env.DB.sqlite.prepare("SELECT COUNT(*) n FROM devices").get().n, 1);
});

test("expected enrollment identity is paired, strict and rejects a wrong invitation before token creation", async t => {
  for (const wrongScope of [
    { experiment_id: "other-faces", experiment_version: "1.0.0", protocol_sha256: "a".repeat(64) },
    { experiment_id: "test-faces", experiment_version: "1.1.0", protocol_sha256: "a".repeat(64) },
  ]) {
    const { env, scope, run, register, client } = await setup(t);
    const device = client();
    const expected = { experiment_id: scope.experiment_id, experiment_version: scope.experiment_version };
    const wrongCode = await register(wrongScope);
    const response = await run(device.enrollment({ ...expected, code: wrongCode }));
    assert.equal(response.status, 409);
    assert.deepEqual(await response.json(), { schema_version: "1.0", error: "protocol_mismatch" });
    assert.equal(env.DB.sqlite.prepare("SELECT COUNT(*) n FROM devices").get().n, 0);
    const corrected = await run(device.enrollment(expected));
    assert.equal(corrected.status, 200);
    const profile = await corrected.json();
    assert.equal(profile.experiment_id, scope.experiment_id);
    assert.equal(profile.experiment_version, scope.experiment_version);
    assert.deepEqual(await (await run(device.enrollment(expected))).json(), profile);
    assert.equal(env.DB.sqlite.prepare("SELECT COUNT(*) n FROM devices").get().n, 1);
  }
  const { env, run, client } = await setup(t);
  const device = client();
  for (const fields of [
    { experiment_id: "test-faces" },
    { experiment_version: "1.0.0" },
    { experiment_id: "../invalid", experiment_version: "1.0.0" },
    { experiment_id: "test-faces", experiment_version: "" },
    { experiment_id: "test-faces", experiment_version: "1.0.0", lab_id: "unknown" },
  ]) {
    const response = await run(device.enrollment(fields));
    assert.equal(response.status, 400);
    assert.deepEqual(await response.json(), { schema_version: "1.0", error: "invalid_enrollment" });
  }
  assert.equal(env.DB.sqlite.prepare("SELECT COUNT(*) n FROM devices").get().n, 0);
});

test("shared synthetic wire fixtures match service enrollment, intake and aggregate output", async t => {
  const { client } = await setup(t);
  const device = client();
  const profile = await device.enroll();
  const expectedProfile = JSON.parse(readFileSync(new URL("../fixtures/profile-v1.json", import.meta.url), "utf8"));
  assert.deepEqual({ ...profile, device_id: expectedProfile.device_id }, expectedProfile);
  const raw = readFileSync(new URL("../fixtures/report-v1.json", import.meta.url), "utf8");
  const response = await device.send(raw);
  assert.equal(response.status, 200);
  assert.equal((await response.json()).sha256, await sha256(raw));
  const references = [client(), client(), client()];
  for (const reference of references) await reference.enroll();
  await sendReports(references, 10, index => [occurrence(),
    occurrence({ occurrence_index: 2, mean_rt_ms: 500, rt_count: 2 }),
    ...(index === 0 ? [occurrence({ condition_id: "sparse", occurrence_index: 3 })] : [])]);
  const actual = await (await device.comparison()).json();
  const expected = JSON.parse(readFileSync(new URL("../fixtures/comparison-v1.json", import.meta.url), "utf8"));
  assert.deepEqual({ ...actual, generated_at: expected.generated_at }, expected);
});

test("unknown, revoked and incorrectly scoped credentials cannot submit or compare", async t => {
  const { env, scope, run, register, client } = await setup(t);
  const device = client();
  assert.equal((await device.send(report(scope))).status, 401);
  const profile = await device.enroll();
  assert.equal((await run(device.request("/v1/experiments/other-study/reports", "POST", report(scope)))).status, 403);
  assert.equal((await run(device.request("/v1/experiments/other-study/comparison", "POST", { schema_version: "1.0" }))).status, 403);
  const otherScope = { ...scope, experiment_version: "2.0.0", protocol_sha256: "b".repeat(64) };
  const otherCode = await register(otherScope);
  const reused = client(otherScope, otherCode, device.token);
  assert.equal((await run(reused.enrollment())).status, 409);
  assert.equal((await device.send(report(otherScope))).status, 409);
  assert.equal((await run(device.request("/v1/device", "DELETE"))).status, 200);
  assert.equal((await device.send(report(scope))).status, 403);
  assert.equal((await device.comparison()).status, 403);
  assert.equal((await run(device.enrollment())).status, 403);
  assert.ok(env.DB.sqlite.prepare("SELECT revoked_at FROM devices WHERE device_id = ?").get(profile.device_id).revoked_at !== null);
});

test("disabled/expired invitations and disabled protocol versions fail closed", async t => {
  const { env, run, client } = await setup(t);
  const device = client();
  env.DB.sqlite.exec("UPDATE invitations SET expires_at = 1");
  assert.equal((await run(device.enrollment())).status, 403);
  env.DB.sqlite.exec("UPDATE invitations SET expires_at = NULL, revoked_at = 1");
  assert.equal((await run(device.enrollment())).status, 403);
  env.DB.sqlite.exec("UPDATE invitations SET revoked_at = NULL");
  await device.enroll();
  env.DB.sqlite.exec("UPDATE experiment_versions SET revoked_at = 1");
  assert.equal((await device.comparison()).status, 403);
  assert.equal((await run(client().enrollment())).status, 403);
});

test("revocation or invitation expiry between lookup and enrollment prevents a new device", async t => {
  for (const update of [
    "UPDATE invitations SET revoked_at = 1",
    "UPDATE invitations SET expires_at = 1",
    "UPDATE experiment_versions SET revoked_at = 1",
  ]) {
    const { env, run, client } = await setup(t);
    env.DB.beforeDeviceInsert = () => env.DB.sqlite.exec(update);
    assert.equal((await run(client().enrollment())).status, 403, update);
    assert.equal(env.DB.sqlite.prepare("SELECT COUNT(*) n FROM devices").get().n, 0);
  }
});

test("invitation expiry uses the database execution clock after binding", async t => {
  const { env, run, client } = await setup(t);
  const requestNow = Math.floor(Date.now() / 1000);
  t.mock.method(Date, "now", () => requestNow * 1000);
  let databaseNow = requestNow;
  env.DB.sqlite.function("unixepoch", value => {
    assert.equal(value, "now");
    return databaseNow;
  });
  env.DB.sqlite.prepare("UPDATE invitations SET expires_at = ?").run(requestNow + 1);
  env.DB.beforeDeviceInsert = () => { databaseNow = requestNow + 2; };
  assert.equal((await run(client().enrollment())).status, 403);
  assert.equal(env.DB.sqlite.prepare("SELECT COUNT(*) n FROM devices").get().n, 0);
});

test("intake commits before receipts, retries immutable bytes, and rejects digest/device conflicts", async t => {
  const { env, scope, run, client } = await setup(t);
  const device = client();
  const other = client();
  await device.enroll();
  await other.enroll();
  const payload = report(scope);
  const raw = JSON.stringify(payload);
  env.DB.failReportInsert = true;
  assert.equal((await device.send(raw)).status, 503);
  assert.equal(env.DB.sqlite.prepare("SELECT COUNT(*) n FROM reports").get().n, 0);
  env.DB.failReportInsert = false;
  const first = await (await device.send(raw)).json();
  assert.equal(first.sha256, await sha256(raw));
  assert.equal(env.DB.sqlite.prepare("SELECT payload FROM reports").get().payload, raw);
  assert.deepEqual(await (await device.send(raw)).json(), first);
  assert.equal(env.DB.sqlite.prepare("SELECT COUNT(*) n FROM reports").get().n, 1);
  const receiptPath = `/v1/experiments/${scope.experiment_id}/reports/${payload.report_id}/receipt`;
  assert.deepEqual(await (await run(device.request(receiptPath))).json(), first);
  assert.equal((await run(other.request(receiptPath))).status, 404);
  assert.equal((await device.send(`${raw}\n`)).status, 409);
  assert.equal((await other.send(raw)).status, 409);
  assert.equal((await device.send({ ...payload, studio_version: "2.2.1" })).status, 409);
});

test("concurrent same-ID insertion resolves to one durable receipt", async t => {
  const { env, scope, client } = await setup(t);
  const device = client();
  await device.enroll();
  const payload = report(scope);
  const responses = await Promise.all([device.send(payload), device.send(payload)]);
  assert.ok(responses.every(response => response.status === 200));
  assert.deepEqual(await responses[0].json(), await responses[1].json());
  assert.equal(env.DB.sqlite.prepare("SELECT COUNT(*) n FROM reports").get().n, 1);
});

test("revocation between authentication and commit prevents new report acceptance", async t => {
  for (const target of ["devices", "experiment_versions"]) {
    const { env, scope, client } = await setup(t);
    const device = client();
    await device.enroll();
    env.DB.beforeReportInsert = () => env.DB.sqlite.exec(`UPDATE ${target} SET revoked_at = 1`);
    assert.equal((await device.send(report(scope))).status, 403);
    assert.equal(env.DB.sqlite.prepare("SELECT COUNT(*) n FROM reports").get().n, 0);
  }
});

test("strict fixation fields reject identifiers, inconsistent counts and impossible null semantics", async t => {
  const { env, scope, client } = await setup(t);
  const device = client();
  await device.enroll();
  for (const changed of [
    { participant_id: "100" }, { path: "private" }, { hit_count: true }, { miss_count: 1 },
    { hit_count: -1 }, { false_alarm_count: 1000001 }, { accuracy_percent: 81 },
    { accuracy_percent: null }, { mean_rt_ms: null }, { rt_count: 9 }, { rt_count: 0 },
    { scoring_source: "guessed" }, { refresh_hz: 0 }, { response_window_ms: 600001 },
    { mean_rt_ms: Infinity }, { occurrence_index: 0 }, { condition_id: "../private" },
  ]) {
    assert.equal((await device.send(report(scope, [occurrence(changed)]))).status, 400, JSON.stringify(changed));
  }
  for (const changed of [
    { participant_id: "100" }, { demographics: {} }, { occurrences: [] },
    { report_id: randomUUID().toUpperCase() }, { completed_at: "2026-02-30T14:00:00Z" },
    { completed_at: "2026-10-05T14:00:00-05:00" },
  ]) {
    assert.equal((await device.send(report(scope, undefined, changed))).status, 400, JSON.stringify(changed));
  }
  assert.equal((await device.send(report(scope, [occurrence(), occurrence()]))).status, 400);
  assert.equal(env.DB.sqlite.prepare("SELECT COUNT(*) n FROM reports").get().n, 0);
  const zero = occurrence({ total_targets: 0, hit_count: 0, miss_count: 0, accuracy_percent: null, rt_count: 0, mean_rt_ms: null });
  assert.equal((await device.send(report(scope, [zero]))).status, 200);
  assert.equal((await device.send(report(scope, [occurrence({ hit_count: 0, miss_count: 10, accuracy_percent: 0, rt_count: 0, mean_rt_ms: null })]))).status, 200);
});

test("reads reject oversized streams, malformed UTF-8/JSON and browser or proxy requests", async t => {
  const { env, scope, run, client } = await setup(t);
  const device = client();
  await device.enroll();
  assert.equal((await device.send(" ".repeat(128 * 1024 + 1))).status, 413);
  assert.equal((await device.send("{bad-json")).status, 400);
  assert.equal((await device.send(JSON.stringify(report(scope)).replace('"mean_rt_ms":300', '"mean_rt_ms":1e999'))).status, 400);
  const malformed = new Request(`${env.RESULTS_ORIGIN}/v1/experiments/${scope.experiment_id}/reports`, {
    method: "POST", headers: { Authorization: `Bearer ${device.token}`, "Content-Type": "application/json" },
    body: new Uint8Array([0xff]),
  });
  assert.equal((await run(malformed)).status, 400);
  const stream = new ReadableStream({ start(controller) {
    controller.enqueue(new Uint8Array(128 * 1024));
    controller.enqueue(new Uint8Array(1));
    controller.close();
  } });
  assert.equal((await run(new Request(`${env.RESULTS_ORIGIN}/v1/experiments/${scope.experiment_id}/reports`, {
    method: "POST", headers: { Authorization: `Bearer ${device.token}`, "Content-Type": "application/json", "Content-Length": "1" },
    body: stream, duplex: "half",
  }))).status, 413);
  assert.equal((await run(device.request(`/v1/experiments/${scope.experiment_id}/comparison`, "POST", { schema_version: "1.0" }, { Origin: "https://untrusted.example" }))).status, 403);
  assert.equal((await run(new Request("https://untrusted.example/v1/enroll", { method: "POST" }))).status, 403);
  assert.equal((await run(device.request("/v1/device?proxy=https://untrusted.example", "DELETE"))).status, 403);
  assert.equal((await run(device.request("/v1/enroll", "GET"))).status, 404);
  assert.equal((await run(device.request(`/v1/experiments/${scope.experiment_id}/reports`))).status, 405);
  delete env.RESULTS_ORIGIN;
  assert.equal((await device.comparison()).status, 503);
});

test("duplicate JSON members cannot retain hidden private fields or unvalidated SQL metrics", async t => {
  const { env, scope, client } = await setup(t);
  const device = client();
  await device.enroll();
  const raw = JSON.stringify(report(scope));
  const privateMember = raw.replace('"total_targets":10',
    '"total_targets":{"participant_id":"PRIVATE-SYNTHETIC-ONLY"},"total_targets":10');
  // JavaScript keeps the last member, while SQLite selects the first member.
  assert.equal(JSON.parse(privateMember).occurrences[0].total_targets, 10);
  assert.equal(env.DB.sqlite.prepare("SELECT json_extract(?, '$.occurrences[0].total_targets.participant_id') value")
    .get(privateMember).value, "PRIVATE-SYNTHETIC-ONLY");
  for (const body of [
    privateMember,
    raw.replace('"schema_version":"1.0"', '"schema_version":{"participant_id":"private"},"schema_version":"1.0"'),
    raw.replace('"total_targets":10', '"total_targets":1000001,"total_targets":10'),
    raw.replace('"hit_count":8', '"hit_count":0,"hit_count":8'),
    raw.replace('"schema_version":"1.0"', '"schema_version":"1.0","schema_\\u0076ersion":"1.0"'),
    raw.replace('"condition_id":"faces"', '"condition_id":"faces","condition_\\u0069d":"faces"'),
  ]) {
    const response = await device.send(body);
    assert.equal(response.status, 400);
    assert.deepEqual(await response.json(), { schema_version: "1.0", error: "invalid_json" });
  }
  assert.equal(env.DB.sqlite.prepare("SELECT COUNT(*) n FROM reports").get().n, 0);
  const enrollment = device.enrollment();
  const enrollmentBody = (await enrollment.text()).replace('"code":', '"code":"hidden-private-value","code":');
  const response = await handleRequest(new Request(enrollment.url, {
    method: enrollment.method, headers: enrollment.headers, body: enrollmentBody,
  }), env);
  assert.equal(response.status, 400);
  assert.equal((await device.comparison('{"schema_version":"1.0","schema_version":"1.0"}')).status, 400);
  // Independent objects may reuse field names; accepted bytes and their digest stay exact.
  const valid = ` \n${JSON.stringify(report(scope, [occurrence(), occurrence({ occurrence_index: 2 })]), null, 2)}\n`;
  const receipt = await (await device.send(valid)).json();
  assert.equal(receipt.sha256, await sha256(valid));
  assert.equal(env.DB.sqlite.prepare("SELECT payload FROM reports").get().payload, valid);
  assert.deepEqual(await (await device.send(valid)).json(), receipt);
});

test("enrollment and new-report quotas are bounded; raw errors and cacheable data never leave service", async t => {
  const { env, scope, run, client } = await setup(t);
  const device = client();
  for (let i = 0; i < 10; i++) assert.equal((await run(device.enrollment({ code: "invalid" }))).status, 403);
  assert.equal((await run(device.enrollment())).status, 429);
  const good = client();
  const profile = await good.enroll();
  const window = Math.floor(Date.now() / 1000 / 86400);
  env.DB.sqlite.prepare("INSERT INTO request_limits(bucket, attempts, expires_at) VALUES (?, 240, ?)")
    .run(`reports:${profile.device_id}:${window}`, (window + 1) * 86400);
  assert.equal((await good.send(report(scope))).status, 429);
  env.DB.sqlite.prepare("UPDATE request_limits SET attempts = 0 WHERE bucket = ?").run(`reports:${profile.device_id}:${window}`);
  const payload = report(scope);
  assert.equal((await good.send(payload)).status, 200);
  env.DB.sqlite.prepare("UPDATE request_limits SET attempts = 240 WHERE bucket = ?").run(`reports:${profile.device_id}:${window}`);
  assert.equal((await good.send(payload)).status, 200);
  env.DB.failReportInsert = true;
  env.DB.sqlite.prepare("UPDATE request_limits SET attempts = 0 WHERE bucket = ?").run(`reports:${profile.device_id}:${window}`);
  const response = await good.send(report(scope));
  assert.equal(response.status, 503);
  assert.equal(response.headers.get("Cache-Control"), "no-store");
  assert.deepEqual(await response.json(), { schema_version: "1.0", error: "service_unavailable" });
});

test("comparison always excludes requester, counts sessions once, weights RT and suppresses sparse conditions", async t => {
  const { scope, client } = await setup(t);
  const requester = client();
  const references = [client(), client(), client()];
  await requester.enroll();
  for (const device of references) await device.enroll();
  await sendReports([requester], 10, [occurrence({ hit_count: 0, miss_count: 10, accuracy_percent: 0, rt_count: 0, mean_rt_ms: null })]);
  assert.deepEqual((await (await requester.comparison()).json()).conditions, []);
  await sendReports(references, 9, [occurrence(), occurrence({ occurrence_index: 2, mean_rt_ms: 500, rt_count: 2 }),
    occurrence({ condition_id: "disabled", occurrence_index: 3, total_targets: 0, hit_count: 0, miss_count: 0, accuracy_percent: null, mean_rt_ms: null, rt_count: 0 })]);
  const sparse = (await (await requester.comparison()).json()).conditions[0];
  assert.deepEqual(sparse, { condition_id: "faces", session_count: 9, device_count: 3, eligible: false,
    total_targets: null, hit_count: null, accuracy_percent: null, mean_rt_ms: null, rt_count: null,
    scoring_source: null, response_window_ms: null });
  await sendReports(references, 1, [occurrence(), occurrence({ occurrence_index: 2, mean_rt_ms: 500, rt_count: 2 }),
    occurrence({ condition_id: "sparse", occurrence_index: 3 })]);
  const snapshot = await (await requester.comparison()).json();
  assert.equal(snapshot.minimum_sessions, 10);
  assert.equal(snapshot.minimum_devices, 3);
  assert.deepEqual(snapshot.conditions[0], { condition_id: "faces", session_count: 10, device_count: 3,
    eligible: true, total_targets: 200, hit_count: 160, accuracy_percent: 80, mean_rt_ms: 340, rt_count: 100,
    scoring_source: "timestamps", response_window_ms: 1000 });
  assert.equal(snapshot.conditions[1].eligible, false);
  assert.equal(snapshot.conditions[1].total_targets, null);
  assert.ok(!JSON.stringify(snapshot).includes("device_id"));
  assert.ok(!JSON.stringify(snapshot).includes("report_id"));
  assert.ok(!JSON.stringify(snapshot).includes("received_at"));
  assert.equal((await requester.comparison({ schema_version: "1.0", exclude_report_ids: [] })).status, 400);
});

test("ten sessions from one or two devices remain suppressed", async t => {
  const { client } = await setup(t);
  const requester = client();
  const references = [client(), client()];
  await requester.enroll();
  for (const device of references) await device.enroll();
  await sendReports([references[0]], 10, [occurrence()]);
  let row = (await (await requester.comparison()).json()).conditions[0];
  assert.equal(row.session_count, 10);
  assert.equal(row.device_count, 1);
  assert.equal(row.eligible, false);
  await sendReports([references[1]], 1, [occurrence()]);
  row = (await (await requester.comparison()).json()).conditions[0];
  assert.equal(row.device_count, 2);
  assert.equal(row.total_targets, null);
});

test("different registered versions/protocols are isolated even when experiment and conditions match", async t => {
  const { scope, register, client } = await setup(t);
  const alternate = { ...scope, experiment_version: "2.0.0", protocol_sha256: "b".repeat(64) };
  const alternateCode = await register(alternate);
  const requester = client();
  const references = [client(alternate, alternateCode), client(alternate, alternateCode), client(alternate, alternateCode)];
  await requester.enroll();
  for (const device of references) await device.enroll();
  await sendReports(references, 10, [occurrence()]);
  assert.deepEqual((await (await requester.comparison()).json()).conditions, []);
});

test("mixed scoring sources/windows suppress aggregate metrics while valid observations are retained", async t => {
  const { env, client } = await setup(t);
  const requester = client();
  const references = [client(), client(), client()];
  await requester.enroll();
  for (const device of references) await device.enroll();
  await sendReports(references, 10, index => [occurrence(),
    occurrence({ condition_id: "mixed", occurrence_index: 2 }),
    occurrence({ condition_id: "mixed", occurrence_index: 3, scoring_source: index === 0 ? "frames" : "timestamps" }),
    occurrence({ condition_id: "window", occurrence_index: 4, response_window_ms: index === 0 ? 900 : 1000 })]);
  const rows = (await (await requester.comparison()).json()).conditions;
  assert.equal(rows[0].eligible, true);
  for (const row of rows.slice(1)) {
    assert.equal(row.session_count, 10);
    assert.equal(row.device_count, 3);
    assert.equal(row.eligible, false);
    assert.equal(row.hit_count, null);
    assert.equal(row.mean_rt_ms, null);
    assert.equal(row.scoring_source, null);
    assert.equal(row.response_window_ms, null);
  }
  assert.equal(env.DB.sqlite.prepare("SELECT COUNT(*) n FROM reports").get().n, 10);
});

test("no-hit reference keeps zero accuracy and null RT distinct from unavailable cohort metrics", async t => {
  const { client } = await setup(t);
  const requester = client();
  const references = [client(), client(), client()];
  await requester.enroll();
  for (const device of references) await device.enroll();
  await sendReports(references, 10, [occurrence({ hit_count: 0, miss_count: 10, accuracy_percent: 0, rt_count: 0, mean_rt_ms: null })]);
  const row = (await (await requester.comparison()).json()).conditions[0];
  assert.equal(row.eligible, true);
  assert.equal(row.accuracy_percent, 0);
  assert.equal(row.rt_count, 0);
  assert.equal(row.mean_rt_ms, null);
});

test("registration generates scoped SQL without overwriting existing identity or exposing invitation/token", async t => {
  const { env, scope } = await setup(t);
  const values = { "experiment-id": "apostrophe-study", "experiment-version": "1.0.0",
    "protocol-sha256": "c".repeat(64), "invitation-code-sha256": "d".repeat(64), title: "Lab's fixation study" };
  const sql = registrationSql(values, 1);
  assert.ok(!sql.includes("BEGIN") && !sql.includes("COMMIT"));
  applyRegistration(env.DB.sqlite, sql);
  assert.equal(env.DB.sqlite.prepare("SELECT title FROM experiment_versions WHERE experiment_id = ?").get("apostrophe-study").title, values.title);
  assert.throws(() => applyRegistration(env.DB.sqlite, sql), /UNIQUE constraint/);
  assert.throws(() => applyRegistration(env.DB.sqlite, registrationSql({ ...values, "experiment-id": "failed-registration" })), /UNIQUE constraint/);
  assert.equal(env.DB.sqlite.prepare("SELECT COUNT(*) n FROM experiment_versions WHERE experiment_id = 'failed-registration'").get().n, 0);
  assert.throws(() => registrationSql({ ...values, "experiment-id": "../unsafe" }));
  assert.throws(() => registrationSql({ ...values, "protocol-sha256": "invalid" }));
  assert.equal(env.DB.sqlite.prepare("SELECT protocol_sha256 FROM experiment_versions WHERE experiment_id = ?").get(scope.experiment_id).protocol_sha256, scope.protocol_sha256);
});
