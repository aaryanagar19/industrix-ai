import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../contexts/AuthContext";
import { ToastProvider } from "../components/ui";
import Login from "../pages/Login";
import { Protected } from "../App";

const wrap = (ui: JSX.Element, route = "/") => render(<MemoryRouter initialEntries={[route]}><ToastProvider><AuthProvider>{ui}</AuthProvider></ToastProvider></MemoryRouter>);
beforeEach(() => { localStorage.clear(); vi.restoreAllMocks(); });

describe("authentication UI", () => {
  it("redirects unauthenticated users from protected routes to login", () => {
    wrap(<Routes><Route path="/login" element={<div>login page</div>} /><Route path="/" element={<Protected><div>secret</div></Protected>} /></Routes>);
    expect(screen.getByText("login page")).toBeInTheDocument(); expect(screen.queryByText("secret")).toBeNull();
  });
  it("validates registration input before calling the API", async () => {
    const f = vi.spyOn(globalThis, "fetch"); wrap(<Login />);
    fireEvent.click(screen.getByText("No account? Register"));
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "a@b.io" } }); fireEvent.change(screen.getByLabelText(/^Password/), { target: { value: "short" } });
    fireEvent.click(screen.getByRole("button", { name: "Register" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/full name|8 characters/i); expect(f).not.toHaveBeenCalled();
  });
  it("shows the server error on failed login", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ detail: "Invalid email or password" }), { status: 401 }));
    wrap(<Login />);
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "x@y.io" } }); fireEvent.change(screen.getByLabelText(/^Password/), { target: { value: "wrongpass" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Invalid email or password"));
  });
  it("demo-account chips fill the form", () => {
    wrap(<Login />); fireEvent.click(screen.getByText("Safety Officer")); expect((screen.getByLabelText("Email") as HTMLInputElement).value).toBe("officer@industrix.dev");
  });
});
