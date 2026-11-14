# Go

Standard: Effective Go and the Go Code Review Comments.

Tools: `gofmt` (or the repo's `goimports`), `go vet ./...`, `go test ./...`, with `-race` when the change touches goroutines, channels or shared state; the repo's `staticcheck` or `golangci-lint` when declared.

Classic traps:
- An ignored error (`_ = f()`, or a missing `if err != nil`); wrap with `%w` so callers can use `errors.Is` and `errors.As`.
- `panic` in library code; a goroutine with no way to stop (leak).
- The incoming `context.Context` not passed to calls that can block or cross the network; a context stored in a struct.
- A loop variable captured by a closure (before Go 1.22); a nil map written to.
- An exported (capitalised) name is a public API for every importer.
- `go mod tidy` only when dependencies really change; keep the `go.mod` diff to what the change needs.
