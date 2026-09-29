// Prefixed logger; info/debug only when localStorage.scholaraDebug === "1".
const SECRET_PATTERNS = [
  /Bearer\s+[A-Za-z0-9._-]+/g,
  /\b(pk|sk)_(test|live)_[A-Za-z0-9$_-]+/g,
  /\bsk-or-[A-Za-z0-9_-]+/g,
];

function redact(value) {
  if (typeof value === "string") {
    return SECRET_PATTERNS.reduce((text, re) => text.replace(re, "[redacted]"), value);
  }
  if (value instanceof Error) return redact(`${value.name}: ${value.message}`);
  if (value && typeof value === "object") {
    try {
      return JSON.parse(redact(JSON.stringify(value)));
    } catch (err) {
      return "[unserializable]";
    }
  }
  return value;
}

function verbose() {
  try {
    return localStorage.getItem("scholaraDebug") === "1";
  } catch (err) {
    return false;
  }
}

export function createLogger(moduleName) {
  const tag = () => `[Scholara:${moduleName}] ${new Date().toISOString()}`;
  return {
    debug: (...args) => verbose() && console.debug(tag(), ...args.map(redact)),
    info: (...args) => verbose() && console.info(tag(), ...args.map(redact)),
    warn: (...args) => console.warn(tag(), ...args.map(redact)),
    error: (...args) => console.error(tag(), ...args.map(redact)),
  };
}
