import { act, cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { toast } from "../../lib/toast";
import { ToastProvider } from "./ToastProvider";

async function renderWithProvider() {
  render(
    <ToastProvider>
      <div>children</div>
    </ToastProvider>,
  );
  await act(async () => {
    await Promise.resolve();
  });
}

function fireAnimationEnd(element: HTMLElement) {
  const event = new Event("animationend", { bubbles: true });
  Object.defineProperty(event, "animationName", { value: "toast-exit-left" });
  element.dispatchEvent(event);
}

afterEach(() => {
  toast.clear();
  cleanup();
  vi.useRealTimers();
  vi.clearAllTimers();
});

describe("ToastProvider", () => {
  it("renders a toast message when triggered", async () => {
    await renderWithProvider();

    act(() => {
      toast.success("Saved!");
    });

    expect(await screen.findByText("Saved!")).toBeInTheDocument();
  });

  it("auto-dismisses toasts after the specified duration", async () => {
    vi.useFakeTimers();
    await renderWithProvider();

    act(() => {
      toast({ message: "Auto hide", duration: 2000 });
    });

    const toastCard = await screen.findByTestId("toast-card");
    expect(toastCard).toHaveTextContent("Auto hide");

    act(() => {
      vi.advanceTimersByTime(2000);
    });

    fireAnimationEnd(toastCard);

    await waitFor(() => expect(screen.queryByText("Auto hide")).not.toBeInTheDocument());
  });

  it("supports manual dismissal via the close button", async () => {
    const user = userEvent.setup();
    await renderWithProvider();

    act(() => {
      toast.error("Something went wrong");
    });

    const toastCard = await screen.findByTestId("toast-card");
    const closeButton = within(toastCard).getByRole("button", { name: /close notification/i });

    await user.click(closeButton);
    fireAnimationEnd(toastCard);

    await waitFor(() => expect(screen.queryByText("Something went wrong")).not.toBeInTheDocument());
  });

  it("positions the viewport in the top-left with entry animation applied", async () => {
    await renderWithProvider();

    act(() => {
      toast.info("Heads up");
    });

    const viewport = await screen.findByTestId("toast-viewport");
    expect(viewport).toHaveAttribute("aria-live", "polite");
    expect(viewport.className).toContain("left-4");
    expect(viewport.className).toContain("top-4");

    const toastCard = await screen.findByTestId("toast-card");
    expect(toastCard.className).toContain("toast-enter");
  });
});
