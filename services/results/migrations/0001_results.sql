CREATE TABLE experiment_versions (
  experiment_id TEXT NOT NULL,
  experiment_version TEXT NOT NULL,
  protocol_sha256 TEXT NOT NULL CHECK(length(protocol_sha256) = 64),
  title TEXT NOT NULL,
  registered_at INTEGER NOT NULL,
  revoked_at INTEGER,
  PRIMARY KEY (experiment_id, experiment_version),
  UNIQUE (experiment_id, experiment_version, protocol_sha256)
);

CREATE TABLE invitations (
  code_hash TEXT PRIMARY KEY CHECK(length(code_hash) = 64),
  experiment_id TEXT NOT NULL,
  experiment_version TEXT NOT NULL,
  protocol_sha256 TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  expires_at INTEGER,
  revoked_at INTEGER,
  FOREIGN KEY (experiment_id, experiment_version, protocol_sha256)
    REFERENCES experiment_versions(experiment_id, experiment_version, protocol_sha256)
);

CREATE TABLE devices (
  device_id TEXT PRIMARY KEY,
  token_hash TEXT NOT NULL UNIQUE CHECK(length(token_hash) = 64),
  experiment_id TEXT NOT NULL,
  experiment_version TEXT NOT NULL,
  protocol_sha256 TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  revoked_at INTEGER,
  FOREIGN KEY (experiment_id, experiment_version, protocol_sha256)
    REFERENCES experiment_versions(experiment_id, experiment_version, protocol_sha256)
);

CREATE TABLE reports (
  experiment_id TEXT NOT NULL,
  report_id TEXT NOT NULL,
  experiment_version TEXT NOT NULL,
  protocol_sha256 TEXT NOT NULL,
  device_id TEXT NOT NULL REFERENCES devices(device_id),
  sha256 TEXT NOT NULL CHECK(length(sha256) = 64),
  received_at TEXT NOT NULL,
  payload TEXT NOT NULL CHECK(json_valid(payload)),
  PRIMARY KEY (experiment_id, report_id),
  FOREIGN KEY (experiment_id, experiment_version, protocol_sha256)
    REFERENCES experiment_versions(experiment_id, experiment_version, protocol_sha256)
);
CREATE INDEX reports_cohort ON reports(experiment_id, experiment_version, protocol_sha256, device_id);

CREATE TABLE request_limits (
  bucket TEXT PRIMARY KEY,
  attempts INTEGER NOT NULL,
  expires_at INTEGER NOT NULL
);
CREATE INDEX request_limits_expiry ON request_limits(expires_at);
