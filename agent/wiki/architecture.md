# System Architecture
# Update monthly or when service boundaries change
# last_verified: YYYY-MM-DD (update this date when you verify)

last_verified: $(date +%Y-%m-%d 2>/dev/null || echo 'YYYY-MM-DD')

## System Map
[Describe your high-level architecture here — major components and how they connect]

## Service Boundaries
[What does each service/module own? What are the contracts between them?]

## Key Data Flows
[Describe the critical paths through the system, e.g. user request → DB → response]

## External Dependencies
[List services this project depends on and why]
