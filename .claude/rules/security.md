# Security rules

- Secrets come from `.env` through config. Never hard-code keys, and never log them.
- Keep `.env.example` complete, with dummy values and a comment for each variable.
- CORS allows only the configured origins.
- Once auth exists (M12), every project endpoint checks that the project belongs to the signed-in user.
- Limit upload size, request body size and LLM calls per user (values in config).
- Pin dependencies with `uv.lock` and `package-lock.json`, and commit both.
- Never log full data rows or uploaded file contents. Log IDs, counts and durations.
