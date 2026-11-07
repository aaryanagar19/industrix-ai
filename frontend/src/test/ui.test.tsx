import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Confirm, Empty, Pager, RiskBadge, ToastProvider, useToast } from "../components/ui";

describe("UI components", () => {
  it("RiskBadge renders the level", () => { render(<RiskBadge level="Critical" />); expect(screen.getByText("Critical")).toBeInTheDocument(); });
  it("Empty state shows text and hint", () => { render(<Empty text="Nothing here" hint="Try later" />); expect(screen.getByText("Nothing here")).toBeInTheDocument(); expect(screen.getByText("Try later")).toBeInTheDocument(); });
  it("Pager disables boundaries and pages forward", () => {
    const onPage = vi.fn(); render(<Pager page={1} total={25} size={10} onPage={onPage} />);
    expect(screen.getByText("Prev")).toBeDisabled(); fireEvent.click(screen.getByText("Next")); expect(onPage).toHaveBeenCalledWith(2); expect(screen.getByText("1 / 3")).toBeInTheDocument();
  });
  it("Confirm calls onConfirm then closes, Cancel does not confirm", () => {
    const ok = vi.fn(), close = vi.fn(); render(<Confirm open title="Delete?" message="Sure?" onConfirm={ok} onClose={close} confirmLabel="Yes" />);
    fireEvent.click(screen.getByText("Cancel")); expect(ok).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText("Yes")); expect(ok).toHaveBeenCalledTimes(1); expect(close).toHaveBeenCalled();
  });
  it("Toast provider shows messages", () => {
    const T = () => { const t = useToast(); return <button onClick={() => t("Saved!", "success")}>go</button>; };
    render(<ToastProvider><T /></ToastProvider>); fireEvent.click(screen.getByText("go")); expect(screen.getByText("Saved!")).toBeInTheDocument();
  });
});
