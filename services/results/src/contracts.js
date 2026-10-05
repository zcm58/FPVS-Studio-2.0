import { ServiceError } from "./http.js";

export const ID = /^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$/;
export const VERSION = /^[A-Za-z0-9][A-Za-z0-9._+-]{0,63}$/;
export const HASH = /^[a-f0-9]{64}$/;
export const UUID = /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/;
export const MAX_REPORT_BYTES = 128 * 1024;

export function exactObject(value, fields) {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    && Object.keys(value).length === fields.length
    && fields.every(field => Object.hasOwn(value, field));
}

function validString(value, pattern) {
  return typeof value === "string" && pattern.test(value);
}

function count(value, maximum = 1000000, minimum = 0) {
  return Number.isInteger(value) && value >= minimum && value <= maximum;
}

function finite(value, minimum, maximum) {
  return typeof value === "number" && Number.isFinite(value) && value >= minimum && value <= maximum;
}

export function validateEnrollment(body) {
  if (!exactObject(body, ["schema_version", "code", "device_token", "protocol_sha256"])
      || body.schema_version !== "1.0" || typeof body.code !== "string"
      || body.code.length < 1 || body.code.length > 128 || /[\x00-\x20\x7f]/.test(body.code)
      || !validString(body.device_token, HASH) || !validString(body.protocol_sha256, HASH)) {
    throw new ServiceError(400, "invalid_enrollment");
  }
  return body;
}

export function validateReport(body) {
  if (!exactObject(body, ["schema_version", "report_id", "experiment_id", "experiment_version",
    "protocol_sha256", "completed_at", "studio_version", "occurrences"])
      || body.schema_version !== "1.0" || !validString(body.report_id, UUID)
      || !validString(body.experiment_id, ID) || !validString(body.experiment_version, VERSION)
      || !validString(body.protocol_sha256, HASH) || !validString(body.studio_version, VERSION)
      || typeof body.completed_at !== "string"
      || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)$/.test(body.completed_at)
      || !Number.isFinite(Date.parse(body.completed_at))
      || new Date(body.completed_at).toISOString().slice(0, 19) !== body.completed_at.slice(0, 19)
      || !Array.isArray(body.occurrences) || body.occurrences.length < 1 || body.occurrences.length > 4096) {
    throw new ServiceError(400, "invalid_report");
  }
  const indices = new Set();
  const conditions = new Set();
  for (const row of body.occurrences) {
    if (!exactObject(row, ["condition_id", "occurrence_index", "total_targets", "hit_count", "miss_count",
      "false_alarm_count", "accuracy_percent", "mean_rt_ms", "rt_count", "scoring_source",
      "refresh_hz", "response_window_ms"])
        || !validString(row.condition_id, ID) || !count(row.occurrence_index, 4096, 1)
        || indices.has(row.occurrence_index) || !count(row.total_targets) || !count(row.hit_count)
        || !count(row.miss_count) || !count(row.false_alarm_count) || !count(row.rt_count)
        || row.hit_count + row.miss_count !== row.total_targets || row.rt_count > row.hit_count
        || !["timestamps", "frames"].includes(row.scoring_source)
        || !finite(row.refresh_hz, 1, 1000) || !finite(row.response_window_ms, 0, 600000)
        || (row.rt_count === 0 ? row.mean_rt_ms !== null : !finite(row.mean_rt_ms, 0, 600000))
        || (row.total_targets === 0 ? row.accuracy_percent !== null
          : !finite(row.accuracy_percent, 0, 100)
            || Math.abs(row.accuracy_percent - 100 * row.hit_count / row.total_targets) > 1e-6)) {
      throw new ServiceError(400, "invalid_fixation_metrics");
    }
    indices.add(row.occurrence_index);
    conditions.add(row.condition_id);
  }
  if (conditions.size > 512) throw new ServiceError(400, "too_many_conditions");
  return body;
}

export function validateComparison(body) {
  if (!exactObject(body, ["schema_version"]) || body.schema_version !== "1.0") {
    throw new ServiceError(400, "invalid_comparison");
  }
}
