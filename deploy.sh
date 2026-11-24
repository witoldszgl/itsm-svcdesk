#!/usr/bin/env bash
# ai-generated: 75% - the plumbing is the course's skeleton; Claude Code wrote the shadow phase, the gate loop and the record prose with me, I set the rules and checked them on practice seeds
#
# deploy.sh - Lab 6: a shadow phase, then a weighted canary, with an automated analysis gate on my own Prometheus.
#
# The plan: (1) the candidate into svcdesk-canary at weight 0; (2) the shadow: nginx mirrors every user search to
# it while users keep getting 2.0.0, until it has answered shadow.min_requests searches within the gate; (3) the
# weighted steps of deploy.config.yaml; (4) promote. Any failed look on the way rolls back to 100/0/0. The gate:
# the canary's 5xx share and its share slower than the SLO threshold, each against max_burn_rate x (1 - objective)
# with at least gate.min_failures bad searches; and a canary whose observed searches stop while traffic flows
# (gate.stall_after) is a hang. Everything below "the gate" is mine; above it, the skeleton's helpers.
#
#   ./deploy.sh <candidate image reference>          # e.g. ghcr.io/swasik/svcdesk-v2-seeded:2.1.0-rc.1
#
# Exit status (R-15): 0 = promoted, 3 = rolled back; 1 = the script failed (a run without an outcome).
#
# Run by the course (itsmlab release 6, itsmlab verify 6, the grader): inside the checker image, on your stack's
# network, with stdin at end-of-file and every variable of R-13 set. Run by hand: on your machine against the stack
# you started with `docker compose -f release/compose.yml up -d --wait`, with the defaults below. By hand it needs
# bash 4 or newer, curl, jq, yq v4 (https://github.com/mikefarah/yq) and docker with Compose v2, as the checker
# image has; nothing else. It never reads stdin: nobody is there to answer (R-12).
set -euo pipefail

if [ -z "${BASH_VERSINFO:-}" ] || [ "${BASH_VERSINFO[0]}" -lt 4 ]; then
  echo "deploy.sh: needs bash 4 or newer (macOS ships 3.2: brew install bash, or run it with itsmlab release 6)" >&2
  exit 1
fi

# --- arguments ----------------------------------------------------------------------------------------------------
if [[ $# -ne 1 || -z ${1:-} || $1 == -* ]]; then
  echo "usage: ./deploy.sh <candidate image reference>" >&2
  exit 1
fi
CANDIDATE=$1                               # the reference exactly as given: it goes into CHANGE.md verbatim (R-25)

# --- environment (R-13); the defaults are for running by hand -----------------------------------------------------
# COMPOSE_FILE: the course sets your stack plus its override; use `docker compose` without -f and -p.
export COMPOSE_FILE=${COMPOSE_FILE:-release/compose.yml}
# COMPOSE_PROJECT_NAME: the course sets it. Unset, Compose takes `name:` from release/compose.yml (svcdesk-release
# in the template), which is the project `docker compose -f release/compose.yml up` started. Leave it unset by hand
# unless you started the stack with -p.
# PROMETHEUS_URL: the course sets http://prometheus:9090. By hand: the port release/compose.yml publishes.
PROMETHEUS_URL=${PROMETHEUS_URL:-http://127.0.0.1:${PROMETHEUS_PORT:-9090}}
# CADDY_ADMIN_URL: the course sets http://edge:2019. By hand it is unset, because the template does not publish the
# admin API on your machine (and should not: it can reconfigure the proxy). Unset, every admin call runs curl
# INSIDE the edge container, `docker compose exec -T edge curl http://127.0.0.1:2019/...`: the same API, reached
# from where it listens. Set it yourself only if you publish the port on loopback and point it there.
CADDY_ADMIN_URL=${CADDY_ADMIN_URL:-}
CADDY_SERVICE=${CADDY_SERVICE:-edge}       # the compose service that runs caddy:2.11.4 (exec mode only)
# RELEASE_RECORD_DIR: the course gives an empty directory per run. By hand: a new temporary directory, printed at
# the end (never under changes/: that is for the four runs `itsmlab verify 6 --save` records, R-26).
if [[ -z ${RELEASE_RECORD_DIR:-} ]]; then
  RELEASE_RECORD_DIR=$(mktemp -d "${TMPDIR:-/tmp}/lab6-change.XXXXXX")
fi
RELEASE_STRATEGY=${RELEASE_STRATEGY:-canary}   # canary, or flag in Stretch 2's runs (R-31)
CONFIG_FILE=${CONFIG_FILE:-deploy.config.yaml}

# --- logging and time -----------------------------------------------------------------------------------------------
# Everything the script says goes to stderr, so that helpers can print values on stdout for $(...). The course keeps
# both streams as run.log (R-26): say what you read and what you decided, with the numbers.
log() { printf '%s %s\n' "$(date -u +%H:%M:%S)" "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }

now_utc() { date -u +%Y-%m-%dT%H:%M:%SZ; }        # ISO 8601 UTC with Z (R-23)
now_s() { date -u +%s; }
STARTED=$(now_utc)
STARTED_S=$(now_s)
elapsed_s() { echo $(( $(now_s) - STARTED_S )); }

# calc <expression>: floating-point arithmetic, which bash does not have.   calc '10 * (1 - 0.995)'  ->  0.05
calc() { awk "BEGIN { printf \"%.10g\n\", ($1) }"; }
# check <condition>: true when the awk condition holds.                     if check "$share > $threshold"; then ...
check() { awk "BEGIN { exit !($1) }"; }

# dur_seconds <Prometheus duration>: 45s -> 45, 1m30s -> 90, 500ms -> 0.5 (R-07: durations are Prometheus durations)
dur_seconds() {
  local d=$1 total=0 n u
  [[ $d =~ ^([0-9]+(ms|s|m|h|d|w|y))+$ ]] || die "not a Prometheus duration: '$d'"
  while [[ $d =~ ^([0-9]+)(ms|s|m|h|d|w|y)(.*)$ ]]; do
    n=${BASH_REMATCH[1]}; u=${BASH_REMATCH[2]}; d=${BASH_REMATCH[3]}
    case $u in
      ms) total=$(calc "$total + $n / 1000") ;;
      s) total=$(calc "$total + $n") ;;
      m) total=$(calc "$total + $n * 60") ;;
      h) total=$(calc "$total + $n * 3600") ;;
      d) total=$(calc "$total + $n * 86400") ;;
      w) total=$(calc "$total + $n * 604800") ;;
      y) total=$(calc "$total + $n * 31536000") ;;
    esac
  done
  echo "$total"
}

# --- tools ------------------------------------------------------------------------------------------------------------
for tool in curl jq yq docker awk; do
  command -v "$tool" >/dev/null 2>&1 || die "$tool is missing (R-12 lists what the checker image has; by hand, install it or use itsmlab release 6)"
done
yq --version 2>&1 | grep -q 'mikefarah' || die "yq is not mikefarah's yq v4 (https://github.com/mikefarah/yq): $(yq --version 2>&1 | head -n 1)"
docker compose version >/dev/null 2>&1 || die "docker compose (Compose v2) is missing"

# --- deploy.config.yaml (R-07, R-11) ----------------------------------------------------------------------------------
[[ -f $CONFIG_FILE ]] || die "$CONFIG_FILE not found: copy deploy.config.example.yaml to deploy.config.yaml and fill it in"

# cfg <path below lab6_deploy>: one value of the file, or an error when it is missing or null.
cfg() {
  local v
  v=$(yq -e ".lab6_deploy.$1" "$CONFIG_FILE" 2>/dev/null) || die "$CONFIG_FILE: lab6_deploy.$1 is missing or null (R-07)"
  printf '%s\n' "$v"
}

SLO_WINDOW=$(cfg slo.window)
AVAILABILITY_OBJECTIVE=$(cfg slo.availability.objective)
LATENCY_OBJECTIVE=$(cfg slo.latency.objective)
LATENCY_THRESHOLD_S=$(cfg slo.latency.threshold_seconds)
AVAILABILITY_MAX_BURN=$(cfg gate.availability.max_burn_rate)
LATENCY_MAX_BURN=$(cfg gate.latency.max_burn_rate)
MIN_REQUESTS=$(cfg gate.min_requests)
interval=$(cfg gate.interval)
INTERVAL_S=$(dur_seconds "$interval")
timeout=$(cfg timeout)
TIMEOUT_S=$(dur_seconds "$timeout")
mapfile -t STEP_WEIGHTS < <(yq '.lab6_deploy.steps[].weight' "$CONFIG_FILE")
mapfile -t step_durations < <(yq '.lab6_deploy.steps[].min_duration' "$CONFIG_FILE")
(( ${#STEP_WEIGHTS[@]} > 0 )) || die "$CONFIG_FILE: lab6_deploy.steps is empty (R-10)"
STEP_MIN_S=()                              # STEP_WEIGHTS[i] per cent for at least STEP_MIN_S[i] seconds
for d in "${step_durations[@]}"; do
  STEP_MIN_S+=("$(dur_seconds "$d")")
done

# time_left_s: seconds until your own deadline (lab6_deploy.timeout). The course kills the script at 180 s, and a
# killed run has no outcome (R-15): leave yourself the time to roll back and write the record.
time_left_s() { calc "$TIMEOUT_S - $(elapsed_s)"; }

# --- the stack ----------------------------------------------------------------------------------------------------------
# stack_curl <curl arguments...>: curl as seen from inside the stack's network. Run by the course the script is on
# that network already; by hand (CADDY_ADMIN_URL unset) it runs inside the edge container, which has curl.
stack_curl() {
  if [[ -n $CADDY_ADMIN_URL ]]; then
    curl "$@"
  else
    docker compose exec -T "$CADDY_SERVICE" curl "$@"
  fi
}

# caddy_admin <METHOD> <path> [<content type> <body>]: one call of Caddy's admin API; prints the answer.
caddy_admin() {
  local method=$1 path=$2 base=${CADDY_ADMIN_URL:-http://127.0.0.1:2019}
  local args=(-sS --fail-with-body --max-time 10 -X "$method")
  if [[ $# -ge 4 ]]; then
    args+=(-H "Content-Type: $3" --data-binary "$4")
  fi
  stack_curl "${args[@]}" "${base%/}$path"
}

# The stack as Compose resolves it (with the course's override, when the course runs the script).
STACK_JSON=$(docker compose config --format json) || die "docker compose config failed for COMPOSE_FILE=$COMPOSE_FILE"

# The Caddyfile is the one in release/compose.yml (the config named $CADDYFILE_CONFIG, as `docker compose config`
# resolves it); set_weights changes the numbers after weighted_round_robin and nothing else, so the stack's file
# and what the script loads never drift apart. Keep `admin 0.0.0.0:2019` in it: POST /load replaces the WHOLE
# configuration, the admin listener included, and without that line the admin API moves to the container's own
# localhost, where the course's runner no longer reaches it.
CADDYFILE_CONFIG=${CADDYFILE_CONFIG:-caddyfile}
CADDYFILE_TEMPLATE=$(jq -er --arg c "$CADDYFILE_CONFIG" '.configs[$c].content' <<<"$STACK_JSON") \
  || die "no config '$CADDYFILE_CONFIG' with inline content in the stack (R-01: configuration goes in through configs: content:)"
n=$(grep -cE 'weighted_round_robin([[:space:]]+[0-9]+)+' <<<"$CADDYFILE_TEMPLATE" || true)
[[ $n == 1 ]] || die "the Caddyfile must have exactly one 'lb_policy weighted_round_robin <weights>' line (it has $n)"

# caddyfile_with_weights <w1> <w2> ...: the stack's Caddyfile with these weights.
caddyfile_with_weights() {
  sed -E "s/weighted_round_robin([[:space:]]+[0-9]+)+/weighted_round_robin $*/" <<<"$CADDYFILE_TEMPLATE"
}

# get_weights: the weights Caddy runs now, space-separated in upstream order, e.g. "90 10".
# weights_by_upstream: the same as lines "<upstream> <weight>", e.g. "svcdesk-canary:8080 10".
WRR='[.. | objects | select(.handler? == "reverse_proxy" and .load_balancing.selection_policy.policy? == "weighted_round_robin")] | first // empty'
get_weights() {
  caddy_admin GET /config/ | jq -r "$WRR"' | .load_balancing.selection_policy.weights | map(tostring) | join(" ")'
}
weights_by_upstream() {
  caddy_admin GET /config/ \
    | jq -r "$WRR"' | [.upstreams, .load_balancing.selection_policy.weights] | transpose[] | "\(.[0].dial) \(.[1])"'
}

# set_weights <stable> <canary>: load the Caddyfile with these weights (whole numbers, in upstream order; a stack
# with a third upstream, such as Stretch 1's recipe, passes three). Refuses all-zero weights (R-06: Caddy 2.11.4
# then answers no request at all), then reads the weights back and fails unless Caddy runs exactly these.
set_weights() {
  local w sum=0 got body
  (( $# >= 2 )) || die "set_weights needs one weight per upstream, e.g. set_weights 90 10"
  for w in "$@"; do
    [[ $w =~ ^[0-9]+$ ]] || die "set_weights: '$w' is not a whole number"
    sum=$(( sum + w ))
  done
  (( sum > 0 )) || die "set_weights $*: refused - with every weight at 0 Caddy 2.11.4 answers no request at all (R-06)"
  body=$(caddyfile_with_weights "$@")
  [[ -n $body ]] || die "set_weights: empty Caddyfile"
  caddy_admin POST /load text/caddyfile "$body" >/dev/null \
    || { log "set_weights $*: Caddy refused the configuration"; return 1; }
  got=$(get_weights) || { log "set_weights $*: could not read the weights back"; return 1; }
  [[ $got == "$*" ]] || { log "set_weights $*: Caddy runs '$got'"; return 1; }
  log "weights now $*"
}

# start_canary <image>: put an image into svcdesk-canary, the one command R-14 allows for it. Only svcdesk-canary is
# recreated; it keeps whatever weight Caddy gives it (put it at 0 first). Waits until the new container answers
# /health. Your own requests to svcdesk-canary are not the users' (R-14), but a search you send counts towards the
# hang's onset like any other (RELEASE-SPEC.md R-30).
start_canary() {
  local image=$1 i
  CANARY_IMAGE=$image docker compose up -d --no-deps --wait svcdesk-canary >&2 \
    || { log "start_canary: compose could not start svcdesk-canary with $image"; return 1; }
  for i in $(seq 1 30); do
    if stack_curl -fsS --max-time 2 http://svcdesk-canary:8080/health >/dev/null 2>&1; then
      log "svcdesk-canary runs $image"
      return 0
    fi
    sleep 1
  done
  log "start_canary: svcdesk-canary did not answer /health within 30 s"
  return 1
}

# --- Prometheus -----------------------------------------------------------------------------------------------------
# prom_query <PromQL> [<time>]: one instant query against your Prometheus, evaluated now or at <time> (Unix seconds).
# The query must return exactly one number (use sum(...) around a vector). Prints it and returns:
#   0  a number (possibly +Inf);
#   1  Prometheus did not answer, refused the query, or returned more than one series;
#   2  NO DATA: an empty result, or NaN (0 divided by 0: nothing to count yet).
# 2 is not a pass and not a failure: what it means for your gate is your decision (the empty-data case, R-28).
# Under set -e, call it inside `if` or with `||`, never bare:
#   if share=$(prom_query "$q"); then ...; else rc=$?; ...; fi
# Two numbers that belong together - a count and its 5xx or its le bucket - must come from the same scrape: read them
# in one query, or give every query of one look the same <time>, a second or two in the past (trap 4):
#   at=$(( $(now_s) - 2 )); n=$(prom_query "$q_all" "$at") && bad=$(prom_query "$q_5xx" "$at") || ...
prom_query() {
  local body n value
  local -a at=()
  [[ -n ${2:-} ]] && at=(--data-urlencode "time=$2")
  body=$(curl -sS --fail-with-body --max-time 5 "${PROMETHEUS_URL%/}/api/v1/query" --data-urlencode "query=$1" \
    ${at[@]+"${at[@]}"} 2>&1) \
    || { log "prom_query: no answer from $PROMETHEUS_URL, or an error: ${body:0:300}"; return 1; }
  [[ $(jq -r '.status' <<<"$body" 2>/dev/null) == success ]] \
    || { log "prom_query: ${body:0:300}"; return 1; }
  case $(jq -r '.data.resultType' <<<"$body") in
    scalar) value=$(jq -r '.data.result[1]' <<<"$body") ;;
    vector)
      n=$(jq '.data.result | length' <<<"$body")
      (( n == 0 )) && return 2
      (( n == 1 )) || { log "prom_query: $n series, expected one (aggregate with sum): $1"; return 1; }
      value=$(jq -r '.data.result[0].value[1]' <<<"$body") ;;
    *) log "prom_query: a range or string result, expected one number: $1"; return 1 ;;
  esac
  [[ $value == NaN ]] && return 2
  printf '%s\n' "$value"
}

# --- the change record (R-23, R-24, R-27) ---------------------------------------------------------------------------
# Your decisions about this change, the same for every run. The record check accepts only the values listed.
CHANGE_TYPE=standard             # standard | normal | emergency
RISK=low                         # low | medium | high
ROLLBACK_PLAN="Caddy weights back to 100/0/0 in one admin-API call (never 0/0/0); svcdesk-stable 2.0.0 keeps running and serving throughout, the candidate container stays in svcdesk-canary at weight 0 until the next release"
# The pre-authorisation the approve-then-act action rests on (R-24): it exists before every run.
APPROVAL="standard change model SCM-SVCDESK-CANARY: release procedure and gate of BLAST-RADIUS.md, pre-authorised for svcdesk-v2-seeded 2.x candidates"

STABLE_IMAGE=$(jq -r '.services["svcdesk-stable"].image // empty' <<<"$STACK_JSON")
[[ -n $STABLE_IMAGE ]] || die "the stack has no service svcdesk-stable (R-01)"

ACTIONS=()
RECORD_WRITTEN=0

# yaml_str <text>: a quoted YAML string (a JSON string is one).
yaml_str() { jq -Rn --arg s "$1" '$s'; }

# record_action <autonomy> <what the script did> [<approval>]: one entry of `actions`, stamped now. The autonomy
# ladder of Lecture 6: read-only, suggest, approve-then-act, closed-loop. approve-then-act needs the approval that
# existed before the run (a change ticket, a CAB decision): nobody can approve during it (R-24).
record_action() {
  local autonomy=$1 text=$2 approval=${3:-} entry
  case $autonomy in
    read-only|suggest|approve-then-act|closed-loop) ;;
    *) die "record_action: autonomy '$autonomy' is not one of read-only, suggest, approve-then-act, closed-loop" ;;
  esac
  entry="{at: $(now_utc), action: $(yaml_str "$text"), autonomy: $autonomy"
  if [[ $autonomy == approve-then-act ]]; then
    [[ ${#approval} -ge 5 ]] || die "record_action: approve-then-act needs the approval it acts on (R-24)"
    entry+=", approval: $(yaml_str "$approval")"
  fi
  ACTIONS+=("$entry}")
  log "action [$autonomy] $text"
}

# record_body: the prose below the front matter, read by the lecturer (R-27). Write yours: it is the same reasoning
# for every run, and you may add what this run saw (the variables of the script are in scope).
record_body() {
  cat <<'EOF'
# Change record

## Why this change type

Standard. The procedure is the same for every svcdesk 2.x candidate and was pre-authorised once, as a standard
change model (SCM-SVCDESK-CANARY): the candidate first sees only mirrored copies of live searches while every user
still gets 2.0.0, then 10 % and 50 % of the users, and an automatic gate on my own SLOs decides at every look. What
makes the risk low is not the candidate - it is untested by definition - but the procedure: the stable build never
stops, a rollback is one admin-API call, and the four practice runs (changes/) show the gate rolling back an errors,
a slow and a hanging candidate with almost no user failure and promoting the honest one. It stops being a standard
change if the plan changes (a first step above 20 %, no shadow, a gate window longer than a step), if the candidate
changes anything the shadow cannot exercise (a schema migration, a write path: the mirror would then duplicate
writes), or if the gate ever promotes a candidate that later breaks the SLO - then each release goes back to a
normal change with a person's approval before the run.

## Risk and what bounds it

What can go wrong for users: during the weighted steps a bad candidate answers a share of real searches. The shadow
is there so that this almost never happens: an errors or slow candidate shows its 30 % bad share among the first
few dozen mirrored searches, and a hang stops being observed after at most 120 of them, which at 40 mirrored
searches a second the stall rule notices within about 10-14 s, still before any user reaches it. If a bad
behaviour only showed itself under weighted traffic, the bound is c + R x w x q x D at the 10 % step: about
5 + 40 x 0.1 x 1 x 14 = 61 failed searches for the worst case (a hang), under the 150 ceiling. The gate's deadline
(timeout 165 s) rolls back anything undecided. What it cannot see: a defect on a route the traffic does not use, and
anything slower than the 1 s user patience but still within the SLO threshold of the gate (none, at 0.2 s).
EOF
}

# write_record <promoted|rolled-back> <reason>: $RELEASE_RECORD_DIR/CHANGE.md with R-23's front matter.
write_record() {
  local outcome=$1 reason=$2 finished a
  finished=$(now_utc)
  case $CHANGE_TYPE in standard|normal|emergency) ;; *) log "WARNING: change_type '$CHANGE_TYPE' is not standard, normal or emergency" ;; esac
  case $RISK in low|medium|high) ;; *) log "WARNING: risk '$RISK' is not low, medium or high" ;; esac
  (( ${#ROLLBACK_PLAN} >= 20 )) || log "WARNING: rollback_plan is shorter than 20 characters"
  (( ${#reason} >= 10 )) || log "WARNING: reason is shorter than 10 characters"
  (( ${#ACTIONS[@]} >= 3 )) || log "WARNING: ${#ACTIONS[@]} actions recorded; R-24 wants at least three"
  mkdir -p "$RELEASE_RECORD_DIR"
  {
    echo "---"
    echo "lab6_change:"
    echo "  id: CHG-${STARTED//[-:]/}"
    echo "  candidate: $(yaml_str "$CANDIDATE")"
    echo "  stable: $(yaml_str "$STABLE_IMAGE")"
    echo "  strategy: $RELEASE_STRATEGY"
    echo "  change_type: $CHANGE_TYPE"
    echo "  risk: $RISK"
    echo "  rollback_plan: $(yaml_str "$ROLLBACK_PLAN")"
    echo "  started: $STARTED"
    echo "  finished: $finished"
    echo "  outcome: $outcome"
    echo "  reason: $(yaml_str "$reason")"
    echo "  actions:"
    for a in "${ACTIONS[@]}"; do
      echo "    - $a"
    done
    echo "---"
    record_body
  } >"$RELEASE_RECORD_DIR/CHANGE.md"
  RECORD_WRITTEN=1
  log "record: $RELEASE_RECORD_DIR/CHANGE.md"
}

# finish <promoted|rolled-back> <reason>: write the record and exit 0 or 3 (R-15). Call it only once the routing it
# reports is in place. In a canary run it checks Caddy first - promoted: every upstream but svcdesk-canary at 0;
# rolled back: svcdesk-canary at 0 - and exits 1, a run without an outcome, when the weights disagree.
finish() {
  local outcome=$1 reason=$2 weights canary others
  case $outcome in promoted|rolled-back) ;; *) die "finish: the outcome is promoted or rolled-back, not '$outcome'" ;; esac
  if [[ $RELEASE_STRATEGY == canary ]]; then
    weights=$(weights_by_upstream) || die "finish: could not read Caddy's weights"
    canary=$(awk '$1 == "svcdesk-canary:8080" { print $2 }' <<<"$weights")
    others=$(awk '$1 != "svcdesk-canary:8080" { s += $2 } END { print s + 0 }' <<<"$weights")
    if [[ $outcome == promoted ]] && ! (( ${canary:-0} > 0 && others == 0 )); then
      die "finish promoted, but Caddy's weights are: $(tr '\n' ' ' <<<"$weights")- the stable build still takes requests"
    fi
    if [[ $outcome == rolled-back ]] && (( ${canary:-0} != 0 )); then
      die "finish rolled-back, but Caddy's weights are: $(tr '\n' ' ' <<<"$weights")- the candidate still takes requests"
    fi
  fi
  write_record "$outcome" "$reason"
  log "outcome: $outcome - $reason ($(elapsed_s) s)"
  if [[ $outcome == promoted ]]; then exit 0; else exit 3; fi
}

on_exit() {
  local rc=$?
  if (( RECORD_WRITTEN == 0 )); then
    log "exited with status $rc before finish: no record, no outcome (R-15, R-23)"
  fi
}
trap on_exit EXIT

log "candidate $CANDIDATE, stable $STABLE_IMAGE, strategy $RELEASE_STRATEGY"
log "config: SLO window $SLO_WINDOW; availability $AVAILABILITY_OBJECTIVE (max burn $AVAILABILITY_MAX_BURN);" \
    "latency $LATENCY_OBJECTIVE under ${LATENCY_THRESHOLD_S}s (max burn $LATENCY_MAX_BURN);" \
    "min_requests $MIN_REQUESTS; interval ${INTERVAL_S}s; timeout ${TIMEOUT_S}s;" \
    "steps ${STEP_WEIGHTS[*]} % for ${STEP_MIN_S[*]} s"
log "Prometheus $PROMETHEUS_URL; Caddy admin ${CADDY_ADMIN_URL:-via docker compose exec $CADDY_SERVICE}"


# =====================================================================================================================
# The gate
# =====================================================================================================================
# Read from deploy.config.yaml (R-11): every threshold, step, duration and the deadline. Optional keys of my own:
# gate.min_failures, gate.stall_after and the shadow block (Stretch 1).
cfg_opt() { local v; v=$(yq ".lab6_deploy.$1 // \"\"" "$CONFIG_FILE"); [[ -n $v && $v != null ]] && echo "$v" || echo "$2"; }
MIN_FAILURES=$(cfg_opt gate.min_failures 5)
STALL_S=$(dur_seconds "$(cfg_opt gate.stall_after 10s)")
AV_T=$(calc "$AVAILABILITY_MAX_BURN * (1 - $AVAILABILITY_OBJECTIVE)")     # 5xx share that fails a step
LAT_T=$(calc "$LATENCY_MAX_BURN * (1 - $LATENCY_OBJECTIVE)")             # share slower than the threshold
SHADOW_TOOL=$(cfg_opt shadow.tool "")
SHADOW_MIN_REQ=$(cfg_opt shadow.min_requests 200)
SHADOW_MIN_S=$(dur_seconds "$(cfg_opt shadow.min_duration 10s)")
SHADOW_MAX_S=$(dur_seconds "$(cfg_opt shadow.max_duration 60s)")
RESERVE_S=12        # time kept back before the deadline for the rollback call and the record

# The number of upstreams in the stack's Caddyfile: 3 with the nginx mirror (stable, canary, shadow), else 2.
N_UP=$(grep -oE 'weighted_round_robin([[:space:]]+[0-9]+)+' <<<"$CADDYFILE_TEMPLATE" | awk '{print NF - 1}')
if [[ -n $SHADOW_TOOL && $N_UP -lt 3 ]]; then
  log "WARNING: shadow declared but the Caddyfile has $N_UP upstreams: no shadow phase"; SHADOW_TOOL=""
fi
# route <stable> <canary> [<shadow>]: Caddy's weights, with the shadow's 0 added when the stack has a mirror.
route() {
  if (( N_UP >= 3 )); then set_weights "$1" "$2" "${3:-0}"; else set_weights "$1" "$2"; fi
}

# The latency threshold as Prometheus 3 stores the le label: 0.2 -> "0.2", 1 -> "1.0".
LE=$(awk -v t="$LATENCY_THRESHOLD_S" 'BEGIN { s = sprintf("%.10g", t); if (s !~ /[.e]/) s = s ".0"; print s }')
SEL='job="svcdesk", http_route="/kb/search"'
Q_N_CANARY="sum(http_server_request_duration_seconds_count{$SEL, track=\"canary\"}) or vector(0)"
Q_E_CANARY="sum(http_server_request_duration_seconds_count{$SEL, track=\"canary\", http_response_status_code=~\"5..\"}) or vector(0)"
Q_F_CANARY="sum(http_server_request_duration_seconds_bucket{$SEL, track=\"canary\", le=\"$LE\"}) or vector(0)"
Q_N_STABLE="sum(http_server_request_duration_seconds_count{$SEL, track=\"stable\"}) or vector(0)"

# look: one reading of the canary's raw counters (cumulative since its container started) and the stable's
# searches, every number evaluated at the same instant a second in the past (same scrape: trap 4). Sets N E F S.
# Returns 1 when Prometheus does not answer. "No data" cannot happen: every query says `or vector(0)`, because a
# canary nobody has called yet has no series, and that is 0 searches, not a pass - the stall rule judges it.
N=0; E=0; F=0; S=0; PROM_ERRORS=0; LOOKS=0
look() {
  local at=$(( $(now_s) - 1 )) n e f s
  n=$(prom_query "$Q_N_CANARY" "$at") && e=$(prom_query "$Q_E_CANARY" "$at") \
    && f=$(prom_query "$Q_F_CANARY" "$at") && s=$(prom_query "$Q_N_STABLE" "$at") || return 1
  N=$(calc "$n"); E=$(calc "$e"); F=$(calc "$f"); S=$(calc "$s")
  LOOKS=$(( LOOKS + 1 ))
}

# canary_runs_candidate: Prometheus's latest scrape of the canary track is the candidate's build (its version is
# not the stable's). Only from then on are the canary's counters the candidate's (R-29 counts them the same way).
STABLE_VERSION=""
canary_runs_candidate() {
  local at=$(( $(now_s) - 1 )) body
  body=$(curl -sS --max-time 5 "${PROMETHEUS_URL%/}/api/v1/query" --data-urlencode "time=$at" \
    --data-urlencode 'query=group by (track, version) (svcdesk_build_info{job="svcdesk"})' 2>/dev/null) || return 1
  STABLE_VERSION=$(jq -r '[.data.result[] | select(.metric.track == "stable") | .metric.version] | first // ""' <<<"$body")
  CANARY_VERSION=$(jq -r '[.data.result[] | select(.metric.track == "canary") | .metric.version] | join(",")' <<<"$body")
  [[ -n $STABLE_VERSION && -n $CANARY_VERSION && $CANARY_VERSION != *,* && $CANARY_VERSION != "$STABLE_VERSION" ]]
}

# verdict <n> <bad5xx> <slow> <scope>: prints a failure reason and returns 0 when a share breaks its threshold
# with at least MIN_FAILURES bad searches behind it (trap 5: the first 5xx is kb-index's floor, not a verdict).
verdict() {
  local n=$1 e=$2 s=$3 scope=$4
  check "$n > 0" || return 1
  if check "$e >= $MIN_FAILURES && $e / $n > $AV_T"; then
    printf 'availability: %s of %s canary searches answered 5xx (%s %%) against a %s %% threshold (%s)\n' \
      "$(calc "int($e)")" "$(calc "int($n)")" "$(calc "int(1000 * $e / $n) / 10")" "$(calc "100 * $AV_T")" "$scope"
    return 0
  fi
  if check "$s >= $MIN_FAILURES && $s / $n > $LAT_T"; then
    printf 'latency: %s of %s canary searches slower than %s s (%s %%) against a %s %% threshold (%s)\n' \
      "$(calc "int($s)")" "$(calc "int($n)")" "$LATENCY_THRESHOLD_S" "$(calc "int(1000 * $s / $n) / 10")" "$(calc "100 * $LAT_T")" "$scope"
    return 0
  fi
  return 1
}

FAIL_REASON=""
# phase <name> <expected canary searches per stable search> <min seconds> <max seconds> <min searches>
# Runs one phase (the shadow, or one weighted step) whose routing is already in place. Returns 0 when it passed,
# 1 when it failed (FAIL_REASON says why). Looks every INTERVAL_S seconds:
#   fail  - a share above its threshold, over the phase or over the whole run, with >= MIN_FAILURES bad searches;
#         - a stall: no new canary search observed for STALL_S while the stable build's searches say the canary
#           should have had at least 20 (the hang: its held searches are never observed; /health stays green);
#         - Prometheus unreachable for 5 looks in a row; the phase's max duration or the script's deadline.
#   pass  - min seconds over, at least <min searches> canary searches in this phase, and no failure.
phase() {
  local name=$1 ratio=$2 min_s=$3 max_s=$4 min_req=$5
  local t0 n0 e0 f0 last_n last_t s_at_last now dn de ds why
  look || { FAIL_REASON="$name: Prometheus did not answer at the phase's start"; return 1; }
  t0=$(now_s); n0=$N; e0=$E; f0=$F; last_n=$N; last_t=$t0; s_at_last=$S
  while true; do
    sleep "$INTERVAL_S"
    now=$(now_s)
    if check "$(time_left_s) < $RESERVE_S"; then
      FAIL_REASON="$name: the script's deadline ($TIMEOUT_S s) came before the gate could pass it ($(calc "int($N - n0)") canary searches)"
      return 1
    fi
    if ! look; then
      PROM_ERRORS=$(( PROM_ERRORS + 1 ))
      (( PROM_ERRORS < 5 )) && continue
      FAIL_REASON="$name: Prometheus did not answer 5 looks in a row - no evidence is not a pass"
      return 1
    fi
    PROM_ERRORS=0
    dn=$(calc "$N - $n0"); de=$(calc "$E - $e0"); ds=$(calc "($N - $F) - ($n0 - $f0)")
    if why=$(verdict "$dn" "$de" "$ds" "$name"); then FAIL_REASON=$why; return 1; fi
    if why=$(verdict "$N" "$E" "$(calc "$N - $F")" "whole run"); then FAIL_REASON=$why; return 1; fi
    if check "$N > $last_n"; then
      last_n=$N; last_t=$now; s_at_last=$S
    elif (( now - last_t >= ${STALL_S%.*} )) && check "($S - $s_at_last) * $ratio >= 20"; then
      FAIL_REASON="$name: no new canary search observed for $(( now - last_t )) s while the stable build served $(calc "int($S - $s_at_last)") (the canary stopped answering; it had answered $(calc "int($N)") in all)"
      return 1
    fi
    log "$name: $(( now - t0 )) s, canary searches $(calc "int($dn)") in the phase ($(calc "int($N)") in all), 5xx $(calc "int($de)"), slower than ${LATENCY_THRESHOLD_S}s $(calc "int($ds)")"
    if (( now - t0 >= ${min_s%.*} )) && check "$dn >= $min_req"; then
      PASS_SUMMARY="$name passed after $(( now - t0 )) s: $(calc "int($dn)") canary searches, $(calc "int($de)") 5xx, $(calc "int($ds)") slower than ${LATENCY_THRESHOLD_S} s"
      return 0
    fi
    if (( now - t0 >= ${max_s%.*} )); then
      FAIL_REASON="$name: not passed within $max_s s ($(calc "int($dn)") canary searches of $min_req needed)"
      return 1
    fi
  done
}

rollback() {
  local reason=$1
  log "ROLLBACK: $reason"
  route 100 0 0 || route 100 0 0 || die "could not roll back the weights"
  record_action closed-loop "set weights $( (( N_UP >= 3 )) && echo 100/0/0 || echo 100/0 ) (roll back): $reason"
  record_release_state
  finish rolled-back "$reason"
}

# record_release_state: ITSM-43 of my Lab 4 postmortem - "what changed?" is one query. Reads the release rules'
# svcdesk:release_build (the build on each track) and svcdesk:release_builds_seen:10m (a track that changed build
# fires SvcdeskReleaseChanged, P3) and puts the answer into the record. Read-only, and never a reason to fail.
record_release_state() {
  local body state seen
  body=$(curl -sS --max-time 5 "${PROMETHEUS_URL%/}/api/v1/query" \
    --data-urlencode 'query={__name__=~"svcdesk:release_build|svcdesk:release_builds_seen:10m"}' 2>/dev/null) || body=""
  state=$(jq -r '[.data.result[]? | select(.metric.__name__ == "svcdesk:release_build") | "\(.metric.track)=\(.metric.version)"] | sort | join(", ")' <<<"$body" 2>/dev/null || true)
  seen=$(jq -r '[.data.result[]? | select(.metric.__name__ == "svcdesk:release_builds_seen:10m") | "\(.metric.track): \(.value[1])"] | sort | join(", ")' <<<"$body" 2>/dev/null || true)
  record_action read-only "read svcdesk:release_build (ITSM-43, what changed): ${state:-no data}; builds seen in 10 min per track: ${seen:-no data}"
}

log "gate: 5xx share > $(calc "100 * $AV_T") %, share slower than ${LATENCY_THRESHOLD_S} s (le=\"$LE\") > $(calc "100 * $LAT_T") %," \
    "each with >= $MIN_FAILURES bad; stall after ${STALL_S} s; shadow ${SHADOW_TOOL:-none} ($SHADOW_MIN_REQ searches, ${SHADOW_MIN_S}-${SHADOW_MAX_S} s)"
if [[ $RELEASE_STRATEGY != canary ]]; then
  log "strategy $RELEASE_STRATEGY is not implemented (Stretch 2 not taken): the canary path runs"
  RELEASE_STRATEGY=canary
fi

# 1. The candidate into svcdesk-canary, at weight 0: nobody sees it yet.
route 100 0 0 || die "could not put the weights at 100/0 before the release"
start_canary "$CANDIDATE" || rollback "the candidate did not start or did not answer /health within 30 s"
record_action approve-then-act "start svcdesk-canary with the candidate at weight 0" "$APPROVAL"

# 2. Wait until Prometheus scrapes the candidate's build on the canary track.
for i in $(seq 1 20); do
  canary_runs_candidate && break
  sleep 1
done
canary_runs_candidate || rollback "Prometheus never saw the candidate's build on the canary track (version '${CANARY_VERSION:-none}')"
record_action read-only "read svcdesk_build_info from Prometheus: canary track runs $CANARY_VERSION, stable $STABLE_VERSION"

# 3. The shadow (Stretch 1): users keep getting 2.0.0 through nginx, the candidate gets a copy of every search.
if [[ -n $SHADOW_TOOL ]]; then
  route 0 0 100 || rollback "could not switch the shadow on"
  record_action closed-loop "set weights 0/0/100: every user search through the $SHADOW_TOOL mirror to 2.0.0, a copy to the candidate"
  if phase shadow 1 "$SHADOW_MIN_S" "$SHADOW_MAX_S" "$SHADOW_MIN_REQ"; then
    record_action read-only "read the canary's searches, 5xx and le=$LE bucket every ${INTERVAL_S} s ($LOOKS looks): $PASS_SUMMARY"
  else
    record_action read-only "read the canary's searches, 5xx and le=$LE bucket every ${INTERVAL_S} s ($LOOKS looks): $FAIL_REASON"
    rollback "shadow, before any user reached the candidate - $FAIL_REASON"
  fi
fi

# 4. The weighted steps.
for i in "${!STEP_WEIGHTS[@]}"; do
  w=${STEP_WEIGHTS[$i]}
  route $(( 100 - w )) "$w" 0 || rollback "could not set the weights $(( 100 - w ))/$w"
  record_action closed-loop "set weights $(( 100 - w ))/$w$( (( N_UP >= 3 )) && echo /0 ) (step $(( i + 1 )) of ${#STEP_WEIGHTS[@]})"
  LOOKS=0
  if phase "step $(( i + 1 )) at $w %" "$(calc "$w / (100 - $w)")" "${STEP_MIN_S[$i]}" "$(( ${STEP_MIN_S[$i]%.*} + 60 ))" "$MIN_REQUESTS"; then
    record_action read-only "read the canary's SLIs every ${INTERVAL_S} s ($LOOKS looks): $PASS_SUMMARY"
  else
    record_action read-only "read the canary's SLIs every ${INTERVAL_S} s ($LOOKS looks): $FAIL_REASON"
    rollback "$FAIL_REASON"
  fi
done

# 5. Promote: the candidate serves every request.
route 0 100 0 || rollback "could not set the weights 0/100 to promote"
record_action closed-loop "set weights 0/100$( (( N_UP >= 3 )) && echo /0 ) (promote)"
record_release_state
finish promoted "every phase passed: $(calc "int($N)") canary searches in all, $(calc "int($E)") 5xx ($(calc "int(1000 * $E / ($N > 0 ? $N : 1)) / 10") %), $(calc "int($N - $F)") slower than ${LATENCY_THRESHOLD_S} s, against thresholds of $(calc "100 * $AV_T") % and $(calc "100 * $LAT_T") %"
