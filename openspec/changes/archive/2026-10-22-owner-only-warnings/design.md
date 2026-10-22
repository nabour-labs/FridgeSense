# Design

`Warnings` already reads `role` from `AppContext`. It returns `null` and skips the request unless `isAdmin(role)`. Since only owners see banners, the per-link `canEdit` check becomes redundant and goes away. Both screens keep rendering `<Warnings />`, so the gate lives in one place.

The API stays readable by every role: hiding is a presentation choice, and the TV or MCP may want warnings later.
