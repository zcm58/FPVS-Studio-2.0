import { MAX_REPORT_BYTES, validateComparison, validateReport } from "./contracts.js";
import { quota } from "./auth.js";
import { ServiceError, readJson, sha256 } from "./http.js";

function receipt(row) {
  return {
    schema_version: "1.0", report_id: row.report_id, experiment_id: row.experiment_id,
    experiment_version: row.experiment_version, protocol_sha256: row.protocol_sha256,
    sha256: row.sha256, received_at: row.received_at,
  };
}

export async function ingest(request, env, device) {
  const { value, text, bytes } = await readJson(request, MAX_REPORT_BYTES);
  const report = validateReport(value);
  if (report.experiment_id !== device.experiment_id || report.experiment_version !== device.experiment_version
      || report.protocol_sha256 !== device.protocol_sha256) {
    throw new ServiceError(409, "protocol_mismatch");
  }
  const digest = await sha256(bytes);
  const existing = await env.DB.prepare("SELECT * FROM reports WHERE experiment_id = ? AND report_id = ?")
    .bind(device.experiment_id, report.report_id).first();
  if (existing) return existingReceipt(existing, device, digest);
  await quota(env.DB, [{ key: `reports:${device.device_id}`, duration: 86400, maximum: 240 }]);
  // A single INSERT is durable before receipt construction. Concurrent retries resolve
  // through the same unique key and re-read the winner rather than replacing its bytes.
  await env.DB.prepare(`INSERT INTO reports(experiment_id, report_id, experiment_version, protocol_sha256,
    device_id, sha256, received_at, payload)
    SELECT ?, ?, ?, ?, ?, ?, ?, ? FROM devices d JOIN experiment_versions v
      USING (experiment_id, experiment_version, protocol_sha256)
    WHERE d.device_id = ? AND d.experiment_id = ? AND d.experiment_version = ? AND d.protocol_sha256 = ?
      AND d.revoked_at IS NULL AND v.revoked_at IS NULL
    ON CONFLICT(experiment_id, report_id) DO NOTHING`)
    .bind(report.experiment_id, report.report_id, report.experiment_version, report.protocol_sha256,
      device.device_id, digest, new Date().toISOString(), text, device.device_id,
      device.experiment_id, device.experiment_version, device.protocol_sha256).run();
  const committed = await env.DB.prepare("SELECT * FROM reports WHERE experiment_id = ? AND report_id = ?")
    .bind(device.experiment_id, report.report_id).first();
  if (!committed) throw new ServiceError(403, "device_revoked");
  return existingReceipt(committed, device, digest);
}

function existingReceipt(row, device, digest) {
  if (row.device_id !== device.device_id || row.sha256 !== digest
      || row.experiment_version !== device.experiment_version || row.protocol_sha256 !== device.protocol_sha256) {
    throw new ServiceError(409, "report_conflict");
  }
  return receipt(row);
}

export async function getReceipt(env, device, reportId) {
  const row = await env.DB.prepare(`SELECT experiment_id, report_id, experiment_version, protocol_sha256,
    sha256, received_at FROM reports WHERE experiment_id = ? AND report_id = ? AND device_id = ?
    AND experiment_version = ? AND protocol_sha256 = ?`)
    .bind(device.experiment_id, reportId, device.device_id, device.experiment_version, device.protocol_sha256).first();
  if (!row) throw new ServiceError(404, "receipt_not_found");
  return receipt(row);
}

const MINIMUM_SESSIONS = 10;
const MINIMUM_DEVICES = 3;

export async function compare(request, env, device) {
  validateComparison((await readJson(request, 1024)).value);
  const data = await env.DB.prepare(`WITH per_report AS (
    SELECT r.report_id, r.device_id,
      json_extract(o.value, '$.condition_id') AS condition_id,
      SUM(json_extract(o.value, '$.total_targets')) AS targets,
      SUM(json_extract(o.value, '$.hit_count')) AS hits,
      SUM(json_extract(o.value, '$.rt_count')) AS rt_count,
      SUM(COALESCE(json_extract(o.value, '$.mean_rt_ms'), 0) * json_extract(o.value, '$.rt_count')) AS rt_sum,
      MIN(json_extract(o.value, '$.scoring_source')) AS source_min,
      MAX(json_extract(o.value, '$.scoring_source')) AS source_max,
      MIN(json_extract(o.value, '$.response_window_ms')) AS window_min,
      MAX(json_extract(o.value, '$.response_window_ms')) AS window_max
    FROM reports r JOIN json_each(r.payload, '$.occurrences') o
    WHERE r.experiment_id = ? AND r.experiment_version = ? AND r.protocol_sha256 = ?
      AND r.device_id <> ? AND json_extract(o.value, '$.total_targets') > 0
    GROUP BY r.report_id, r.device_id, condition_id
  ) SELECT condition_id, COUNT(*) AS session_count, COUNT(DISTINCT device_id) AS device_count,
    SUM(targets) AS total_targets, SUM(hits) AS hit_count, SUM(rt_count) AS rt_count, SUM(rt_sum) AS rt_sum,
    MIN(source_min) AS source_min, MAX(source_max) AS source_max,
    MIN(window_min) AS window_min, MAX(window_max) AS window_max
    FROM per_report GROUP BY condition_id ORDER BY condition_id LIMIT 513`)
    .bind(device.experiment_id, device.experiment_version, device.protocol_sha256, device.device_id).all();
  if (data.results.length > 512) throw new ServiceError(503, "cohort_condition_limit");
  const conditions = data.results.map(row => {
    const eligible = row.session_count >= MINIMUM_SESSIONS && row.device_count >= MINIMUM_DEVICES
      && row.source_min === row.source_max && row.window_min === row.window_max;
    return {
      condition_id: row.condition_id, session_count: row.session_count, device_count: row.device_count, eligible,
      total_targets: eligible ? row.total_targets : null, hit_count: eligible ? row.hit_count : null,
      accuracy_percent: eligible ? 100 * row.hit_count / row.total_targets : null,
      mean_rt_ms: eligible && row.rt_count > 0 ? row.rt_sum / row.rt_count : null,
      rt_count: eligible ? row.rt_count : null,
      scoring_source: eligible ? row.source_min : null,
      response_window_ms: eligible ? row.window_min : null,
    };
  });
  return {
    schema_version: "1.0", experiment_id: device.experiment_id,
    experiment_version: device.experiment_version, protocol_sha256: device.protocol_sha256,
    minimum_sessions: MINIMUM_SESSIONS, minimum_devices: MINIMUM_DEVICES,
    conditions, generated_at: new Date().toISOString(),
  };
}
