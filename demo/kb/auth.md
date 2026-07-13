# Authentication

Every Fluxus API request is authenticated with an API key in the `X-Fluxus-Key` header.
Create a key in the Developer section of the account dashboard.

Keys come in two types: test keys (the `fx_test_` prefix) and live keys (the `fx_live_` prefix).
Test keys work only in the sandbox and are not billed.

Keys do not expire, but you can revoke them at any time from the account dashboard.
After revocation, a key stops working within five minutes.
