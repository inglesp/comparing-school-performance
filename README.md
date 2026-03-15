# Comparing School Performance

A dashboard for exploring primary school performance and demographic data in England, built from the DfE's [compare school performance](https://www.compare-school-performance.service.gov.uk/) data for 2024-25.

Live site: https://inglesp.github.io/comparing-school-performance/

## Features

- Histogram and scatterplot views of ~14,500 state-funded primary schools with switchable axes
- Filter by local authority, school type, religious character, and demographic percentiles
- Search and highlight individual schools
- National and filtered median lines on charts
- Sortable comparison table with configurable columns
- Shareable URLs preserving all state

## Development

Requires [uv](https://docs.astral.sh/uv/) and [just](https://github.com/casey/just).

```
just build   # build the static site to _site/
just serve   # serve locally
```
