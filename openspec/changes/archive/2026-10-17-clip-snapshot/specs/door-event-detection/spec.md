# Spec Delta

## ADDED Requirements

### Requirement: Signed media readable cross-origin
The stills bucket SHALL have a CORS rule that allows `GET` and `HEAD` from any origin, allows the `Range` request header, and exposes `Content-Length`, `Content-Range` and `Accept-Ranges`, so the app can draw a clip frame onto a canvas. The bucket SHALL stay private: every read still needs a presigned link.

#### Scenario: CORS rule on the stills bucket
- **WHEN** the stack is synthesized
- **THEN** the stills bucket's `CorsConfiguration` has one rule with `AllowedMethods` `["GET", "HEAD"]`, `AllowedOrigins` `["*"]`, `AllowedHeaders` including `Range`, and `ExposedHeaders` `Content-Length`, `Content-Range` and `Accept-Ranges`

#### Scenario: Bucket still private
- **WHEN** the stack is synthesized
- **THEN** the stills bucket still blocks all public access and has no bucket policy statement that allows unsigned reads
