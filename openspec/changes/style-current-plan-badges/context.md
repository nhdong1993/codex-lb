# Context

Plan badges are a scanning aid in the request-log grid: an operator looks down the Plan column to see which subscription tier served each request. A tier that shares the Free gray defeats that. In production, Go accounts serve real traffic, so their rows looked like Free rows.

## Palette

| Plan | Style |
| --- | --- |
| `free`, unrecognized | neutral zinc |
| `go` | lime |
| `plus` | emerald |
| `team` | sky |
| `business` | blue |
| `enterprise` | indigo |
| `edu` | teal |
| `pro` | violet |
| `prolite` | amber |
| `promax` | fuchsia |

Red and orange are left out because the same grid uses them for quota and rate-limit status badges. `business` sits next to `team` in hue because Business is the renamed Team workspace plan.

## Example

A request served by a `go` account shows a lime "Go" badge. A row whose plan is `self_serve_business_usage_based` shows "Self serve business usage based" in the neutral badge, the same as Free.
