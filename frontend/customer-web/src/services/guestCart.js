/**
 * Guest basket identity (round 23).
 *
 * A shopper can now fill a cart before signing in. The basket itself lives on
 * the server - same validation, same stock checks, same totals as an account
 * cart - so all this module owns is the *key* that names it.
 *
 * The key is a random UUID kept in localStorage, so it survives a refresh and
 * every tab of the same browser shares one basket. On login the cart is merged
 * into the account and the key is thrown away.
 */

const KEY_STORAGE = "ums.guestCartKey";

/* Survives a localStorage that refuses writes (private mode, quota, blocked). */
let memoryKey = null;

function randomKey() {
  try {
    if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  } catch {
    /* older browser - fall through */
  }
  return `g${Date.now().toString(36)}${Math.random().toString(36).slice(2, 14)}`;
}

/** The stable basket key for this browser. Created on first use. */
export function getGuestKey() {
  /*
   * Round 32: always keep a memory copy.
   *
   * Previously a localStorage that failed to *write* (private mode, "block all
   * cookies", a partitioned third-party frame) minted a brand-new key on every
   * call. The guest cart then dissolved per request, and - worse - the key sent
   * with verify-otp was not the key the rest of the app was reading. Caching in
   * memory means the browser still has one stable basket even when storage is
   * unavailable; only a full page reload loses it.
   */
  if (memoryKey) return memoryKey;

  try {
    let key = localStorage.getItem(KEY_STORAGE);
    if (!key || key.length < 8) {
      key = randomKey();
      localStorage.setItem(KEY_STORAGE, key);
    }
    memoryKey = key;
    return key;
  } catch {
    memoryKey = memoryKey || randomKey();
    return memoryKey;
  }
}

/**
 * Forget the basket after it has been merged into an account.
 * The next signed-out visit starts a fresh, empty basket.
 */
export function resetGuestKey() {
  memoryKey = null;
  try {
    localStorage.removeItem(KEY_STORAGE);
  } catch {
    /* ignore */
  }
}

export function hasGuestKey() {
  if (memoryKey) return true;
  try {
    return Boolean(localStorage.getItem(KEY_STORAGE));
  } catch {
    return Boolean(memoryKey);
  }
}
