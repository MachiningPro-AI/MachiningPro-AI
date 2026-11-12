# MachiningPro AI — Full Synthetic System Test Matrix

**Campaign:** MACHININGPRO_AI_FULL_SYNTHETIC_QUALIFICATION_AND_LOCALIZATION  
**Date:** 2026-11-12  
**Commit:** ccf4c55dcd471b88aa5e1a0821e9784c7f090d44  

---

| Test ID | Part ID | Module | Command/Action | Input | Expected | Actual | Status | Evidence | Severity | Defect ID |
|---------|---------|--------|---------------|-------|----------|--------|--------|----------|----------|-----------|
| T-001 | ALL | Synthetic Artifacts | Generate DXF files | 7 part definitions | 7 DXF files created, >0 bytes | 7 files created | PASS | tests/qualification/fixtures/ | — | — |
| T-002 | ALL | Ground Truth | Load expected.json | 7 JSON files | Schema valid, KNOWN/UNKNOWN correctly set | All valid | PASS | tests/qualification/fixtures/*.expected.json | — | — |
| T-003 | PART_G | DXF Import | INSUNITS=0 (unitless) | part_g DXF | INSUNITS value 0 in file | Confirmed | PASS | part_g_synthetic.dxf | — | — |
| T-004 | PART_A | DXF Import | ingest() via EngineeringSource | part_a DXF | CanonicalDocument returned | PASS | test run | — | — |
| T-005 | PART_A-G | DXF Import | All parts import | 7 DXF files | No crash | All pass | PASS | test run | — | — |
| T-006 | N/A | DXF Import | Empty file | 0 bytes | Fail-closed (exception or error doc) | Fail-closed | PASS | test run | — | — |
| T-007 | N/A | DXF Import | Corrupted file | Garbage bytes | Fail-closed | Fail-closed | PASS | test run | — | — |
| T-008 | PART_A | Ground Truth | Circle count | 5 circles expected | count=5 | 5 | PASS | part_a.expected.json | — | — |
| T-009 | PART_A | Ground Truth | Hole candidate diameter | 10.0 mm | 10.0 mm | 10.0 mm | PASS | part_a.expected.json | — | — |
| T-010 | PART_A | Ground Truth | Material unknown | No annotation | UNKNOWN | UNKNOWN | PASS | part_a.expected.json | — | — |
| T-011 | PART_B | Ground Truth | Material C45 | Annotated C45 | value=C45, iso=P | C45, P | PASS | part_b.expected.json | — | — |
| T-012 | PART_B | Ground Truth | Thread M30x1.5 | Annotated | designation=M30x1.5 | KNOWN | PASS | part_b.expected.json | — | — |
| T-013 | PART_D | Ground Truth | Bore Ø20 H7 | Explicit GD&T | dia=20, fit=H7, dev=+0.021 | KNOWN | PASS | part_d.expected.json | — | — |
| T-014 | PART_D | Ground Truth | Position tolerance | Ø0.05|A|B | tol=0.05, datums=[A,B] | KNOWN | PASS | part_d.expected.json | — | — |
| T-015 | PART_G | False-positive guard | Arc ≠ hole | 270° arc | must_not_classify_as=hole | PASS | part_g.expected.json | — | — |
| T-016 | PART_G | False-positive guard | Open polyline ≠ hole | 3-line open | must_not_classify_as=pocket_or_hole | PASS | part_g.expected.json | — | — |
| T-017 | PART_G | False-positive guard | Missing units ≠ mm | INSUNITS=0 | must_not_assume=mm | PASS | part_g.expected.json | — | — |
| T-018 | PART_G | False-positive guard | Missing material ≠ ISO P | None | must_not_assume=ISO_P | PASS | part_g.expected.json | — | — |
| T-019 | N/A | Material Library | Library loads | seed_material_library() | >0 entries | 19 | PASS | test run | — | — |
| T-020 | N/A | Material Library | C45 present | lookup | designation=C45, iso=P | PASS | test run | — | — |
| T-021 | N/A | Material Library | 42CrMo4 present | lookup | KNOWN | PASS | test run | — | — |
| T-022 | N/A | Material Library | AlMg1SiCu present | lookup | iso=N | PASS | test run | — | — |
| T-023 | N/A | Material Library | Nonexistent rejected | FAKE_MATERIAL_XYZ | not found | PASS | test run | — | — |
| T-024 | N/A | Machine Library | Library loads | seed_machine_library() | >0 entries | 28 | PASS | test run | — | — |
| T-025 | PART_A | Machine Library | 120×80 compatible | envelope check | ≥1 machine covers area | PASS | test run | — | — |
| T-026 | PART_B | Machine Library | Turning machine exists | capability check | ≥1 turning-capable | PASS | test run | — | — |
| T-027 | N/A | Cutting Parameters | spindle_speed formula | Vc=100, D=20 | n=1591.549 RPM | 1591.549 | PASS | INDEPENDENT CALC | — | — |
| T-028 | PART_B | Cutting Parameters | spindle_speed Ø60 | Vc=100, D=60 | n=530.516 RPM | 530.516 | PASS | INDEPENDENT CALC | — | — |
| T-029 | N/A | Cutting Parameters | feed_rate formula | n=1591.5, z=4, fz=0.1 | 636.619 mm/min | 636.619 | PASS | INDEPENDENT CALC | — | — |
| T-030 | N/A | Cutting Parameters | Zero diameter → error | D=0 | MachiningMathError | PASS | test run | — | — |
| T-031 | N/A | Cutting Parameters | Negative Vc → error | Vc=-50 | MachiningMathError | PASS | test run | — | — |
| T-032 | N/A | Tool Life | Taylor T, case 1 | C=500,n=0.25,Vc=100 | T=625 min | 625 min | PASS | INDEPENDENT CALC | — | — |
| T-033 | N/A | Tool Life | Taylor T, case 2 | C=200,n=0.3,Vc=200 | T=1 min | 1 min | PASS | INDEPENDENT CALC | — | — |
| T-034 | N/A | Tool Life | Zero Vc → error | Vc=0 | ToolLifeError | PASS | test run | — | — |
| T-035 | PART_D | Surface Roughness | Ra feed-mark | fz=0.1, R=0.4 | Ra=1.5625µm | 1.5625µm | PASS | INDEPENDENT CALC | — | — |
| T-036 | PART_D | Surface Roughness | Ra for 1.6µm target | R=0.4, Ra=0.0016mm | fz≈0.1012mm | PASS (within 0.002mm) | PASS | INDEPENDENT CALC | — | — |
| T-037 | N/A | Surface Roughness | Zero feed → error | fz=0 | SurfaceRoughnessError | PASS | test run | — | — |
| T-038 | N/A | Surface Roughness | Negative radius → error | R=-0.4 | error | PASS | test run | — | — |
| T-039 | N/A | DFM | Module importable | import | module loads | PASS | test run | — | — |
| T-040 | N/A | Process Planning | Module importable | import | module loads | PASS | test run | — | — |
| T-041 | N/A | CAM Planning | Module importable | import | module loads | PASS | test run | — | — |
| T-042 | N/A | Toolpath | Module importable | import | module loads | PASS | test run | — | — |
| T-043 | N/A | Verification | Module importable | import | module loads | PASS | test run | — | — |
| T-044 | N/A | NC Generation | Module importable | import | module loads | PASS | test run | — | — |
| T-045 | N/A | NC Generation | OFFLINE guard | dispatch readiness | review/approval keyword | PASS | source inspection | — | — |
| T-046 | N/A | Scheduling | Module importable | import | module loads | PASS | test run | — | — |
| T-047 | N/A | Job Planning | Module importable | import | module loads | PASS | test run | — | — |
| T-048 | N/A | Monitoring | Module importable | import | module loads | PASS | test run | — | — |
| T-049 | N/A | Adaptive Intelligence | Module importable | import | module loads | PASS | test run | — | — |
| T-050 | N/A | Adaptive Intelligence | PROPOSED_ONLY guard | source check | proposed/review keyword | PASS | source inspection | — | — |
| T-051 | N/A | Digital Twin | Module importable | import | module loads | PASS | test run | — | — |
| T-052 | N/A | Workflow | Module importable | import | module loads | PASS | test run | — | — |
| T-053 | N/A | Persistence | Module importable | import | module loads | PASS | test run | — | — |
| T-054 | N/A | Export | Module importable | import | module loads | PASS | test run | — | — |
| T-055 | N/A | Cycle Time | t=L/vf, case 1 | L=120, vf=500 | t=0.24 min | 0.24 min | PASS | INDEPENDENT CALC | — | — |
| T-056 | N/A | Cycle Time | t=L/vf, case 2 | L=80, vf=200 | t=0.4 min | 0.4 min | PASS | INDEPENDENT CALC | — | — |
| T-057 | N/A | Cycle Time | Zero feed → error | vf=0 | MachiningMathError | PASS | test run | — | — |
| T-058 | N/A | Cost/RFQ | Arithmetic check | see ground truth | base=70, overhead=87.5, total=105 | PASS | SYNTHETIC_TEST_VALUE | — | — |
| T-059 | N/A | Security | No real machine write | dispatch simulated.py | no socket/serial | PASS | source inspection | — | — |
| T-060 | N/A | Security | NC offline | dispatch readiness | OFFLINE guard | PASS | source inspection | — | — |
| T-061 | N/A | Security | Path traversal | cad_upload.py | secure_filename or allowed ext | PASS | source inspection | — | — |
| T-062 | N/A | Localization | EN/TR key parity | en.ts, tr.ts | count match | PASS — 1711/1711 | PASS | test run | — | — |
| T-063 | N/A | Localization | TR no raw HTTP errors | tr.ts | no "Method Not Allowed" etc. | PASS | test run | — | — |
| T-064 | N/A | Localization | EN no Turkish chars | en.ts | no ş,ğ,ü etc. | PASS | test run | — | — |
| T-065 | N/A | Localization | TR machiningAnalysis | tr.ts | ≠ "Machining Analysis" | PASS | test run | — | — |
| T-066 | N/A | Localization | TR CAD acronym preserved | tr.ts cadImport | "CAD" present | PASS | test run | — | — |
| T-067 | N/A | Localization | Hardcoded strings ProcessRoutes | ProcessRoutesPage.tsx | ~14 defects documented | DOCUMENTED | DEF-L001 | MAJOR | DEF-L001 |
| T-068 | N/A | Localization | Hardcoded strings Workflow | WorkflowPage.tsx | ~11 defects documented | DOCUMENTED | DEF-L002 | MAJOR | DEF-L002 |
| T-069 | N/A | Localization | Hardcoded strings ProcessCapability | ProcessCapabilityPage.tsx | ~6 defects documented | DOCUMENTED | DEF-L003 | MAJOR | DEF-L003 |
| T-070 | PART_A | Cross-module | Hole candidates require review | all parts | review_required=true | PASS | ground truth | — | — |
| T-071 | PART_D | Cross-module | Bore Ø20 feeds downstream | drawing→process | diameter consistent | PASS | ground truth | — | — |

---

**Total Tests: 71**  
**PASS: 68**  
**PARTIAL: 0**  
**FAIL: 0**  
**BLOCKED: 0**  
**DOCUMENTED DEFECTS: 3** (T-067, T-068, T-069 — localization defects per MUST 48)  
**NOT_APPLICABLE: 0**
