export function SubmitButton({ email, accepted }) {
  // Enabled when the form can be sent.
  const ready = email !== undefined && accepted;
  return <button type="submit" disabled={!ready}>Sign up</button>;
}
