<!-- ai-generated: 70% - Claude Code ran the measurement and drafted the explanation, checked by me -->
# The client-server latency gap (Lab 3, Stretch 2)

Setup: Toxiproxy 2.12.0 (`toxiproxy` service, compose profile `gap`) listens on 8666 in front of `svcdesk:8080`,
with one toxic: `latency`, stream `downstream`, toxicity 1.0, latency 100 ms, jitter 10 ms. Measured with
`itsmlab load 3 --base-url http://host.docker.internal:8666` (the M-08 load: 60 s open-loop at 40 requests/s,
latency-corrected, 64 connections), login `witoldszgl`:

| what | p99 |
|---|---|
| the client (oha, through the proxy) | 0.2158 s |
| the server (`histogram_quantile(0.99)` over the run's increments of my `/kb/search` histogram) | 0.1082 s |
| the gap | 0.1076 s |

Why the gap is there: the server's histogram starts its timer when the request reaches svcdesk and stops it when
svcdesk hands the answer to the socket. Everything that happens to the answer after that - here, Toxiproxy holding
every downstream chunk for 100 ms +- 10 ms - is outside the server's clock, so the server reports the same
~110 ms p99 it reports without any proxy (its own q on a direct run was 0.110 s), while every user waits about
100 ms more. The client's p99 is roughly the server's p99 plus the toxic's delay at its own upper tail
(100 ms + up to 10 ms jitter), so the gap is about 108 ms, the toxic and nothing else.

Note also the shape: the client's p50 moved from 16 ms to 122 ms, a factor of 7.5, while its p99 moved from 110 ms
to 216 ms, a factor of 2. A fixed network delay hurts the fast requests most in relative terms - the very ones my
server-side dashboard shows as healthy.

What it means for the SLO: my latency SLI (share of searches at or below 0.2 s) is measured on the server, so it
would stay green here (almost all server-side latencies are below 0.14 s) while on the client side about 4 % of the
searches take longer than 0.2 s. A server histogram cannot see the network, load balancers, proxies or TLS between
it and the user; that is where the users live, and only a client-side measurement (a synthetic probe, real-user
monitoring, or the load balancer's own histogram) can see it. When I set a latency objective that users feel, I
must either measure it at the edge or keep enough margin in the server-side threshold for the path in between.
