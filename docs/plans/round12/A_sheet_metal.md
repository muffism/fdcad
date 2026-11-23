# Cloud A: sheet metal

Branch `cloud/round12a`. Decisions D1100 to D1199. Follow `COMMON.md`.

Items, in this order (open lines in PLAN.md Phase 7B):

1. TR165 Sheet metal Tab
2. TR166 Edge flange profile and edge choices
3. TR167 Edit Bends
4. TR168 Corner Relief feature
5. TR169 Bend notches
6. TR76 Sheet metal: flat pattern options (see also spec merge note 13: No Bends applies to converted and Insert Bends parts)
7. TR172 Flat pattern data for quoting
8. TR173 Flat pattern DXF output options
9. TR171 Convert to Sheet Metal extras
10. TR170 Miter flange extras
11. TR174 Sheet metal small options
12. TR370 Sheet metal small additions
13. TR282 Bend table and bend order
14. TR281 Several sheet metal bodies
15. TR283 Sheet metal forms as features, and fold progress
16. TR77 Sheet metal stamp
17. TR279 Own forming tools
18. TR332 Sheet metal rule library

Sheet metal code lives under `src/fdcad/core/features/` (sheet metal modules) and its tests under `tests/`; find it with `grep -ril "sheet" src/fdcad --include=*.py -l`. Flatten must keep working for every new feature: each item adds a flatten test.
