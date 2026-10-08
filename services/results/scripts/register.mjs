import { parseArgs } from "node:util";
import { fileURLToPath } from "node:url";
import { HASH, ID, VERSION } from "../src/contracts.js";

export function registrationSql(values, now = Math.floor(Date.now() / 1000)) {
  const id = values["experiment-id"];
  const version = values["experiment-version"];
  const protocol = values["protocol-sha256"];
  const invitationHash = values["invitation-code-sha256"];
  const title = values.title;
  if (!ID.test(id ?? "") || !VERSION.test(version ?? "") || !HASH.test(protocol ?? "")
      || !HASH.test(invitationHash ?? "") || typeof title !== "string" || !title.trim()
      || title.length > 160 || /[\x00-\x1f\x7f]/.test(title)) {
    throw new Error("Invalid registration fields.");
  }
  const quote = value => `'${value.replaceAll("'", "''")}'`;
  // No UPDATE/REPLACE: registering an existing identity must fail, never relabel data.
  // D1 owns the transaction boundary; explicit BEGIN/COMMIT are unsupported there.
  return `INSERT INTO experiment_versions(experiment_id, experiment_version, protocol_sha256, title, registered_at)
VALUES (${quote(id)}, ${quote(version)}, ${quote(protocol)}, ${quote(title)}, ${now});
INSERT INTO invitations(code_hash, experiment_id, experiment_version, protocol_sha256, created_at)
VALUES (${quote(invitationHash)}, ${quote(id)}, ${quote(version)}, ${quote(protocol)}, ${now});
`;
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  try {
    const { values } = parseArgs({ options: Object.fromEntries([
      "experiment-id", "experiment-version", "protocol-sha256", "invitation-code-sha256", "title",
    ].map(name => [name, { type: "string" }])), strict: true });
    process.stdout.write(registrationSql(values));
  } catch {
    process.stderr.write("Registration requires valid experiment-id, experiment-version, protocol-sha256, title and invitation-code-sha256.\n");
    process.exitCode = 1;
  }
}
