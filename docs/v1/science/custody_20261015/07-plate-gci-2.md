Status: DONE-PASS
Subject: Three-mesh plate GCI across g3, w271b_11772, w271b_11860, w271c_11522 (file 07, pass 2)
Date: 2026-10-15T07:57:47.501697+00:00
Commit: 9a45061449d901315494b81a07742ace1a4282cd

Three-mesh plate families (`max_area = [4.0, 1.0, 0.25] mm^2`, `h = [2.0, 1.0, 0.5] mm`, uniform refinement ratio `r = 2.0`) executed via `fem::report_fields` and evaluated with `fem_solid.gci.compute_gci`:

- `g3` (`evidence/cad_battery/plate_gci/g3.json`, sha256 `93a0a1e461f13bda465afbe23ad286ddd876c8aacca1a93450e923a086285969`):
  - Elements: `3407 -> 7257 -> 26137`
  - `seq_ratio`: `1.0084062169291625 -> 0.9871866057281934 -> 0.9765216896409545` (`admissible_estimate`, `monotone=true`, `p=0.9925256080950314`, `gci_fine=0.013794225201111676` = 1.38% < 3%, `admitted=true`, battery `plate.gci = pass`).
  - `sf_hunter`: `1.3555859370571688 -> 1.3738563412963347 -> 1.3624293593819508` (`oscillatory`, `admitted=false`).
- `w271b_11772` (`evidence/cad_battery/plate_gci/w271b_11772.json`, sha256 `7222e22235b2aa14fcccd44014c1f15db2fcc990a0fc871b2f948cb4a970a8dd`):
  - Elements: `3173 -> 7007 -> 25608`
  - `seq_ratio`: `0.973623051497388 -> 0.9418912612315339 -> 0.8918998553971407` (`nonpositive_order`, `p=-0.6557511798638445`, `admitted=false`, battery `plate.gci = fail`).
  - `sf_hunter`: `1.2163010907398786 -> 1.2324434544632508 -> 1.198917333830571` (`oscillatory`, `admitted=false`).
- `w271b_11860` (`evidence/cad_battery/plate_gci/w271b_11860.json`, sha256 `69ffd66427729ecfd61e5621ba1da5a4d33f91fe3d37a9b4eec42c91f5a67531`):
  - Elements: `3043 -> 6781 -> 24724`
  - `seq_ratio`: `1.0494471358487953 -> 1.0046540651607705 -> 0.917559906566461` (`nonpositive_order`, `p=-0.9593003902133571`, `admitted=false`, battery `plate.gci = fail`).
  - `sf_hunter`: `1.0956365182481433 -> 1.1263561801045698 -> 1.056411492495809` (`oscillatory`, `admitted=false`).
- `w271c_11522` (`evidence/cad_battery/plate_gci/w271c_11522.json`, sha256 `244b1ff25e93f2d1689a1395e4bcdc27b846e834b55bfb37bc71e2e86036f420`):
  - Elements: `3226 -> 7094 -> 25960`
  - `seq_ratio`: `1.0324572029198904 -> 0.8637690380831939 -> 0.8028716606255869` (`admissible_estimate`, `monotone=true`, `p=1.4699067526827305`, `gci_fine=0.053564791694462814` = 5.36% >= 3%, `admitted=true`, battery `plate.gci = pass`, `discretization_under_3pct=false`).
  - `sf_hunter`: `1.2388775044293163 -> 1.1473250478286949 -> 1.0844600516244387` (`admissible_estimate`, `p=0.5423416628804812`, `gci_fine=0.1587896306477363`).
