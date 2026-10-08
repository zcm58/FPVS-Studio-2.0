import { HASH, validateEnrollment } from "./contracts.js";
import { ServiceError, readJson, sha256 } from "./http.js";

export async function quota(db, buckets, now = Math.floor(Date.now() / 1000)) {
  const statements = [db.prepare("DELETE FROM request_limits WHERE expires_at < ?").bind(now)];
  for (const { key, duration } of buckets) {
    const window = Math.floor(now / duration);
    statements.push(db.prepare(`INSERT INTO request_limits(bucket, attempts, expires_at) VALUES (?, 1, ?)
      ON CONFLICT(bucket) DO UPDATE SET attempts = attempts + 1 RETURNING attempts`)
      .bind(`${key}:${window}`, (window + 1) * duration));
  }
  const result = await db.batch(statements);
  if (buckets.some((bucket, i) => result[i + 1].results[0].attempts > bucket.maximum)) {
    throw new ServiceError(429, "rate_limited");
  }
}

export async function enroll(request, env) {
  const now = Math.floor(Date.now() / 1000);
  const ip = request.headers.get("CF-Connecting-IP");
  if (!ip) throw new ServiceError(403, "client_address_required");
  // Fixed hash slots bound table growth; collisions share limits and fail closed.
  const slot = parseInt((await sha256(ip)).slice(0, 4), 16) % 4096;
  await quota(env.DB, [
    { key: `enroll:${slot}`, duration: 600, maximum: 10 },
    { key: "enroll:global", duration: 600, maximum: 1000 },
  ], now);
  const body = validateEnrollment((await readJson(request, 2048)).value);
  const invitationHash = await sha256(body.code);
  const invitation = await env.DB.prepare(`SELECT i.*, v.title, v.revoked_at AS version_revoked_at
    FROM invitations i JOIN experiment_versions v USING (experiment_id, experiment_version, protocol_sha256)
    WHERE i.code_hash = ?`).bind(invitationHash).first();
  if (!invitation || invitation.revoked_at !== null || invitation.version_revoked_at !== null
      || invitation.expires_at !== null && invitation.expires_at <= now) {
    throw new ServiceError(403, "invalid_invitation");
  }
  if (invitation.protocol_sha256 !== body.protocol_sha256 || body.experiment_id !== undefined
      && (invitation.experiment_id !== body.experiment_id || invitation.experiment_version !== body.experiment_version)) {
    throw new ServiceError(409, "protocol_mismatch");
  }
  const tokenHash = await sha256(body.device_token);
  // Recheck invitation/version status atomically with creation, including expiry during the request.
  await env.DB.prepare(`INSERT INTO devices(device_id, token_hash, experiment_id, experiment_version,
    protocol_sha256, created_at) SELECT ?, ?, ?, ?, ?, ? FROM invitations i JOIN experiment_versions v
      USING (experiment_id, experiment_version, protocol_sha256)
    WHERE i.code_hash = ? AND i.experiment_id = ? AND i.experiment_version = ? AND i.protocol_sha256 = ?
      AND i.revoked_at IS NULL AND v.revoked_at IS NULL AND (i.expires_at IS NULL OR i.expires_at > unixepoch('now'))
    ON CONFLICT(token_hash) DO NOTHING`)
    .bind(crypto.randomUUID(), tokenHash, invitation.experiment_id, invitation.experiment_version,
      invitation.protocol_sha256, now, invitationHash, invitation.experiment_id, invitation.experiment_version,
      invitation.protocol_sha256).run();
  const device = await env.DB.prepare("SELECT * FROM devices WHERE token_hash = ?").bind(tokenHash).first();
  if (!device || device.revoked_at !== null) throw new ServiceError(403, "device_revoked");
  if (device.experiment_id !== invitation.experiment_id || device.experiment_version !== invitation.experiment_version
      || device.protocol_sha256 !== invitation.protocol_sha256) {
    throw new ServiceError(409, "credential_scope_conflict");
  }
  return {
    schema_version: "1.0", experiment_id: device.experiment_id,
    experiment_version: device.experiment_version, protocol_sha256: device.protocol_sha256,
    title: invitation.title, device_id: device.device_id,
  };
}

export async function authenticate(request, env, experimentId) {
  const authorization = request.headers.get("Authorization") ?? "";
  if (!authorization.startsWith("Bearer ") || !HASH.test(authorization.slice(7))) {
    throw new ServiceError(401, "authentication_required");
  }
  const device = await env.DB.prepare(`SELECT d.*, v.revoked_at AS version_revoked_at
    FROM devices d JOIN experiment_versions v USING (experiment_id, experiment_version, protocol_sha256)
    WHERE d.token_hash = ?`).bind(await sha256(authorization.slice(7))).first();
  if (!device) throw new ServiceError(401, "unknown_device");
  if (device.revoked_at !== null || device.version_revoked_at !== null) {
    throw new ServiceError(403, "device_revoked");
  }
  if (experimentId !== undefined && device.experiment_id !== experimentId) {
    throw new ServiceError(403, "experiment_scope_denied");
  }
  await quota(env.DB, [{ key: `requests:${device.device_id}`, duration: 60, maximum: 60 }]);
  return device;
}

export async function revoke(env, device) {
  await env.DB.prepare("UPDATE devices SET revoked_at = ? WHERE device_id = ? AND revoked_at IS NULL")
    .bind(Math.floor(Date.now() / 1000), device.device_id).run();
  return { schema_version: "1.0", revoked: true };
}
