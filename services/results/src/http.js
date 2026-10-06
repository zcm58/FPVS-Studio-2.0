export class ServiceError extends Error {
  constructor(status, code) {
    super(code);
    this.status = status;
    this.code = code;
  }
}

export function jsonResponse(body, status = 200) {
  return Response.json(body, {
    status,
    headers: {
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
      "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    },
  });
}

function rejectDuplicateMembers(text) {
  // Syntax is already validated by JSON.parse. Compare decoded keys in each object:
  // JavaScript keeps the last duplicate, while D1's JSON queries may use the first.
  const objects = [];
  for (let index = 0; index < text.length; index++) {
    if (text[index] === "{") objects.push(new Set());
    else if (text[index] === "}") objects.pop();
    else if (text[index] === '"') {
      const start = index;
      for (index++; index < text.length; index++) {
        if (text[index] === "\\") index++;
        else if (text[index] === '"') break;
      }
      let next = index + 1;
      while (/\s/.test(text[next] ?? "")) next++;
      if (text[next] === ":") {
        const key = JSON.parse(text.slice(start, index + 1));
        const keys = objects.at(-1);
        if (keys.has(key)) throw new ServiceError(400, "invalid_json");
        keys.add(key);
      }
    }
  }
}

export async function readJson(request, maximumBytes) {
  if (request.headers.get("Content-Type")?.split(";")[0].trim().toLowerCase() !== "application/json") {
    throw new ServiceError(415, "json_required");
  }
  const length = request.headers.get("Content-Length");
  if (length !== null && (!/^\d+$/.test(length) || Number(length) > maximumBytes)) {
    throw new ServiceError(413, "body_too_large");
  }
  if (!request.body) throw new ServiceError(400, "invalid_json");
  const reader = request.body.getReader();
  const chunks = [];
  let size = 0;
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > maximumBytes) {
        await reader.cancel();
        throw new ServiceError(413, "body_too_large");
      }
      chunks.push(value);
    }
    const bytes = new Uint8Array(size);
    let offset = 0;
    for (const chunk of chunks) {
      bytes.set(chunk, offset);
      offset += chunk.byteLength;
    }
    const text = new TextDecoder("utf-8", { fatal: true, ignoreBOM: true }).decode(bytes);
    const value = JSON.parse(text);
    rejectDuplicateMembers(text);
    return { value, text, bytes };
  } catch (error) {
    if (error instanceof ServiceError) throw error;
    throw new ServiceError(400, "invalid_json");
  } finally {
    reader.releaseLock();
  }
}

export async function sha256(value) {
  const bytes = typeof value === "string" ? new TextEncoder().encode(value) : value;
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map(byte => byte.toString(16).padStart(2, "0")).join("");
}
