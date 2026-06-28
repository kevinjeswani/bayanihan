# Inventory data

## manila_schools_demo.geojson (committed — synthetic)

Approximately 50 hypothetical Manila school buildings for demonstration and CI.

**This is not real data.** It uses:
- Archetype type distributions matching Jeswani (2021)
- Generic building identifiers (SCH_001, SCH_002, ...)
- Realistic geographic spread across Makati and Quezon City

Use this for `examples/`, CI, and testing. Do not represent it as actual buildings.

## manila_schools_real.geojson (gitignored — never committed)

The actual 1,021-building dataset assessed in Jeswani (2021), covering public school buildings in Makati and Quezon City. This file is gitignored and not redistributed — the cities may not want building-level data public.

If you have local access to this file, it can be used to reproduce the thesis Chapter 7 results. Real-data outputs are committed to `images/` as PNG only.
