# Rate limits

The Fluxus API limits request frequency. The Basic plan allows no more than 600 requests per hour
for each API key. The Pro plan raises the limit to 5,000 requests per hour.

When the limit is exceeded, the server returns HTTP 429 Too Many Requests. The `Retry-After` response
header states how many seconds remain until the limit is lifted.

Limits use a rolling 60-minute window, not a calendar hour.
