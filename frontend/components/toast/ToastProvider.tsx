'use client';

import { createPortal } from "react-dom";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useReducer,
  useRef,
  useState,
} from "react";
import type { AnimationEvent, MouseEvent } from "react";

import { toastStore, type ToastPayload, type ToastStoreEvent, type ToastType } from "../../lib/toast";

const MAX_VISIBLE_TOASTS = 5;

interface ToastInternal extends ToastPayload {
  createdAt: number;
  dismissed: boolean;
}

interface ToastState {
  visible: ToastInternal[];
  queue: ToastInternal[];
}

type ToastAction =
  | { type: "ADD"; toast: ToastPayload }
  | { type: "DISMISS"; id?: string }
  | { type: "REMOVE"; id: string }
  | { type: "CLEAR" };

const reducer = (state: ToastState, action: ToastAction): ToastState => {
  switch (action.type) {
    case "ADD": {
      const freshToast: ToastInternal = {
        ...action.toast,
        createdAt: Date.now(),
        dismissed: false,
      };
      const visibleWithoutDupe = state.visible.filter((toast) => toast.id !== freshToast.id);
      const queueWithoutDupe = state.queue.filter((toast) => toast.id !== freshToast.id);

      if (visibleWithoutDupe.length < MAX_VISIBLE_TOASTS) {
        return {
          visible: [...visibleWithoutDupe, freshToast],
          queue: queueWithoutDupe,
        };
      }

      return {
        visible: visibleWithoutDupe,
        queue: [...queueWithoutDupe, freshToast],
      };
    }
    case "DISMISS": {
      if (!action.id) {
        return {
          visible: state.visible.map((toast) => ({ ...toast, dismissed: true })),
          queue: [],
        };
      }

      return {
        visible: state.visible.map((toast) =>
          toast.id === action.id ? { ...toast, dismissed: true } : toast,
        ),
        queue: state.queue.filter((toast) => toast.id !== action.id),
      };
    }
    case "REMOVE": {
      const filteredVisible = state.visible.filter((toast) => toast.id !== action.id);
      if (filteredVisible.length >= MAX_VISIBLE_TOASTS || state.queue.length === 0) {
        return {
          visible: filteredVisible,
          queue: state.queue.filter((toast) => toast.id !== action.id),
        };
      }

      const [next, ...rest] = state.queue;
      const promoted: ToastInternal = {
        ...next,
        createdAt: Date.now(),
        dismissed: false,
      };

      return {
        visible: [...filteredVisible, promoted],
        queue: rest,
      };
    }
    case "CLEAR": {
      return {
        visible: state.visible.map((toast) => ({ ...toast, dismissed: true })),
        queue: [],
      };
    }
    default:
      return state;
  }
};

type ToastProviderContextValue = {
  dismiss: (id?: string) => void;
};

const ToastContext = createContext<ToastProviderContextValue | undefined>(undefined);

const toastVisuals: Record<
  ToastType,
  { icon: string; container: string; accent: string; close: string }
> = {
  success: {
    icon: "✅",
    container: "border-emerald-200 bg-emerald-50 text-emerald-900",
    accent: "text-emerald-600",
    close: "text-emerald-500 hover:text-emerald-700",
  },
  error: {
    icon: "❌",
    container: "border-rose-200 bg-rose-50 text-rose-900",
    accent: "text-rose-600",
    close: "text-rose-500 hover:text-rose-700",
  },
  warn: {
    icon: "⚠️",
    container: "border-amber-200 bg-amber-50 text-amber-900",
    accent: "text-amber-600",
    close: "text-amber-500 hover:text-amber-700",
  },
  default: {
    icon: "💬",
    container: "border-slate-200 bg-white text-slate-900",
    accent: "text-slate-600",
    close: "text-slate-400 hover:text-slate-600",
  },
};

type ToastProviderProps = {
  children: React.ReactNode;
};

export function ToastProvider({ children }: ToastProviderProps) {
  const [state, dispatch] = useReducer(reducer, {
    visible: [],
    queue: [],
  });

  useEffect(() => {
    const unsubscribe = toastStore.subscribe((event: ToastStoreEvent) => {
      if (event.type === "ADD") {
        dispatch({ type: "ADD", toast: event.toast });
      } else if (event.type === "DISMISS") {
        if (event.id) {
          dispatch({ type: "DISMISS", id: event.id });
        } else {
          dispatch({ type: "CLEAR" });
        }
      } else if (event.type === "CLEAR") {
        dispatch({ type: "CLEAR" });
      }
    });
    return unsubscribe;
  }, []);

  const dismiss = useCallback((id?: string) => {
    toastStore.dismiss(id);
  }, []);

  const value = useMemo<ToastProviderContextValue>(
    () => ({
      dismiss,
    }),
    [dismiss],
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      <ToastViewport
        toasts={state.visible}
        onDismiss={(id) => dispatch({ type: "DISMISS", id })}
        onRemove={(id) => dispatch({ type: "REMOVE", id })}
      />
    </ToastContext.Provider>
  );
}

type ToastViewportProps = {
  toasts: ToastInternal[];
  onDismiss: (id: string) => void;
  onRemove: (id: string) => void;
};

function ToastViewport({ toasts, onDismiss, onRemove }: ToastViewportProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    return () => setMounted(false);
  }, []);

  if (!mounted || typeof document === "undefined") {
    return null;
  }

  return createPortal(
    <div
      aria-live="polite"
      aria-atomic="false"
      data-testid="toast-viewport"
      className="pointer-events-none fixed left-4 top-4 z-[1000] flex w-full max-w-sm flex-col gap-3 sm:max-w-md"
    >
      {toasts.map((toast) => (
        <ToastCard key={toast.id} toast={toast} onDismiss={onDismiss} onRemove={onRemove} />
      ))}
    </div>,
    document.body,
  );
}

type ToastCardProps = {
  toast: ToastInternal;
  onDismiss: (id: string) => void;
  onRemove: (id: string) => void;
};

function ToastCard({ toast, onDismiss, onRemove }: ToastCardProps) {
  const visual = toastVisuals[toast.type];
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const startTimeRef = useRef<number | null>(null);
  const remainingRef = useRef<number>(toast.duration ?? 0);

  const clearTimer = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const pauseTimer = useCallback(() => {
    if (toast.persist || !timerRef.current || startTimeRef.current === null) {
      clearTimer();
      return;
    }
    clearTimer();
    const elapsed = Date.now() - startTimeRef.current;
    remainingRef.current = Math.max(remainingRef.current - elapsed, 0);
  }, [clearTimer, toast.persist]);

  const startTimer = useCallback(
    (duration: number) => {
      if (toast.persist || duration <= 0) {
        if (duration <= 0) {
          onDismiss(toast.id);
        }
        return;
      }
      clearTimer();
      remainingRef.current = duration;
      startTimeRef.current = Date.now();
      timerRef.current = setTimeout(() => {
        remainingRef.current = 0;
        onDismiss(toast.id);
      }, duration);
    },
    [clearTimer, onDismiss, toast.id, toast.persist],
  );

  useEffect(() => {
    if (!toast.persist && toast.duration) {
      startTimer(toast.duration);
    }
    return () => {
      clearTimer();
    };
  }, [clearTimer, startTimer, toast.duration, toast.persist]);

  useEffect(() => {
    if (toast.dismissed) {
      pauseTimer();
    }
  }, [pauseTimer, toast.dismissed]);

  const handleMouseEnter = () => {
    pauseTimer();
  };

  const handleMouseLeave = () => {
    if (toast.persist) {
      return;
    }
    if (remainingRef.current > 0) {
      startTimer(remainingRef.current);
    }
  };

  const handleClose = (event: MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();
    onDismiss(toast.id);
  };

  const handleClick = () => {
    if (typeof toast.onClick === "function") {
      toast.onClick();
    }
  };

  const animationClass = toast.dismissed ? "toast-exit" : "toast-enter";

  const handleAnimationEnd = (event: AnimationEvent<HTMLDivElement>) => {
    if (toast.dismissed && event.animationName === "toast-exit-left") {
      onRemove(toast.id);
    }
  };

  return (
    <div
      data-testid="toast-card"
      role="status"
      className={`pointer-events-auto flex w-full items-start gap-3 rounded-lg border px-4 py-3 shadow-lg ring-1 ring-black/5 transition ${visual.container} ${animationClass}`}
      data-type={toast.type}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onClick={handleClick}
      onAnimationEnd={handleAnimationEnd}
    >
      <span className={`select-none text-xl ${visual.accent}`} aria-hidden="true">
        {visual.icon}
      </span>
      <div className="flex-1 text-sm font-medium leading-snug">{toast.message}</div>
      <button
        type="button"
        aria-label="Close notification"
        className={`ml-2 inline-flex h-6 w-6 flex-none items-center justify-center rounded-md transition ${visual.close}`}
        onClick={handleClose}
      >
        <span aria-hidden="true">×</span>
      </button>
    </div>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return context;
}
