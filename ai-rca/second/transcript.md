# Investigation transcript
agent: Claude Code (general-purpose subagent)
model: claude-opus-5-5

## Question
"Checkout errors paged at 06:39:19Z on 2026-10-12. Investigate 06:30Z to 06:50Z. What is the cause?"

### Query 1
```
sum by (service_name) (rate(traces_span_metrics_calls_total{status_code="STATUS_CODE_ERROR"}[5m]))
time=2026-10-12T06:42:00Z
```
```
payment 0.0642, checkout 0.0642, frontend 0.0642, frontend-proxy 0.0321, load-generator 0.2125, ad 0, recommendation 0, flagd 0
```
During the incident, payment, checkout and frontend all show the same error rate, suggesting one error chain that starts in payment and propagates upward.

### Query 2
```
sum by (service_name) (rate(traces_span_metrics_calls_total{status_code="STATUS_CODE_ERROR"}[5m]))
time=2026-10-12T06:32:00Z
```
```
load-generator 0.1875 (only series)
```
Before the incident, only load-generator has errors, so the load-generator errors are a pre-existing baseline. The payment/checkout/frontend errors are new.

### Query 3
```
sum by (service_name, span_name, status_code) (rate(traces_span_metrics_calls_total{service_name=~"payment|checkout"}[5m]))
time=2026-10-12T06:42:00Z
```
```
payment  oteldemo.PaymentService/Charge ERROR 0.0321 / UNSET 0.0708
payment  charge ERROR 0.0321 / UNSET 0.0708
payment  flagd.evaluation.v2.Service/ResolveFloat UNSET 0.0042
checkout oteldemo.PaymentService/Charge ERROR 0.0321 / UNSET 0.0708
checkout oteldemo.CheckoutService/PlaceOrder ERROR 0.0321 / UNSET 0.0708
checkout other client spans (GetCart, Convert, GetProduct, EmptyCart, POST): no ERROR series
```
The error starts in payment's internal `charge` span. Checkout's only failing downstream call is PaymentService/Charge, and its PlaceOrder errors match those failures one for one. Payment also evaluates a float feature flag (ResolveFloat).

### Query 4
```
sum by (service_name) (rate(traces_span_metrics_calls_total{status_code="STATUS_CODE_ERROR"}[5m]))
range 2026-10-12T06:30:00Z .. 2026-10-12T06:50:00Z step 120s
```
```
payment:   06:36 0.0047, 06:38 0.004, 06:40 0.0282, 06:42 0.0642, 06:44 0.0458, 06:46 0.0042, 06:48 0
checkout:  06:40 0.0376, 06:42 0.0642, 06:44 0.0333, 06:46 0
frontend:  06:40 0.0376, 06:42 0.0642, 06:44 0.0333, 06:46 0
ad/recommendation/flagd: ~0.004 at 06:36-38 and 06:44-46
load-generator: 0.16-0.21 throughout
```
The checkout and payment errors begin between 06:38 and 06:40 and are over by 06:46. Small flagd EventStream errors also appear in several services at 06:36-38 and 06:44-46, which hints at a flagd configuration change or reconnect at the start and end.

### Query 5
```
sum by (service_name, span_name) (rate(traces_span_metrics_calls_total{status_code="STATUS_CODE_ERROR", service_name=~"flagd|ad|recommendation|load-generator"}[5m]))
range 2026-10-12T06:30:00Z .. 2026-10-12T06:50:00Z step 120s
```
```
ad/recommendation/flagd  flagd.evaluation.v2.Service/EventStream: ~0.004-0.008 at 06:36-38 and 06:44-46, 0 otherwise
load-generator POST: 0.16-0.21 throughout (pre-existing)
```
The flagd EventStream errors fall exactly at the start and end of the payment error window. This fits a feature-flag change that streamed to clients (EventStream reconnect) when the flag was turned on and again when it was turned off.

### Query 6
```
sum by (span_name) (rate(traces_span_metrics_calls_total{service_name="payment", span_name=~"flagd.*"}[5m]))
range 2026-10-12T06:30:00Z .. 2026-10-12T06:50:00Z step 120s
```
```
ResolveFloat:   0 at 06:30-32, 0.0042 06:34-42, 0.0083 06:44, 0.0042 06:46, 0 06:48+
ResolveBoolean: 0.0042 at 06:34-36 and 06:44-46
EventStream ERROR: 0.0047 06:36, 0.004 06:38, 0.0042 06:44-46
```
Payment resolves a float flag throughout the incident. In the OTel Demo, the `paymentFailure` flag is a float failure ratio, so this supports a flag-injected payment failure.

### Query 7
```
histogram_quantile(0.95, sum by (le, service_name) (rate(traces_span_metrics_duration_milliseconds_bucket{span_name="oteldemo.PaymentService/Charge", span_kind="SPAN_KIND_SERVER"}[5m])))
range 2026-10-12T06:30:00Z .. 2026-10-12T06:50:00Z step 120s
```
```
payment p95: ~1.9-2.0 ms throughout, single point 5.5 ms at 06:44
```
Payment latency barely changes, so the payment failures are fast, explicit errors rather than timeouts.

### Query 8
```
sum(rate(traces_span_metrics_calls_total{service_name="payment",span_name="oteldemo.PaymentService/Charge",status_code="STATUS_CODE_ERROR"}[5m])) / sum(rate(traces_span_metrics_calls_total{service_name="payment",span_name="oteldemo.PaymentService/Charge"}[5m]))
range 2026-10-12T06:30:00Z .. 2026-10-12T06:50:00Z step 120s
```
```
06:40 0.133, 06:42 0.312, 06:44 0.200, 06:46 0 (no result before 06:40)
```
At peak, about 31% of charges fail. That is a partial failure ratio, consistent with a probabilistic flag such as paymentFailure.

### Query 9
```
sum by (service_name) (rate(traces_span_metrics_calls_total{span_kind="SPAN_KIND_SERVER"}[5m]))
range 2026-10-12T06:30:00Z .. 2026-10-12T06:50:00Z step 120s
```
```
frontend:       06:30 3.90, 06:36 3.55, 06:38 9.84, 06:40 40.79, 06:42 63.41, 06:44 42.92, 06:46 15.15, 06:48 2.98
frontend-proxy: 06:30 2.04, 06:38 5.32, 06:40 21.17, 06:42 31.73, 06:44 21.32, 06:46 7.40, 06:48 1.53
checkout/payment: ~0.08-0.11 flat
cart 0.94-1.16, flagd 3.8-4.75, others flat
```
A large traffic surge hits frontend and frontend-proxy at the same time (about 15x at peak), but checkout and payment traffic stay flat. The surge therefore does not explain the payment errors directly.

### Query 10
```
sum by (span_name) (rate(traces_span_metrics_calls_total{service_name="frontend",status_code="STATUS_CODE_ERROR"}[5m]))
range 2026-10-12T06:30:00Z .. 2026-10-12T06:50:00Z step 120s
```
```
executing api route (pages) /api/checkout: 06:40 0.0188, 06:42 0.0321, 06:44 0.0167
oteldemo.CheckoutService/PlaceOrder:       06:40 0.0188, 06:42 0.0321, 06:44 0.0167
```
The only errors in frontend are on the checkout path, and they match the payment Charge failures. The traffic surge itself produces no frontend errors.

### Query 11
```
histogram_quantile(0.95, sum by (le, service_name) (rate(traces_span_metrics_duration_milliseconds_bucket{span_kind="SPAN_KIND_SERVER", service_name=~"checkout|frontend|cart|currency|product-catalog|shipping|email|quote"}[5m])))
range 2026-10-12T06:30:00Z .. 2026-10-12T06:50:00Z step 120s
```
```
frontend p95: 06:30 35.8, 06:36 33.6, 06:38 13.95, 06:40 5.25, 06:42 4.38, 06:44 4.74, 06:46 5.95, 06:48 35.4 ms
checkout p95: ~48 ms flat; cart ~1.9; currency 1.9; quote 1.9; shipping ~3; email 5.6-7.1; product-catalog ~7.3
```
No backend latency regression. Frontend p95 actually drops because the surge consists of cheap requests, so latency is not the cause.

### Query 12
```
topk(6, sum by (service_name, span_name) (rate(traces_span_metrics_calls_total{service_name=~"frontend|frontend-proxy"}[5m])))
time=2026-10-12T06:42:00Z
```
```
frontend GET / 59.45; frontend-proxy router frontend egress 31.73; frontend-proxy GET 31.23; frontend render route (pages) / 29.73; frontend resolve page components 29.73; frontend GET /api/products/[productId]/index 1.825
```
The surge is a flood of homepage (GET /) requests.

### Query 13
```
topk(6, sum by (service_name, span_name) (rate(traces_span_metrics_calls_total{service_name=~"frontend|frontend-proxy"}[5m])))
time=2026-10-12T06:32:00Z
```
```
frontend-proxy router frontend egress 1.975; frontend GET /api/products/[productId]/index 1.8; frontend ProductCatalogService/GetProduct 1.658; frontend-proxy GET 1.575; frontend executing api route (pages) /api/products/[productId]/index 0.9; frontend POST /api/cart 0.617
(GET / not in top 6)
```
Before the incident, there was no homepage flood. The flood (likely the demo's loadGeneratorFloodHomepage flag or an external client) runs at the same time as the payment failures but is a separate symptom.

## Answer
Most likely root cause: the payment service is failing its Charge calls (errors signal; up to about 31% of oteldemo.PaymentService/Charge failing from about 06:39 to 06:46), with the error starting in payment's internal `charge` span, as shown by Query 3, Query 4 and Query 8.
The checkout service's PlaceOrder errors, and the frontend /api/checkout errors that paged, are purely downstream propagation of the payment Charge failures (errors signal; identical rates of 0.0321/s at 06:42 and no other failing checkout dependency), as shown by Query 3 and Query 10.
Probably, though not proven from metrics alone, the payment failures were injected by a feature flag (the OTel Demo `paymentFailure` float flag) served by flagd (errors and traffic signals; payment calls flagd ResolveFloat throughout the window, and flagd EventStream errors in ad, recommendation, payment and flagd at 06:36-38 and 06:44-46 bracket the error window, consistent with a flag change being pushed), as shown by Query 5 and Query 6.
A concurrent traffic surge of homepage GET / requests hit frontend and frontend-proxy (traffic signal; about 4 to 63 req/s on frontend between 06:38 and 06:46), but I believe with moderate confidence that it is a separate, coincident event (possibly the `loadGeneratorFloodHomepage` flag) and not the cause of the checkout errors, because checkout and payment traffic stayed flat and frontend logged no errors outside checkout, as shown by Query 9, Query 12 and Query 13.
Latency is unlikely to be the cause: payment Charge p95 stayed around 2 ms and checkout p95 around 48 ms (latency signal), so the failures are fast explicit errors rather than timeouts or saturation, as shown by Query 7 and Query 11.
The load-generator POST errors (errors signal; 0.16-0.21/s) predate the incident at 06:30 and stay flat, so they are a baseline artifact and unrelated to the page, as shown by Query 2 and Query 5.
