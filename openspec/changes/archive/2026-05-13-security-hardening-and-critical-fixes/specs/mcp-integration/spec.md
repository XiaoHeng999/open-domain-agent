## MODIFIED Requirements

### Requirement: JSON-RPC 2.0 Protocol Compliance
`_request_counter` MUST use atomic increment or `itertools.count()` to prevent concurrent request ID collisions. Additionally, STDIO transport MUST serialize concurrent requests using `asyncio.Lock` and MUST use a `_pending_requests: dict[str, asyncio.Future]` mapping to correlate responses to their originating requests. A background reader task MUST read stdout lines and dispatch responses to the correct Future by matching response `id`.

#### Scenario: Concurrent STDIO requests
- **WHEN** two coroutines call _call_stdio simultaneously with different tool calls
- **THEN** each request gets a unique ID, writes are serialized via Lock, and each coroutine receives the correct response Future

#### Scenario: Response ID mismatch
- **WHEN** a response arrives with an ID not in _pending_requests
- **THEN** the response is logged as unexpected and discarded (no crash)

#### Scenario: Request timeout
- **WHEN** a request Future does not resolve within the timeout
- **THEN** the Future is cancelled and removed from _pending_requests, the caller receives a TimeoutError
