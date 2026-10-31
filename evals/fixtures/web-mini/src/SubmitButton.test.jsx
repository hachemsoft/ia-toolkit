import { render, screen } from "@testing-library/react";
import { SubmitButton } from "./SubmitButton";

test("disabled until the terms are accepted", () => {
  render(<SubmitButton email="a@example.org" accepted={false} />);
  expect(screen.getByRole("button")).toBeDisabled();
});
