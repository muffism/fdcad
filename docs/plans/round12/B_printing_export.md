# Cloud B: 3D printing, mesh, export and import

Branch `cloud/round12b`. Decisions D1200 to D1299. Follow `COMMON.md`.

Items, in this order (open lines in PLAN.md Phase 7B; some are partly done, PLAN.md says what is left):

1. TR336 3D print export preview (mesh preview, refining by edge length and aspect ratio)
2. TR302 Export and import options
3. TR300 Section and outline export
4. TR183 3MF names and metadata (what is left)
5. TR386 Read slicer 3MF files
6. TR385 Slicer target choice
7. TR383 Per body print settings
8. TR384 Settings by height
9. TR187 Layer aware sizes and infill weight (what is left)
10. TR301 Arrange on the bed and suggest an orientation
11. TR181 Split for Printing connectors
12. TR186 Mesh repair and reduce
13. TR409 Suction cups and floating islands
14. TR390 Lattice fill as a feature
15. TR414 Material interlock and base pad (what is left)
16. TR307 Coating allowance
17. TR330 Engraved marks
18. TR311 Code tag generator
19. TR188 Printing sample parts
20. TR358 Guided calibration print

The 3MF reader must stay safe on damaged files (size limits and pattern speed, see D7xx entries on hostile files): every new reader path gets a malformed file test with a small sample.
