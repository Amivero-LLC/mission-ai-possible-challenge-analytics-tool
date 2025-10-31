type ToastType = "success" | "error" | "warn" | "default";

export interface ToastOptions {
  id?: string;
  type?: ToastType;
  message: string;
  duration?: number;
  persist?: boolean;
  onClick?: () => void;
}

export interface ToastPayload extends ToastOptions {
  id: string;
  type: ToastType;
  persist: boolean;
}

type ToastStoreEvent =
  | { type: "ADD"; toast: ToastPayload }
  | { type: "DISMISS"; id?: string }
  | { type: "CLEAR" };

type ToastListener = (event: ToastStoreEvent) => void;

const DEFAULT_DURATION = 4000;
const listeners = new Set<ToastListener>();

function createId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    try {
      return crypto.randomUUID();
    } catch {
      // fall through to Math.random
    }
  }
  return `toast_${Math.random().toString(36).slice(2, 10)}`;
}

function emit(event: ToastStoreEvent) {
  listeners.forEach((listener) => listener(event));
}

export const toastStore = {
  subscribe(listener: ToastListener) {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
  add(toast: ToastPayload) {
    emit({ type: "ADD", toast });
  },
  dismiss(id?: string) {
    emit({ type: "DISMISS", id });
  },
  clear() {
    emit({ type: "CLEAR" });
  },
};

type ToastShortcut = (message: string, options?: Omit<ToastOptions, "message" | "type">) => string;

interface ToastController {
  (options: ToastOptions | string): string;
  success: ToastShortcut;
  error: ToastShortcut;
  warn: ToastShortcut;
  info: ToastShortcut;
  dismiss: (id?: string) => void;
  clear: () => void;
}

function normalizeOptions(input: ToastOptions | string, presetType: ToastType | null): ToastPayload {
  const baseOptions = typeof input === "string" ? { message: input } : input;
  const type = presetType ?? baseOptions.type ?? "default";
  const id = baseOptions.id ?? createId();
  const persist = Boolean(baseOptions.persist);
  const duration = persist ? undefined : baseOptions.duration ?? DEFAULT_DURATION;
  return {
    ...baseOptions,
    id,
    type,
    persist,
    duration,
  };
}

function createShortcut(type: ToastType) {
  const shortcut: ToastShortcut = (message, options) => toast({ ...options, message, type });
  return shortcut;
}

export const toast: ToastController = ((input: ToastOptions | string) => {
  const payload = normalizeOptions(input, null);
  toastStore.add(payload);
  return payload.id;
}) as ToastController;

toast.success = createShortcut("success");
toast.error = createShortcut("error");
toast.warn = createShortcut("warn");
toast.info = createShortcut("default");
toast.dismiss = (id?: string) => toastStore.dismiss(id);
toast.clear = () => toastStore.clear();

export type { ToastType, ToastPayload, ToastStoreEvent };
