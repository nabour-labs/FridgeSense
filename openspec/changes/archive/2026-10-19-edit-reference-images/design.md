# Design

## Decisions

- **PATCH, partial body.** Either field may be sent; a missing field keeps its stored value. Both missing is `400 {"error": "send an annotation or an image"}`. Validation reuses `validate_annotation` and `decode_image`, so the errors match `POST`.
- **Same item, same sort key.** `update_reference` reads the item, returns `False` if it is missing (404), and writes it back with the new fields and an `updated_at`. Keeping the sort key keeps the id and the oldest-first order.
- **One sheet for add and edit.** `AddReference` becomes `ReferenceSheet` with an optional `editing` reference. When editing, the current image is loaded as the starting source (a Blob kept once, so "Undo" after a crop gets back to it). The image counts as changed when the source is no longer that original Blob or a box is drawn; only then is it resized and sent. This avoids re-encoding (and slowly degrading) an image the owner did not touch.
