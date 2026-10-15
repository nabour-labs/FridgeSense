# Proposal

## Why

Nova only sees four stills and a list of item names, so it guesses at things that look alike in this particular fridge: a milk bag versus a juice pouch, one snack versus another. The owner knows what those items look like and how they want them named, but has no way to tell the model. Also, a session currently lasts 30 days. That is too long for a link that judges and other people will see during the demo.

Tracks: **AWS Builder** (Bedrock Nova analysis gets more accurate from the owner's own reference images and instructions) and **Ring** (it reads the Ring camera's stills better).

## What Changes

- **Sign in once a day.** Session tokens now last 24 hours instead of 30 days, for owner and viewer tokens alike.
  - The PWA remembers when its token expires. It shows the passcode screen once that time passes, even before an API call fails and even while it is offline.
  - **BREAKING:** tokens issued before this change stop working after deploy, so everyone signs in again once.
- **A Config screen in the PWA**, opened from a gear button in the header. It is not a sixth tab: the in-progress `voice-page` change already takes the fifth slot.
  - **Reference images:** the owner adds a photo of an item from this fridge with a short annotation, for example "milk bag (2 L, white with blue print)", "soda can" or "granola bar". The app shrinks the photo in the browser before upload. The owner can delete references. At most 6 are kept.
  - **Custom instructions:** one free-text box, up to 1,000 characters, saved on request. For example: "Count yogurt cups individually." or "The brown bag on the top shelf is always bread."
  - Viewer (demo) tokens can see both sub-sections read-only.
- **New config routes** on the app API: `GET /api/config`, `PUT /api/config/instructions`, `POST /api/config/references` and `DELETE /api/config/references/{id}`. The three write routes are owner-only.
- **The Nova request carries the config.**
  - The reference images go first, each labeled with its annotation and marked as examples, not part of this door opening.
  - The stills follow as today.
  - The custom instructions are added to the final instruction text.
  - With no references and no instructions, the request is exactly what it is today.

## Capabilities

### New Capabilities

- `analysis-config`: the owner's reference images and custom instructions. Covers how they are stored per Ring account, their limits and validation, and the HTTP routes that read and change them.

### Modified Capabilities

- `inventory-api`: the session token lifetime changes from 30 days to 24 hours, and older tokens are invalidated.
- `inventory-app`: the sign-in requirement adds expiry on the device. A new Config screen requirement covers reference images and custom instructions.
- `fridge-change-analysis`: the Nova request includes the reference images, their annotations and the custom instructions.

## Out of scope

- **Custom instructions for other models.** Nova analysis is the only model call. The `voice-page` change answers questions by keyword matching, with no LLM, so custom instructions have nothing else to apply to.
- **Editing a reference** in place: delete it and add it again. Also out of scope: cropping in the app, and more than 6 references.
- **Several instruction sets,** or per-device or per-shelf config.
- **"Remember me" or a configurable session length,** and changing the passcode from the app.
- **Checking that a reference actually improves accuracy,** for example an eval set. The per-clip Nova cost log shows the extra tokens.
- **S3 storage for references.** They are small, so DynamoDB holds them (see design).

## Impact

- **Backend:**
  - `session.py`: a 24-hour TTL and a new key-derivation label, which invalidates old tokens.
  - A new `analysis_config.py` for storage, validation and loading.
  - New routes in `handlers/api.py`.
  - `analysis.py`: `build_request` takes the references and instructions.
  - `inventory.analyze_task` loads the config.
  - No new dependencies.
- **PWA:**
  - `session.ts` stores `expires_at`.
  - `App.tsx` gets an expiry check, the gear button and a `config` view.
  - A new `screens/Config.tsx`, an image-resize helper, and new `ApiClient` methods.
  - No new dependencies.
- **Data:** new DynamoDB items under the account partition: `CONFIG#instructions` and `REF#<id>` (base64 JPEG ≤ 200 KB decoded).
- **AWS:** no new resources or IAM. The API Lambda and pipeline Lambda can already read and write the table. Shipping it needs a `cdk deploy` for the new Lambda code.
- **Cost:** each reference adds roughly 1–2K input tokens per analysis. At most 6 references come to about $0.004 more per door opening with Nova 2 Lite, and that is logged in the existing `nova_cost` line.
- **Overlap with `voice-page`** (in progress): both edit `App.tsx`, `AppContext.tsx` and `api/client.ts`. Whichever merges second rebases onto the other.
