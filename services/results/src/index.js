import { authenticate, enroll, revoke } from "./auth.js";
import { ID, UUID } from "./contracts.js";
import { ServiceError, jsonResponse } from "./http.js";
import { compare, getReceipt, ingest } from "./reports.js";

export async function handleRequest(request, env) {
  try {
    let origin;
    try { origin = new URL(env.RESULTS_ORIGIN); } catch { throw new ServiceError(503, "service_unconfigured"); }
    if (!env.DB || origin.protocol !== "https:" || origin.username || origin.password
        || origin.pathname !== "/" || origin.search || origin.hash) {
      throw new ServiceError(503, "service_unconfigured");
    }
    const url = new URL(request.url);
    if (url.origin !== origin.origin || url.search || request.headers.has("Origin")) {
      throw new ServiceError(403, "origin_denied");
    }
    if (url.pathname === "/v1/enroll" && request.method === "POST") {
      return jsonResponse(await enroll(request, env));
    }
    if (url.pathname === "/v1/device" && request.method === "DELETE") {
      return jsonResponse(await revoke(env, await authenticate(request, env)));
    }
    const match = /^\/v1\/experiments\/([^/]+)\/(reports|comparison)(?:\/([^/]+)\/receipt)?$/.exec(url.pathname);
    if (!match || !ID.test(match[1]) || match[3] && !UUID.test(match[3])) {
      throw new ServiceError(404, "route_not_found");
    }
    if (match[2] === "comparison" && !match[3] && request.method === "POST") {
      return jsonResponse(await compare(request, env, await authenticate(request, env, match[1])));
    }
    if (match[2] === "reports" && !match[3] && request.method === "POST") {
      return jsonResponse(await ingest(request, env, await authenticate(request, env, match[1])));
    }
    if (match[2] === "reports" && match[3] && request.method === "GET") {
      return jsonResponse(await getReceipt(env, await authenticate(request, env, match[1]), match[3]));
    }
    throw new ServiceError(405, "method_not_allowed");
  } catch (error) {
    if (error instanceof ServiceError) return jsonResponse({ schema_version: "1.0", error: error.code }, error.status);
    // Never return SQL messages, payloads, credentials, IP addresses or stack traces.
    return jsonResponse({ schema_version: "1.0", error: "service_unavailable" }, 503);
  }
}

export default { fetch: handleRequest };
