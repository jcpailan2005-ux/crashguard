# Preserved live decision evidence

Derived only from the preserved JSONL, run `e45af5de2f1a466db95088addfc45a8c`, camera `CAM-30960048ED`. Bboxes retain telemetry precision. Detection/proposal IDs are observation-local. No physical participant attribution is implied.

## Complete post-baseline decision sequence

| OBS | Local timestamp | Qualified | Streak | Action | Reset reasons | Qualification failures | Decision | Score | Vehicles | Start interval s | Inference ms |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 3620 | 2026-09-28T23:20:10.041568 | True | 2 ? 1 | RESET | temporal_window_expired | none | candidate | 0.997121751 | 1 | 4.935052 | 10489.122 |
| 3778 | 2026-09-28T23:20:14.357950 | False | 1 ? 0 | RESET | below_case_threshold | below_case_threshold | ignored | 0.683715940 | 1 | 10.614139 | 4196.626 |
| 3839 | 2026-09-28T23:20:19.464352 | True | 0 ? 1 | START | none | none | candidate | 0.999501467 | 2 | 4.216131 | 5082.920 |
| 3917 | 2026-09-28T23:20:24.957596 | True | 1 ? 1 | RESET | temporal_window_expired | none | candidate | 0.999039948 | 1 | 5.273517 | 5303.859 |
| 3997 | 2026-09-28T23:20:26.706501 | True | 1 ? 2 | INCREMENT | none | none | candidate | 0.957409978 | 1 | 5.502001 | 1551.255 |
| 4022 | 2026-09-28T23:20:31.380793 | True | 2 ? 2 | RESET | temporal_window_expired | none | candidate | 0.987033725 | 2 | 1.653486 | 4568.556 |
| 4093 | 2026-09-28T23:20:50.971614 | True | 2 ? 1 | RESET | temporal_window_expired | none | candidate | 0.999884605 | 1 | 4.804004 | 19357.720 |
| 4348 | 2026-09-28T23:20:53.625708 | True | 1 ? 2 | INCREMENT | none | none | candidate | 0.998201013 | 1 | 19.489980 | 2521.201 |
| 4420 | 2026-09-28T23:20:55.755720 | False | 2 ? 0 | RESET | no_vehicle_detected | no_vehicle_detected | ignored | 0.913120925 | 0 | 2.635596 | 2018.823 |
| 4451 | 2026-09-28T23:20:57.825416 | False | 0 ? 0 | UNCHANGED | none | no_vehicle_detected | ignored | 0.995513141 | 0 | 2.022694 | 2062.192 |
| 4479 | 2026-09-28T23:21:00.997297 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.511756539 | 0 | 2.071217 | 3162.495 |
| 4526 | 2026-09-28T23:21:03.137504 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.454266578 | 0 | 3.170141 | 2133.656 |
| 4558 | 2026-09-28T23:21:04.529503 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.882717550 | 0 | 2.136189 | 1387.935 |
| 4578 | 2026-09-28T23:21:04.912245 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.791972041 | 0 | 1.391999 | 381.881 |
| 4584 | 2026-09-28T23:21:05.447407 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.689051986 | 0 | 0.386757 | 531.278 |
| 4592 | 2026-09-28T23:21:06.627440 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.652940631 | 0 | 0.532659 | 1179.825 |
| 4610 | 2026-09-28T23:21:07.587709 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.764133453 | 0 | 1.186116 | 950.488 |
| 4625 | 2026-09-28T23:21:09.189626 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.848031759 | 0 | 0.956748 | 1599.999 |
| 4649 | 2026-09-28T23:21:10.079482 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.504298151 | 0 | 1.601860 | 886.344 |
| 4662 | 2026-09-28T23:21:11.181238 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.376322389 | 0 | 0.889863 | 1096.764 |
| 4678 | 2026-09-28T23:21:12.475539 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.709753573 | 0 | 1.101759 | 1288.805 |
| 4697 | 2026-09-28T23:21:13.789947 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.241640761 | 0 | 1.294465 | 1311.429 |
| 4717 | 2026-09-28T23:21:15.073113 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.707593560 | 0 | 1.318024 | 1273.298 |
| 4736 | 2026-09-28T23:21:16.321975 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.559931517 | 0 | 1.275360 | 1247.140 |
| 4754 | 2026-09-28T23:21:17.596441 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.603339255 | 0 | 1.254427 | 1268.300 |
| 4773 | 2026-09-28T23:21:18.934450 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.421904147 | 0 | 1.274051 | 1330.981 |
| 4793 | 2026-09-28T23:21:20.267909 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.473288119 | 0 | 1.335878 | 1329.260 |
| 4812 | 2026-09-28T23:21:22.999744 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.858311951 | 0 | 1.334556 | 2725.844 |
| 4851 | 2026-09-28T23:21:24.511760 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.612189353 | 0 | 2.731740 | 1505.376 |
| 4874 | 2026-09-28T23:21:26.221641 | False | 0 ? 0 | UNCHANGED | none | no_vehicle_detected | ignored | 0.934681952 | 0 | 1.512104 | 1706.198 |
| 4900 | 2026-09-28T23:21:28.049464 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.804382145 | 0 | 1.713855 | 1822.527 |
| 4927 | 2026-09-28T23:21:29.251221 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.278842568 | 0 | 1.823768 | 1196.434 |
| 4946 | 2026-09-28T23:21:31.095650 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.860989153 | 0 | 1.206027 | 1835.989 |
| 4973 | 2026-09-28T23:21:32.419437 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.541310906 | 0 | 1.840247 | 1318.053 |
| 4993 | 2026-09-28T23:21:33.613700 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.776242852 | 0 | 1.323689 | 1190.292 |
| 5010 | 2026-09-28T23:21:34.873712 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.387905210 | 0 | 1.198085 | 1249.483 |
| 5028 | 2026-09-28T23:21:35.969421 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.684542298 | 0 | 1.255803 | 1093.002 |
| 5044 | 2026-09-28T23:21:37.543789 | False | 0 ? 0 | UNCHANGED | none | no_vehicle_detected | ignored | 0.901908338 | 0 | 1.099750 | 1567.952 |
| 5068 | 2026-09-28T23:21:38.597458 | False | 0 ? 0 | UNCHANGED | none | no_vehicle_detected | ignored | 0.913987756 | 0 | 1.570209 | 1050.372 |
| 5083 | 2026-09-28T23:21:39.235561 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.244898438 | 0 | 1.053185 | 632.983 |
| 5091 | 2026-09-28T23:21:40.047828 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.760891616 | 0 | 0.639486 | 808.377 |
| 5103 | 2026-09-28T23:21:41.377111 | False | 0 ? 0 | UNCHANGED | none | no_vehicle_detected | ignored | 0.997534156 | 0 | 0.815743 | 1321.530 |
| 5123 | 2026-09-28T23:21:42.364557 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.661105752 | 0 | 1.324526 | 981.166 |
| 5138 | 2026-09-28T23:21:43.683503 | False | 0 ? 0 | UNCHANGED | none | no_vehicle_detected | ignored | 0.924925208 | 0 | 0.988490 | 1315.691 |
| 5157 | 2026-09-28T23:21:44.610101 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.728289783 | 0 | 1.323218 | 920.542 |
| 5171 | 2026-09-28T23:21:45.557650 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.319756567 | 0 | 0.926697 | 936.333 |
| 5184 | 2026-09-28T23:21:46.509013 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.523052394 | 0 | 0.941017 | 949.543 |
| 5199 | 2026-09-28T23:21:47.737444 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.537631810 | 0 | 0.957370 | 1218.284 |
| 5217 | 2026-09-28T23:21:49.507377 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.600603163 | 0 | 1.221086 | 1767.152 |
| 5244 | 2026-09-28T23:21:50.928833 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.488793522 | 0 | 1.773176 | 1417.174 |
| 5265 | 2026-09-28T23:21:53.897166 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.678957403 | 0 | 1.417536 | 2972.144 |
| 5309 | 2026-09-28T23:21:55.692800 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.772457719 | 0 | 2.979436 | 1787.316 |
| 5336 | 2026-09-28T23:21:57.130834 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.805577874 | 0 | 1.789148 | 1431.600 |
| 5357 | 2026-09-28T23:21:58.027143 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.514275193 | 0 | 1.433416 | 896.876 |
| 5370 | 2026-09-28T23:21:58.950951 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.780580938 | 0 | 0.896310 | 914.913 |
| 5384 | 2026-09-28T23:22:01.557323 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.596458673 | 0 | 0.923807 | 2599.374 |
| 5423 | 2026-09-28T23:22:04.933989 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.400715470 | 0 | 2.616616 | 3366.877 |
| 5472 | 2026-09-28T23:22:05.539026 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.722126961 | 0 | 3.369453 | 605.080 |
| 5481 | 2026-09-28T23:22:07.875451 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.828923821 | 0 | 0.606033 | 2330.179 |
| 5516 | 2026-09-28T23:22:11.677914 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.730793476 | 0 | 2.336500 | 3800.173 |
| 5573 | 2026-09-28T23:22:14.807244 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.595695198 | 0 | 3.805924 | 3122.057 |
| 5619 | 2026-09-28T23:22:17.483208 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.566843748 | 0 | 3.130906 | 2668.443 |
| 5660 | 2026-09-28T23:22:18.554970 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.742648721 | 0 | 2.671006 | 1065.343 |
| 5676 | 2026-09-28T23:22:19.450605 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.298253596 | 0 | 1.071758 | 892.193 |
| 5688 | 2026-09-28T23:22:20.947071 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.675232649 | 0 | 0.895583 | 1490.531 |
| 5711 | 2026-09-28T23:22:23.027282 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.545982718 | 0 | 1.492342 | 2077.230 |
| 5742 | 2026-09-28T23:22:24.078271 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.660906553 | 0 | 2.084337 | 1046.565 |
| 5757 | 2026-09-28T23:22:25.190878 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.708136916 | 0 | 1.050873 | 1110.676 |
| 5774 | 2026-09-28T23:22:26.531268 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.714663088 | 0 | 1.115181 | 1335.637 |
| 5794 | 2026-09-28T23:22:27.607283 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.596089065 | 0 | 1.339827 | 1070.616 |
| 5810 | 2026-09-28T23:22:29.267177 | False | 0 ? 0 | UNCHANGED | none | below_case_threshold, no_vehicle_detected | ignored | 0.465274662 | 0 | 1.074013 | 1656.056 |

## Every proposal, evaluated pair, and temporal window

All captured post-baseline observations are included because the physical interaction window cannot be isolated from these records. Empty pair arrays mean no pair was evaluated; no unlogged pair is inferred.

### OBS 3620 ? 2026-09-28T23:20:10.041568

Quality: good; scene valid: True; classifier: 0.9971217513084412 / case threshold 0.9 (PASS); production rejection: temporal_not_verified.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.9100745916366577 | [1.154052734375, 7.7308349609375, 453.0993347167969, 714.164306640625] | 0.4 | False | class_not_vehicle |
| 1 | 0 | motorcycle | 0.6458120942115784 | [659.87939453125, 415.5119323730469, 896.974609375, 669.86669921875] | 0.4 | True | none |
| 2 | 0 | person | 0.583613395690918 | [243.73728942871094, 207.73468017578125, 509.63623046875, 570.9287109375] | 0.4 | False | class_not_vehicle |
| 3 | 0 | other_class | 0.5415400266647339 | [291.2237548828125, 447.51824951171875, 514.924072265625, 714.9862670898438] | 0.4 | False | class_not_vehicle |
| 4 | 0 | other_class | 0.34113654494285583 | [490.4928894042969, 431.4556884765625, 592.37890625, 527.61572265625] | 0.4 | False | class_not_vehicle |
| 5 | 0 | car | 0.33729681372642517 | [566.9822387695312, 379.01025390625, 942.6421508789062, 570.8321533203125] | 0.4 | False | below_vehicle_confidence |
| 6 | 0 | other_class | 0.32822003960609436 | [286.38128662109375, 447.2330322265625, 706.1713256835938, 714.8631591796875] | 0.4 | False | class_not_vehicle |
| 7 | 0 | person | 0.2668636739253998 | [491.49859619140625, 431.74627685546875, 591.6535034179688, 527.8292236328125] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[
  {
    "index": 0,
    "proposal_id": 1,
    "class_name": "motorcycle",
    "confidence": 0.6458120942115784,
    "bbox_xywh": [
      659.87939453125,
      415.5119323730469,
      237.09521484375,
      254.35476684570312
    ]
  }
]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608794.451253,
      true
    ],
    [
      1790608799.4180703,
      true
    ]
  ],
  "window_after": [
    [
      1790608810.041568,
      true
    ]
  ],
  "window_evaluated_at": 1790608810.041568,
  "temporal_window_seconds": 5.0,
  "expired_observations": 2,
  "frame_receive_time": 1790608799.4379876,
  "inference_start": 1790608799.5484118,
  "inference_end": 1790608810.0376775,
  "decision_time": 1790608810.1584702
}
```

### OBS 3778 ? 2026-09-28T23:20:14.357950

Quality: good; scene valid: True; classifier: 0.6837159395217896 / case threshold 0.9 (FAIL); production rejection: temporal_not_verified.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | motorcycle | 0.645774781703949 | [682.2054443359375, 503.479248046875, 913.8570556640625, 719.44775390625] | 0.4 | True | none |
| 1 | 0 | person | 0.5916169881820679 | [0.384613037109375, 51.44683837890625, 394.4721374511719, 714.3345336914062] | 0.4 | False | class_not_vehicle |
| 2 | 0 | other_class | 0.25158247351646423 | [491.5335388183594, 518.0513305664062, 602.3160400390625, 613.1992797851562] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[
  {
    "index": 0,
    "proposal_id": 0,
    "class_name": "motorcycle",
    "confidence": 0.645774781703949,
    "bbox_xywh": [
      682.2054443359375,
      503.479248046875,
      231.651611328125,
      215.968505859375
    ]
  }
]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608810.041568,
      true
    ]
  ],
  "window_after": [
    [
      1790608810.041568,
      true
    ],
    [
      1790608814.3579504,
      false
    ]
  ],
  "window_evaluated_at": 1790608814.3579504,
  "temporal_window_seconds": 5.0,
  "expired_observations": 0,
  "frame_receive_time": 1790608810.137961,
  "inference_start": 1790608810.1625504,
  "inference_end": 1790608814.3579504,
  "decision_time": 1790608814.3579504
}
```

### OBS 3839 ? 2026-09-28T23:20:19.464352

Quality: good; scene valid: True; classifier: 0.9995014667510986 / case threshold 0.9 (PASS); production rejection: temporal_not_verified.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.8484137654304504 | [0.38818359375, 58.27197265625, 396.30291748046875, 713.238037109375] | 0.4 | False | class_not_vehicle |
| 1 | 0 | motorcycle | 0.7802813053131104 | [672.5455322265625, 488.3734130859375, 920.3419189453125, 718.3177490234375] | 0.4 | True | none |
| 2 | 0 | person | 0.7085325121879578 | [258.0794677734375, 291.54388427734375, 522.0447387695312, 640.2056884765625] | 0.4 | False | class_not_vehicle |
| 3 | 0 | motorcycle | 0.4561566114425659 | [918.5928955078125, 304.7529602050781, 1177.0003662109375, 715.545654296875] | 0.4 | True | none |
| 4 | 0 | other_class | 0.37124350666999817 | [303.4886474609375, 527.138427734375, 525.6884765625, 718.93408203125] | 0.4 | False | class_not_vehicle |
| 5 | 0 | car | 0.31722763180732727 | [582.85498046875, 444.7380676269531, 953.4354248046875, 633.30712890625] | 0.4 | False | below_vehicle_confidence |
| 6 | 0 | person | 0.27308186888694763 | [501.7327880859375, 508.63232421875, 603.6243896484375, 603.705810546875] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[
  {
    "index": 0,
    "proposal_id": 1,
    "class_name": "motorcycle",
    "confidence": 0.7802813053131104,
    "bbox_xywh": [
      672.5455322265625,
      488.3734130859375,
      247.79638671875,
      229.9443359375
    ]
  },
  {
    "index": 1,
    "proposal_id": 3,
    "class_name": "motorcycle",
    "confidence": 0.4561566114425659,
    "bbox_xywh": [
      918.5928955078125,
      304.7529602050781,
      258.407470703125,
      410.7926940917969
    ]
  }
]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[
  {
    "vehicle_indices": [
      0,
      1
    ],
    "iou": 0.002441589977715543,
    "edge_distance": 0.0,
    "classes": [
      "motorcycle",
      "motorcycle"
    ],
    "boxes_xywh": [
      [
        672.5455322265625,
        488.3734130859375,
        247.79638671875,
        229.9443359375
      ],
      [
        918.5928955078125,
        304.7529602050781,
        258.407470703125,
        410.7926940917969
      ]
    ],
    "scale": 410.7926940917969,
    "normalized_edge_distance": 0.0,
    "required_iou": 0.08,
    "maximum_normalized_edge_distance": 0.05,
    "qualifies": true
  }
]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608810.041568,
      true
    ],
    [
      1790608814.3579504,
      false
    ]
  ],
  "window_after": [
    [
      1790608819.4643524,
      true
    ]
  ],
  "window_evaluated_at": 1790608819.4643524,
  "temporal_window_seconds": 5.0,
  "expired_observations": 2,
  "frame_receive_time": 1790608814.3476913,
  "inference_start": 1790608814.3786817,
  "inference_end": 1790608819.4603343,
  "decision_time": 1790608819.643725
}
```

### OBS 3917 ? 2026-09-28T23:20:24.957596

Quality: good; scene valid: True; classifier: 0.9990399479866028 / case threshold 0.9 (PASS); production rejection: temporal_not_verified.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.8387150168418884 | [268.54058837890625, 352.8869934082031, 534.2295532226562, 715.079345703125] | 0.4 | False | class_not_vehicle |
| 1 | 0 | person | 0.7822316288948059 | [0.7098388671875, 119.83441162109375, 367.81207275390625, 715.6716918945312] | 0.4 | False | class_not_vehicle |
| 2 | 0 | person | 0.4684707522392273 | [515.4561767578125, 573.910888671875, 617.89404296875, 670.2513427734375] | 0.4 | False | class_not_vehicle |
| 3 | 0 | motorcycle | 0.36855608224868774 | [739.6500244140625, 558.095947265625, 917.98046875, 718.10595703125] | 0.4 | False | below_vehicle_confidence |
| 4 | 1 | person | 0.8387150168418884 | [268.54058837890625, 352.8869934082031, 534.2295532226562, 715.079345703125] | 0.15 | False | class_not_vehicle |
| 5 | 1 | person | 0.7822316288948059 | [0.7098388671875, 119.83441162109375, 367.81207275390625, 715.6716918945312] | 0.15 | False | class_not_vehicle |
| 6 | 1 | person | 0.4684707522392273 | [515.4561767578125, 573.910888671875, 617.89404296875, 670.2513427734375] | 0.15 | False | class_not_vehicle |
| 7 | 1 | motorcycle | 0.36855608224868774 | [739.6500244140625, 558.095947265625, 917.98046875, 718.10595703125] | 0.15 | True | none |

Accepted vehicles (exact production list, bbox xywh):
```json
[
  {
    "index": 0,
    "proposal_id": 7,
    "class_name": "motorcycle",
    "confidence": 0.36855608224868774,
    "bbox_xywh": [
      739.6500244140625,
      558.095947265625,
      178.3304443359375,
      160.010009765625
    ]
  }
]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608819.4643524,
      true
    ]
  ],
  "window_after": [
    [
      1790608824.957596,
      true
    ]
  ],
  "window_evaluated_at": 1790608824.957596,
  "temporal_window_seconds": 5.0,
  "expired_observations": 1,
  "frame_receive_time": 1790608819.6314986,
  "inference_start": 1790608819.6521983,
  "inference_end": 1790608824.957596,
  "decision_time": 1790608825.1458995
}
```

### OBS 3997 ? 2026-09-28T23:20:26.706501

Quality: good; scene valid: True; classifier: 0.9574099779129028 / case threshold 0.9 (PASS); production rejection: temporal_not_verified.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.7719883322715759 | [268.843505859375, 328.8474426269531, 529.867919921875, 714.703857421875] | 0.4 | False | class_not_vehicle |
| 1 | 0 | person | 0.6763046383857727 | [0.89019775390625, 81.55291748046875, 386.61785888671875, 714.9743041992188] | 0.4 | False | class_not_vehicle |
| 2 | 0 | motorcycle | 0.4021548330783844 | [708.0360107421875, 519.080078125, 977.9210205078125, 718.4609375] | 0.4 | True | none |
| 3 | 0 | person | 0.36534541845321655 | [508.48077392578125, 550.0001220703125, 608.8477172851562, 644.3192138671875] | 0.4 | False | class_not_vehicle |
| 4 | 0 | motorcycle | 0.35476940870285034 | [687.8619384765625, 532.6981201171875, 921.8507080078125, 718.8270263671875] | 0.4 | False | below_vehicle_confidence |

Accepted vehicles (exact production list, bbox xywh):
```json
[
  {
    "index": 0,
    "proposal_id": 2,
    "class_name": "motorcycle",
    "confidence": 0.4021548330783844,
    "bbox_xywh": [
      708.0360107421875,
      519.080078125,
      269.885009765625,
      199.380859375
    ]
  }
]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608824.957596,
      true
    ]
  ],
  "window_after": [
    [
      1790608824.957596,
      true
    ],
    [
      1790608826.7065017,
      true
    ]
  ],
  "window_evaluated_at": 1790608826.7065017,
  "temporal_window_seconds": 5.0,
  "expired_observations": 0,
  "frame_receive_time": 1790608825.1178148,
  "inference_start": 1790608825.154199,
  "inference_end": 1790608826.7065017,
  "decision_time": 1790608826.8046103
}
```

### OBS 4022 ? 2026-09-28T23:20:31.380793

Quality: good; scene valid: True; classifier: 0.9870337247848511 / case threshold 0.9 (PASS); production rejection: temporal_not_verified.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.748455286026001 | [262.2510986328125, 326.163330078125, 526.9068603515625, 714.4813232421875] | 0.4 | False | class_not_vehicle |
| 1 | 0 | person | 0.6300815939903259 | [0.61505126953125, 49.67340087890625, 383.2275390625, 717.3390502929688] | 0.4 | False | class_not_vehicle |
| 2 | 0 | motorcycle | 0.35926997661590576 | [691.0401611328125, 508.0972900390625, 958.4573974609375, 716.1116943359375] | 0.4 | False | below_vehicle_confidence |
| 3 | 0 | person | 0.3277393579483032 | [507.30572509765625, 548.0115356445312, 607.3767700195312, 640.8114624023438] | 0.4 | False | class_not_vehicle |
| 4 | 0 | car | 0.271768718957901 | [596.58251953125, 487.5682373046875, 954.0484619140625, 650.5010986328125] | 0.4 | False | below_vehicle_confidence |
| 5 | 1 | person | 0.748455286026001 | [262.2510986328125, 326.163330078125, 526.9068603515625, 714.4813232421875] | 0.15 | False | class_not_vehicle |
| 6 | 1 | person | 0.6300815939903259 | [0.61505126953125, 49.67340087890625, 383.2275390625, 717.3390502929688] | 0.15 | False | class_not_vehicle |
| 7 | 1 | motorcycle | 0.35926997661590576 | [691.0401611328125, 508.0972900390625, 958.4573974609375, 716.1116943359375] | 0.15 | True | none |
| 8 | 1 | person | 0.3277393579483032 | [507.30572509765625, 548.0115356445312, 607.3767700195312, 640.8114624023438] | 0.15 | False | class_not_vehicle |
| 9 | 1 | car | 0.271768718957901 | [596.58251953125, 487.5682373046875, 954.0484619140625, 650.5010986328125] | 0.15 | True | none |

Accepted vehicles (exact production list, bbox xywh):
```json
[
  {
    "index": 0,
    "proposal_id": 7,
    "class_name": "motorcycle",
    "confidence": 0.35926997661590576,
    "bbox_xywh": [
      691.0401611328125,
      508.0972900390625,
      267.417236328125,
      208.014404296875
    ]
  },
  {
    "index": 1,
    "proposal_id": 9,
    "class_name": "car",
    "confidence": 0.271768718957901,
    "bbox_xywh": [
      596.58251953125,
      487.5682373046875,
      357.4659423828125,
      162.932861328125
    ]
  }
]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[
  {
    "vehicle_indices": [
      0,
      1
    ],
    "iou": 0.49012359473137224,
    "edge_distance": 0.0,
    "classes": [
      "motorcycle",
      "car"
    ],
    "boxes_xywh": [
      [
        691.0401611328125,
        508.0972900390625,
        267.417236328125,
        208.014404296875
      ],
      [
        596.58251953125,
        487.5682373046875,
        357.4659423828125,
        162.932861328125
      ]
    ],
    "scale": 357.4659423828125,
    "normalized_edge_distance": 0.0,
    "required_iou": 0.08,
    "maximum_normalized_edge_distance": 0.05,
    "qualifies": true
  }
]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608824.957596,
      true
    ],
    [
      1790608826.7065017,
      true
    ]
  ],
  "window_after": [
    [
      1790608826.7065017,
      true
    ],
    [
      1790608831.3807938,
      true
    ]
  ],
  "window_evaluated_at": 1790608831.3807938,
  "temporal_window_seconds": 5.0,
  "expired_observations": 1,
  "frame_receive_time": 1790608826.7833636,
  "inference_start": 1790608826.807685,
  "inference_end": 1790608831.3766708,
  "decision_time": 1790608831.6116886
}
```

### OBS 4093 ? 2026-09-28T23:20:50.971614

Quality: good; scene valid: True; classifier: 0.9998846054077148 / case threshold 0.9 (PASS); production rejection: temporal_not_verified.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.7933602929115295 | [260.802734375, 335.3155822753906, 528.3216552734375, 713.9957275390625] | 0.4 | False | class_not_vehicle |
| 1 | 0 | person | 0.6969443559646606 | [0.3369140625, 98.14166259765625, 374.51318359375, 715.3268432617188] | 0.4 | False | class_not_vehicle |
| 2 | 0 | motorcycle | 0.43068790435791016 | [695.130615234375, 556.5137329101562, 947.328857421875, 719.3095092773438] | 0.4 | True | none |
| 3 | 0 | person | 0.27733635902404785 | [507.31097412109375, 552.7119140625, 608.8027954101562, 647.10693359375] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[
  {
    "index": 0,
    "proposal_id": 2,
    "class_name": "motorcycle",
    "confidence": 0.43068790435791016,
    "bbox_xywh": [
      695.130615234375,
      556.5137329101562,
      252.1982421875,
      162.7957763671875
    ]
  }
]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608826.7065017,
      true
    ],
    [
      1790608831.3807938,
      true
    ]
  ],
  "window_after": [
    [
      1790608850.971615,
      true
    ]
  ],
  "window_evaluated_at": 1790608850.971615,
  "temporal_window_seconds": 5.0,
  "expired_observations": 2,
  "frame_receive_time": 1790608831.5875375,
  "inference_start": 1790608831.6116886,
  "inference_end": 1790608850.971615,
  "decision_time": 1790608851.0941386
}
```

### OBS 4348 ? 2026-09-28T23:20:53.625708

Quality: good; scene valid: True; classifier: 0.9982010126113892 / case threshold 0.9 (PASS); production rejection: temporal_not_verified.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.8081029653549194 | [259.0379638671875, 326.6270751953125, 524.7767333984375, 714.6234130859375] | 0.4 | False | class_not_vehicle |
| 1 | 0 | person | 0.7136190533638 | [0.444610595703125, 90.45050048828125, 376.42059326171875, 714.8408203125] | 0.4 | False | class_not_vehicle |
| 2 | 0 | motorcycle | 0.6657586097717285 | [701.2841796875, 526.4227294921875, 918.17822265625, 719.4781494140625] | 0.4 | True | none |
| 3 | 0 | person | 0.4622000753879547 | [495.08544921875, 546.319580078125, 606.7197265625, 641.2900390625] | 0.4 | False | class_not_vehicle |
| 4 | 0 | other_class | 0.41503891348838806 | [938.09765625, 328.633544921875, 1206.5087890625, 713.124267578125] | 0.4 | False | class_not_vehicle |
| 5 | 0 | car | 0.3221155107021332 | [588.953369140625, 479.18499755859375, 952.812744140625, 656.0961303710938] | 0.4 | False | below_vehicle_confidence |

Accepted vehicles (exact production list, bbox xywh):
```json
[
  {
    "index": 0,
    "proposal_id": 2,
    "class_name": "motorcycle",
    "confidence": 0.6657586097717285,
    "bbox_xywh": [
      701.2841796875,
      526.4227294921875,
      216.89404296875,
      193.055419921875
    ]
  }
]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608850.971615,
      true
    ]
  ],
  "window_after": [
    [
      1790608850.971615,
      true
    ],
    [
      1790608853.6257088,
      true
    ]
  ],
  "window_evaluated_at": 1790608853.6257088,
  "temporal_window_seconds": 5.0,
  "expired_observations": 0,
  "frame_receive_time": 1790608851.0701954,
  "inference_start": 1790608851.1016686,
  "inference_end": 1790608853.6218674,
  "decision_time": 1790608853.732197
}
```

### OBS 4420 ? 2026-09-28T23:20:55.755720

Quality: good; scene valid: True; classifier: 0.9131209254264832 / case threshold 0.9 (PASS); production rejection: no_vehicle_detected.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | other_class | 0.4826793968677521 | [998.4481201171875, 239.29833984375, 1075.2803955078125, 341.97808837890625] | 0.4 | False | class_not_vehicle |
| 1 | 0 | person | 0.37433314323425293 | [375.36181640625, 352.3791198730469, 1278.5648193359375, 669.49462890625] | 0.4 | False | class_not_vehicle |
| 2 | 1 | other_class | 0.4826793968677521 | [998.4481201171875, 239.29833984375, 1075.2803955078125, 341.97808837890625] | 0.15 | False | class_not_vehicle |
| 3 | 1 | person | 0.37433314323425293 | [375.36181640625, 352.3791198730469, 1278.5648193359375, 669.49462890625] | 0.15 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608850.971615,
      true
    ],
    [
      1790608853.6257088,
      true
    ]
  ],
  "window_after": [
    [
      1790608850.971615,
      true
    ],
    [
      1790608853.6257088,
      true
    ],
    [
      1790608855.7557204,
      false
    ]
  ],
  "window_evaluated_at": 1790608855.7557204,
  "temporal_window_seconds": 5.0,
  "expired_observations": 0,
  "frame_receive_time": 1790608853.7102222,
  "inference_start": 1790608853.7372642,
  "inference_end": 1790608855.7557204,
  "decision_time": 1790608855.7557204
}
```

### OBS 4451 ? 2026-09-28T23:20:57.825416

Quality: good; scene valid: True; classifier: 0.9955131411552429 / case threshold 0.9 (PASS); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.7120206952095032 | [725.05517578125, 7.39044189453125, 1278.0003662109375, 711.4700927734375] | 0.4 | False | class_not_vehicle |
| 1 | 1 | person | 0.7120206952095032 | [725.05517578125, 7.39044189453125, 1278.0003662109375, 711.4700927734375] | 0.15 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608850.971615,
      true
    ],
    [
      1790608853.6257088,
      true
    ],
    [
      1790608855.7557204,
      false
    ]
  ],
  "window_after": [
    [
      1790608853.6257088,
      true
    ],
    [
      1790608855.7557204,
      false
    ],
    [
      1790608857.8254168,
      false
    ]
  ],
  "window_evaluated_at": 1790608857.8254168,
  "temporal_window_seconds": 5.0,
  "expired_observations": 1,
  "frame_receive_time": 1790608855.7401187,
  "inference_start": 1790608855.7599585,
  "inference_end": 1790608857.822786,
  "decision_time": 1790608857.8254168
}
```

### OBS 4479 ? 2026-09-28T23:21:00.997297

Quality: good; scene valid: True; classifier: 0.5117565393447876 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.8331989049911499 | [13.476318359375, 6.8369140625, 958.484130859375, 708.4169921875] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608853.6257088,
      true
    ],
    [
      1790608855.7557204,
      false
    ],
    [
      1790608857.8254168,
      false
    ]
  ],
  "window_after": [
    [
      1790608857.8254168,
      false
    ],
    [
      1790608860.9972968,
      false
    ]
  ],
  "window_evaluated_at": 1790608860.9972968,
  "temporal_window_seconds": 5.0,
  "expired_observations": 2,
  "frame_receive_time": 1790608857.7850912,
  "inference_start": 1790608857.831175,
  "inference_end": 1790608860.9936943,
  "decision_time": 1790608860.9972968
}
```

### OBS 4526 ? 2026-09-28T23:21:03.137504

Quality: good; scene valid: True; classifier: 0.45426657795906067 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.8327122926712036 | [18.23223876953125, 4.92340087890625, 954.592529296875, 708.5172119140625] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608857.8254168,
      false
    ],
    [
      1790608860.9972968,
      false
    ]
  ],
  "window_after": [
    [
      1790608860.9972968,
      false
    ],
    [
      1790608863.1375048,
      false
    ]
  ],
  "window_evaluated_at": 1790608863.1375048,
  "temporal_window_seconds": 5.0,
  "expired_observations": 1,
  "frame_receive_time": 1790608860.9527137,
  "inference_start": 1790608861.001316,
  "inference_end": 1790608863.1375048,
  "decision_time": 1790608863.1375048
}
```

### OBS 4558 ? 2026-09-28T23:21:04.529503

Quality: good; scene valid: True; classifier: 0.8827175498008728 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.9265040755271912 | [4.13812255859375, 7.07244873046875, 954.7581787109375, 711.9884033203125] | 0.4 | False | class_not_vehicle |
| 1 | 0 | other_class | 0.5073928236961365 | [937.2819213867188, 508.29388427734375, 1188.210205078125, 714.7625122070312] | 0.4 | False | class_not_vehicle |
| 2 | 0 | other_class | 0.25682970881462097 | [1230.97900390625, 554.3743286132812, 1279.71484375, 717.6710815429688] | 0.4 | False | class_not_vehicle |
| 3 | 1 | person | 0.9265040755271912 | [4.13812255859375, 7.07244873046875, 954.7581787109375, 711.9884033203125] | 0.15 | False | class_not_vehicle |
| 4 | 1 | other_class | 0.5073928236961365 | [937.2819213867188, 508.29388427734375, 1188.210205078125, 714.7625122070312] | 0.15 | False | class_not_vehicle |
| 5 | 1 | other_class | 0.25682970881462097 | [1230.97900390625, 554.3743286132812, 1279.71484375, 717.6710815429688] | 0.15 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608860.9972968,
      false
    ],
    [
      1790608863.1375048,
      false
    ]
  ],
  "window_after": [
    [
      1790608860.9972968,
      false
    ],
    [
      1790608863.1375048,
      false
    ],
    [
      1790608864.5295036,
      false
    ]
  ],
  "window_evaluated_at": 1790608864.5295036,
  "temporal_window_seconds": 5.0,
  "expired_observations": 0,
  "frame_receive_time": 1790608863.0977535,
  "inference_start": 1790608863.1375048,
  "inference_end": 1790608864.5295036,
  "decision_time": 1790608864.5295036
}
```

### OBS 4578 ? 2026-09-28T23:21:04.912245

Quality: good; scene valid: True; classifier: 0.7919720411300659 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.9278506636619568 | [4.7110595703125, 3.01513671875, 955.1900024414062, 711.2171630859375] | 0.4 | False | class_not_vehicle |
| 1 | 0 | other_class | 0.2684110403060913 | [940.6190795898438, 506.08563232421875, 1191.12939453125, 714.4561157226562] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608860.9972968,
      false
    ],
    [
      1790608863.1375048,
      false
    ],
    [
      1790608864.5295036,
      false
    ]
  ],
  "window_after": [
    [
      1790608860.9972968,
      false
    ],
    [
      1790608863.1375048,
      false
    ],
    [
      1790608864.5295036,
      false
    ],
    [
      1790608864.912246,
      false
    ]
  ],
  "window_evaluated_at": 1790608864.912246,
  "temporal_window_seconds": 5.0,
  "expired_observations": 0,
  "frame_receive_time": 1790608864.4496267,
  "inference_start": 1790608864.5295036,
  "inference_end": 1790608864.912246,
  "decision_time": 1790608864.912246
}
```

### OBS 4584 ? 2026-09-28T23:21:05.447407

Quality: good; scene valid: True; classifier: 0.6890519857406616 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.9371688961982727 | [3.58685302734375, 3.004150390625, 954.8817138671875, 711.75146484375] | 0.4 | False | class_not_vehicle |
| 1 | 0 | other_class | 0.3053973317146301 | [939.3304443359375, 506.24322509765625, 1189.4781494140625, 714.7931518554688] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608860.9972968,
      false
    ],
    [
      1790608863.1375048,
      false
    ],
    [
      1790608864.5295036,
      false
    ],
    [
      1790608864.912246,
      false
    ]
  ],
  "window_after": [
    [
      1790608860.9972968,
      false
    ],
    [
      1790608863.1375048,
      false
    ],
    [
      1790608864.5295036,
      false
    ],
    [
      1790608864.912246,
      false
    ],
    [
      1790608865.447407,
      false
    ]
  ],
  "window_evaluated_at": 1790608865.447407,
  "temporal_window_seconds": 5.0,
  "expired_observations": 0,
  "frame_receive_time": 1790608864.849517,
  "inference_start": 1790608864.9162607,
  "inference_end": 1790608865.447407,
  "decision_time": 1790608865.447407
}
```

### OBS 4592 ? 2026-09-28T23:21:06.627440

Quality: good; scene valid: True; classifier: 0.6529406309127808 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.9374781847000122 | [8.6204833984375, 4.131103515625, 955.0203247070312, 711.8553466796875] | 0.4 | False | class_not_vehicle |
| 1 | 0 | other_class | 0.3819960951805115 | [942.5137329101562, 506.98876953125, 1189.9677734375, 715.4658203125] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608860.9972968,
      false
    ],
    [
      1790608863.1375048,
      false
    ],
    [
      1790608864.5295036,
      false
    ],
    [
      1790608864.912246,
      false
    ],
    [
      1790608865.447407,
      false
    ]
  ],
  "window_after": [
    [
      1790608863.1375048,
      false
    ],
    [
      1790608864.5295036,
      false
    ],
    [
      1790608864.912246,
      false
    ],
    [
      1790608865.447407,
      false
    ],
    [
      1790608866.6274402,
      false
    ]
  ],
  "window_evaluated_at": 1790608866.6274402,
  "temporal_window_seconds": 5.0,
  "expired_observations": 1,
  "frame_receive_time": 1790608865.383457,
  "inference_start": 1790608865.4489193,
  "inference_end": 1790608866.6274402,
  "decision_time": 1790608866.6324677
}
```

### OBS 4610 ? 2026-09-28T23:21:07.587709

Quality: good; scene valid: True; classifier: 0.7641334533691406 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.9103792905807495 | [0.5150146484375, 2.24725341796875, 955.5046997070312, 710.550537109375] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608863.1375048,
      false
    ],
    [
      1790608864.5295036,
      false
    ],
    [
      1790608864.912246,
      false
    ],
    [
      1790608865.447407,
      false
    ],
    [
      1790608866.6274402,
      false
    ]
  ],
  "window_after": [
    [
      1790608863.1375048,
      false
    ],
    [
      1790608864.5295036,
      false
    ],
    [
      1790608864.912246,
      false
    ],
    [
      1790608865.447407,
      false
    ],
    [
      1790608866.6274402,
      false
    ],
    [
      1790608867.5877092,
      false
    ]
  ],
  "window_evaluated_at": 1790608867.5877092,
  "temporal_window_seconds": 5.0,
  "expired_observations": 0,
  "frame_receive_time": 1790608866.579441,
  "inference_start": 1790608866.635035,
  "inference_end": 1790608867.5841722,
  "decision_time": 1790608867.5877092
}
```

### OBS 4625 ? 2026-09-28T23:21:09.189626

Quality: good; scene valid: True; classifier: 0.848031759262085 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.9012661576271057 | [2.3525390625, 6.04833984375, 956.429443359375, 710.0980224609375] | 0.4 | False | class_not_vehicle |
| 1 | 1 | person | 0.9012661576271057 | [2.3525390625, 6.04833984375, 956.429443359375, 710.0980224609375] | 0.15 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608863.1375048,
      false
    ],
    [
      1790608864.5295036,
      false
    ],
    [
      1790608864.912246,
      false
    ],
    [
      1790608865.447407,
      false
    ],
    [
      1790608866.6274402,
      false
    ],
    [
      1790608867.5877092,
      false
    ]
  ],
  "window_after": [
    [
      1790608864.5295036,
      false
    ],
    [
      1790608864.912246,
      false
    ],
    [
      1790608865.447407,
      false
    ],
    [
      1790608866.6274402,
      false
    ],
    [
      1790608867.5877092,
      false
    ],
    [
      1790608869.1896265,
      false
    ]
  ],
  "window_evaluated_at": 1790608869.1896265,
  "temporal_window_seconds": 5.0,
  "expired_observations": 1,
  "frame_receive_time": 1790608867.577602,
  "inference_start": 1790608867.5917835,
  "inference_end": 1790608869.1896265,
  "decision_time": 1790608869.1896265
}
```

### OBS 4649 ? 2026-09-28T23:21:10.079482

Quality: good; scene valid: True; classifier: 0.5042981505393982 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.6379839777946472 | [78.4090576171875, 6.79632568359375, 924.755615234375, 710.0983276367188] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608864.5295036,
      false
    ],
    [
      1790608864.912246,
      false
    ],
    [
      1790608865.447407,
      false
    ],
    [
      1790608866.6274402,
      false
    ],
    [
      1790608867.5877092,
      false
    ],
    [
      1790608869.1896265,
      false
    ]
  ],
  "window_after": [
    [
      1790608865.447407,
      false
    ],
    [
      1790608866.6274402,
      false
    ],
    [
      1790608867.5877092,
      false
    ],
    [
      1790608869.1896265,
      false
    ],
    [
      1790608870.0794826,
      false
    ]
  ],
  "window_evaluated_at": 1790608870.0794826,
  "temporal_window_seconds": 5.0,
  "expired_observations": 2,
  "frame_receive_time": 1790608869.1729279,
  "inference_start": 1790608869.1936438,
  "inference_end": 1790608870.0794826,
  "decision_time": 1790608870.0794826
}
```

### OBS 4662 ? 2026-09-28T23:21:11.181238

Quality: good; scene valid: True; classifier: 0.3763223886489868 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.7490667700767517 | [333.0152587890625, 1.62176513671875, 973.485595703125, 705.307373046875] | 0.4 | False | class_not_vehicle |
| 1 | 0 | other_class | 0.2963297963142395 | [0.129638671875, 185.798095703125, 953.6434326171875, 706.8798828125] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608865.447407,
      false
    ],
    [
      1790608866.6274402,
      false
    ],
    [
      1790608867.5877092,
      false
    ],
    [
      1790608869.1896265,
      false
    ],
    [
      1790608870.0794826,
      false
    ]
  ],
  "window_after": [
    [
      1790608866.6274402,
      false
    ],
    [
      1790608867.5877092,
      false
    ],
    [
      1790608869.1896265,
      false
    ],
    [
      1790608870.0794826,
      false
    ],
    [
      1790608871.1812382,
      false
    ]
  ],
  "window_evaluated_at": 1790608871.1812382,
  "temporal_window_seconds": 5.0,
  "expired_observations": 1,
  "frame_receive_time": 1790608870.063716,
  "inference_start": 1790608870.0835063,
  "inference_end": 1790608871.1777174,
  "decision_time": 1790608871.1812382
}
```

### OBS 4678 ? 2026-09-28T23:21:12.475539

Quality: good; scene valid: True; classifier: 0.7097535729408264 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.8111281394958496 | [55.830078125, 0.0, 1057.51953125, 712.4658813476562] | 0.4 | False | class_not_vehicle |
| 1 | 0 | other_class | 0.3427724242210388 | [1229.30859375, 537.215576171875, 1279.733642578125, 718.001953125] | 0.4 | False | class_not_vehicle |
| 2 | 0 | other_class | 0.2641541659832001 | [1065.2041015625, 534.9761962890625, 1190.766845703125, 716.7947998046875] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608866.6274402,
      false
    ],
    [
      1790608867.5877092,
      false
    ],
    [
      1790608869.1896265,
      false
    ],
    [
      1790608870.0794826,
      false
    ],
    [
      1790608871.1812382,
      false
    ]
  ],
  "window_after": [
    [
      1790608867.5877092,
      false
    ],
    [
      1790608869.1896265,
      false
    ],
    [
      1790608870.0794826,
      false
    ],
    [
      1790608871.1812382,
      false
    ],
    [
      1790608872.4755394,
      false
    ]
  ],
  "window_evaluated_at": 1790608872.4755394,
  "temporal_window_seconds": 5.0,
  "expired_observations": 1,
  "frame_receive_time": 1790608871.147314,
  "inference_start": 1790608871.185265,
  "inference_end": 1790608872.4714434,
  "decision_time": 1790608872.4755394
}
```

### OBS 4697 ? 2026-09-28T23:21:13.789947

Quality: good; scene valid: True; classifier: 0.24164076149463654 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.8972256779670715 | [0.0, 7.50469970703125, 1015.1004638671875, 711.3908081054688] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608867.5877092,
      false
    ],
    [
      1790608869.1896265,
      false
    ],
    [
      1790608870.0794826,
      false
    ],
    [
      1790608871.1812382,
      false
    ],
    [
      1790608872.4755394,
      false
    ]
  ],
  "window_after": [
    [
      1790608869.1896265,
      false
    ],
    [
      1790608870.0794826,
      false
    ],
    [
      1790608871.1812382,
      false
    ],
    [
      1790608872.4755394,
      false
    ],
    [
      1790608873.7899475,
      false
    ]
  ],
  "window_evaluated_at": 1790608873.7899475,
  "temporal_window_seconds": 5.0,
  "expired_observations": 1,
  "frame_receive_time": 1790608872.3927517,
  "inference_start": 1790608872.4797301,
  "inference_end": 1790608873.7899475,
  "decision_time": 1790608873.7899475
}
```

### OBS 4717 ? 2026-09-28T23:21:15.073113

Quality: good; scene valid: True; classifier: 0.707593560218811 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.922055184841156 | [5.2342529296875, 8.27069091796875, 1123.1685791015625, 710.8605346679688] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608869.1896265,
      false
    ],
    [
      1790608870.0794826,
      false
    ],
    [
      1790608871.1812382,
      false
    ],
    [
      1790608872.4755394,
      false
    ],
    [
      1790608873.7899475,
      false
    ]
  ],
  "window_after": [
    [
      1790608870.0794826,
      false
    ],
    [
      1790608871.1812382,
      false
    ],
    [
      1790608872.4755394,
      false
    ],
    [
      1790608873.7899475,
      false
    ],
    [
      1790608875.073114,
      false
    ]
  ],
  "window_evaluated_at": 1790608875.073114,
  "temporal_window_seconds": 5.0,
  "expired_observations": 1,
  "frame_receive_time": 1790608873.7855995,
  "inference_start": 1790608873.797754,
  "inference_end": 1790608875.073114,
  "decision_time": 1790608875.073114
}
```

### OBS 4736 ? 2026-09-28T23:21:16.321975

Quality: good; scene valid: True; classifier: 0.5599315166473389 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.8814007043838501 | [127.55636596679688, 5.5657958984375, 1035.41015625, 711.6937255859375] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608870.0794826,
      false
    ],
    [
      1790608871.1812382,
      false
    ],
    [
      1790608872.4755394,
      false
    ],
    [
      1790608873.7899475,
      false
    ],
    [
      1790608875.073114,
      false
    ]
  ],
  "window_after": [
    [
      1790608872.4755394,
      false
    ],
    [
      1790608873.7899475,
      false
    ],
    [
      1790608875.073114,
      false
    ],
    [
      1790608876.3219752,
      false
    ]
  ],
  "window_evaluated_at": 1790608876.3219752,
  "temporal_window_seconds": 5.0,
  "expired_observations": 2,
  "frame_receive_time": 1790608875.0530214,
  "inference_start": 1790608875.073114,
  "inference_end": 1790608876.3219752,
  "decision_time": 1790608876.3219752
}
```

### OBS 4754 ? 2026-09-28T23:21:17.596441

Quality: good; scene valid: True; classifier: 0.6033392548561096 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.882196843624115 | [23.5958251953125, 1.5302734375, 1068.101806640625, 714.918701171875] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608872.4755394,
      false
    ],
    [
      1790608873.7899475,
      false
    ],
    [
      1790608875.073114,
      false
    ],
    [
      1790608876.3219752,
      false
    ]
  ],
  "window_after": [
    [
      1790608873.7899475,
      false
    ],
    [
      1790608875.073114,
      false
    ],
    [
      1790608876.3219752,
      false
    ],
    [
      1790608877.5964415,
      false
    ]
  ],
  "window_evaluated_at": 1790608877.5964415,
  "temporal_window_seconds": 5.0,
  "expired_observations": 1,
  "frame_receive_time": 1790608876.2528315,
  "inference_start": 1790608876.3275409,
  "inference_end": 1790608877.59232,
  "decision_time": 1790608877.5975485
}
```

### OBS 4773 ? 2026-09-28T23:21:18.934450

Quality: good; scene valid: True; classifier: 0.42190414667129517 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.9047940373420715 | [13.366943359375, 4.39617919921875, 1087.510986328125, 710.7072143554688] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608873.7899475,
      false
    ],
    [
      1790608875.073114,
      false
    ],
    [
      1790608876.3219752,
      false
    ],
    [
      1790608877.5964415,
      false
    ]
  ],
  "window_after": [
    [
      1790608875.073114,
      false
    ],
    [
      1790608876.3219752,
      false
    ],
    [
      1790608877.5964415,
      false
    ],
    [
      1790608878.93445,
      false
    ]
  ],
  "window_evaluated_at": 1790608878.93445,
  "temporal_window_seconds": 5.0,
  "expired_observations": 1,
  "frame_receive_time": 1790608877.5506263,
  "inference_start": 1790608877.6015916,
  "inference_end": 1790608878.9342663,
  "decision_time": 1790608878.93445
}
```

### OBS 4793 ? 2026-09-28T23:21:20.267909

Quality: good; scene valid: True; classifier: 0.4732881188392639 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.9011763334274292 | [0.0, 2.4053955078125, 1089.0631103515625, 714.36669921875] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608875.073114,
      false
    ],
    [
      1790608876.3219752,
      false
    ],
    [
      1790608877.5964415,
      false
    ],
    [
      1790608878.93445,
      false
    ]
  ],
  "window_after": [
    [
      1790608876.3219752,
      false
    ],
    [
      1790608877.5964415,
      false
    ],
    [
      1790608878.93445,
      false
    ],
    [
      1790608880.267909,
      false
    ]
  ],
  "window_evaluated_at": 1790608880.267909,
  "temporal_window_seconds": 5.0,
  "expired_observations": 1,
  "frame_receive_time": 1790608878.9006448,
  "inference_start": 1790608878.9374695,
  "inference_end": 1790608880.2634892,
  "decision_time": 1790608880.267909
}
```

### OBS 4812 ? 2026-09-28T23:21:22.999744

Quality: good; scene valid: True; classifier: 0.8583119511604309 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.7713753581047058 | [249.548095703125, 11.4227294921875, 1070.2373046875, 713.0391845703125] | 0.4 | False | class_not_vehicle |
| 1 | 0 | person | 0.2942468225955963 | [1230.6865234375, 545.8580322265625, 1279.5390625, 720.0] | 0.4 | False | class_not_vehicle |
| 2 | 1 | person | 0.7713753581047058 | [249.548095703125, 11.4227294921875, 1070.2373046875, 713.0391845703125] | 0.15 | False | class_not_vehicle |
| 3 | 1 | person | 0.2942468225955963 | [1230.6865234375, 545.8580322265625, 1279.5390625, 720.0] | 0.15 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608876.3219752,
      false
    ],
    [
      1790608877.5964415,
      false
    ],
    [
      1790608878.93445,
      false
    ],
    [
      1790608880.267909,
      false
    ]
  ],
  "window_after": [
    [
      1790608878.93445,
      false
    ],
    [
      1790608880.267909,
      false
    ],
    [
      1790608882.9997444,
      false
    ]
  ],
  "window_evaluated_at": 1790608882.9997444,
  "temporal_window_seconds": 5.0,
  "expired_observations": 2,
  "frame_receive_time": 1790608880.2512474,
  "inference_start": 1790608880.2720258,
  "inference_end": 1790608882.9997444,
  "decision_time": 1790608882.9997444
}
```

### OBS 4851 ? 2026-09-28T23:21:24.511760

Quality: good; scene valid: True; classifier: 0.6121893525123596 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.8981610536575317 | [163.670166015625, 3.50799560546875, 1095.8857421875, 714.313232421875] | 0.4 | False | class_not_vehicle |
| 1 | 0 | other_class | 0.2791863977909088 | [1035.044921875, 505.8272705078125, 1191.08740234375, 717.1522216796875] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608878.93445,
      false
    ],
    [
      1790608880.267909,
      false
    ],
    [
      1790608882.9997444,
      false
    ]
  ],
  "window_after": [
    [
      1790608880.267909,
      false
    ],
    [
      1790608882.9997444,
      false
    ],
    [
      1790608884.511761,
      false
    ]
  ],
  "window_evaluated_at": 1790608884.511761,
  "temporal_window_seconds": 5.0,
  "expired_observations": 1,
  "frame_receive_time": 1790608882.9373312,
  "inference_start": 1790608883.0037656,
  "inference_end": 1790608884.511761,
  "decision_time": 1790608884.511761
}
```

### OBS 4874 ? 2026-09-28T23:21:26.221641

Quality: good; scene valid: True; classifier: 0.9346819519996643 / case threshold 0.9 (PASS); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.9111748933792114 | [159.2957763671875, 4.0185546875, 1100.1328125, 714.67431640625] | 0.4 | False | class_not_vehicle |
| 1 | 0 | other_class | 0.2581469416618347 | [252.2352294921875, 290.7593994140625, 412.40167236328125, 443.2510986328125] | 0.4 | False | class_not_vehicle |
| 2 | 1 | person | 0.9111748933792114 | [159.2957763671875, 4.0185546875, 1100.1328125, 714.67431640625] | 0.15 | False | class_not_vehicle |
| 3 | 1 | other_class | 0.2581469416618347 | [252.2352294921875, 290.7593994140625, 412.40167236328125, 443.2510986328125] | 0.15 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608880.267909,
      false
    ],
    [
      1790608882.9997444,
      false
    ],
    [
      1790608884.511761,
      false
    ]
  ],
  "window_after": [
    [
      1790608882.9997444,
      false
    ],
    [
      1790608884.511761,
      false
    ],
    [
      1790608886.2216415,
      false
    ]
  ],
  "window_evaluated_at": 1790608886.2216415,
  "temporal_window_seconds": 5.0,
  "expired_observations": 1,
  "frame_receive_time": 1790608884.4595947,
  "inference_start": 1790608884.5158699,
  "inference_end": 1790608886.2216415,
  "decision_time": 1790608886.2216415
}
```

### OBS 4900 ? 2026-09-28T23:21:28.049464

Quality: good; scene valid: True; classifier: 0.8043821454048157 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.8773576021194458 | [0.0, 5.0426025390625, 1019.010986328125, 666.34716796875] | 0.4 | False | class_not_vehicle |
| 1 | 1 | person | 0.8773576021194458 | [0.0, 5.0426025390625, 1019.010986328125, 666.34716796875] | 0.15 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608882.9997444,
      false
    ],
    [
      1790608884.511761,
      false
    ],
    [
      1790608886.2216415,
      false
    ]
  ],
  "window_after": [
    [
      1790608884.511761,
      false
    ],
    [
      1790608886.2216415,
      false
    ],
    [
      1790608888.049465,
      false
    ]
  ],
  "window_evaluated_at": 1790608888.049465,
  "temporal_window_seconds": 5.0,
  "expired_observations": 1,
  "frame_receive_time": 1790608886.2176201,
  "inference_start": 1790608886.2297251,
  "inference_end": 1790608888.049465,
  "decision_time": 1790608888.049465
}
```

### OBS 4927 ? 2026-09-28T23:21:29.251221

Quality: good; scene valid: True; classifier: 0.278842568397522 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.9092200398445129 | [5.851043701171875, 5.2840576171875, 1029.1201171875, 708.0084228515625] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608884.511761,
      false
    ],
    [
      1790608886.2216415,
      false
    ],
    [
      1790608888.049465,
      false
    ]
  ],
  "window_after": [
    [
      1790608884.511761,
      false
    ],
    [
      1790608886.2216415,
      false
    ],
    [
      1790608888.049465,
      false
    ],
    [
      1790608889.251221,
      false
    ]
  ],
  "window_evaluated_at": 1790608889.251221,
  "temporal_window_seconds": 5.0,
  "expired_observations": 0,
  "frame_receive_time": 1790608888.0146685,
  "inference_start": 1790608888.0534933,
  "inference_end": 1790608889.251221,
  "decision_time": 1790608889.251221
}
```

### OBS 4946 ? 2026-09-28T23:21:31.095650

Quality: good; scene valid: True; classifier: 0.8609891533851624 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.8750686049461365 | [94.46200561523438, 4.809814453125, 1021.9481201171875, 702.0888671875] | 0.4 | False | class_not_vehicle |
| 1 | 1 | person | 0.8750686049461365 | [94.46200561523438, 4.809814453125, 1021.9481201171875, 702.0888671875] | 0.15 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608884.511761,
      false
    ],
    [
      1790608886.2216415,
      false
    ],
    [
      1790608888.049465,
      false
    ],
    [
      1790608889.251221,
      false
    ]
  ],
  "window_after": [
    [
      1790608886.2216415,
      false
    ],
    [
      1790608888.049465,
      false
    ],
    [
      1790608889.251221,
      false
    ],
    [
      1790608891.0956502,
      false
    ]
  ],
  "window_evaluated_at": 1790608891.0956502,
  "temporal_window_seconds": 5.0,
  "expired_observations": 1,
  "frame_receive_time": 1790608889.2471933,
  "inference_start": 1790608889.2595203,
  "inference_end": 1790608891.0956502,
  "decision_time": 1790608891.0956502
}
```

### OBS 4973 ? 2026-09-28T23:21:32.419437

Quality: good; scene valid: True; classifier: 0.5413109064102173 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.8951151967048645 | [0.56536865234375, 6.713134765625, 1019.0379638671875, 651.684814453125] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608886.2216415,
      false
    ],
    [
      1790608888.049465,
      false
    ],
    [
      1790608889.251221,
      false
    ],
    [
      1790608891.0956502,
      false
    ]
  ],
  "window_after": [
    [
      1790608888.049465,
      false
    ],
    [
      1790608889.251221,
      false
    ],
    [
      1790608891.0956502,
      false
    ],
    [
      1790608892.419438,
      false
    ]
  ],
  "window_evaluated_at": 1790608892.419438,
  "temporal_window_seconds": 5.0,
  "expired_observations": 1,
  "frame_receive_time": 1790608891.0672905,
  "inference_start": 1790608891.0997672,
  "inference_end": 1790608892.419438,
  "decision_time": 1790608892.419438
}
```

### OBS 4993 ? 2026-09-28T23:21:33.613700

Quality: good; scene valid: True; classifier: 0.7762428522109985 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.9123475551605225 | [0.0, 4.16522216796875, 1015.9913940429688, 648.2412109375] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608888.049465,
      false
    ],
    [
      1790608889.251221,
      false
    ],
    [
      1790608891.0956502,
      false
    ],
    [
      1790608892.419438,
      false
    ]
  ],
  "window_after": [
    [
      1790608889.251221,
      false
    ],
    [
      1790608891.0956502,
      false
    ],
    [
      1790608892.419438,
      false
    ],
    [
      1790608893.6137006,
      false
    ]
  ],
  "window_evaluated_at": 1790608893.6137006,
  "temporal_window_seconds": 5.0,
  "expired_observations": 1,
  "frame_receive_time": 1790608892.4153848,
  "inference_start": 1790608892.4234567,
  "inference_end": 1790608893.6137006,
  "decision_time": 1790608893.6173632
}
```

### OBS 5010 ? 2026-09-28T23:21:34.873712

Quality: good; scene valid: True; classifier: 0.38790521025657654 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.8865444660186768 | [1.8192138671875, 4.43902587890625, 1031.0980224609375, 707.7938232421875] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608889.251221,
      false
    ],
    [
      1790608891.0956502,
      false
    ],
    [
      1790608892.419438,
      false
    ],
    [
      1790608893.6137006,
      false
    ]
  ],
  "window_after": [
    [
      1790608891.0956502,
      false
    ],
    [
      1790608892.419438,
      false
    ],
    [
      1790608893.6137006,
      false
    ],
    [
      1790608894.8737123,
      false
    ]
  ],
  "window_evaluated_at": 1790608894.8737123,
  "temporal_window_seconds": 5.0,
  "expired_observations": 1,
  "frame_receive_time": 1790608893.5738547,
  "inference_start": 1790608893.6215417,
  "inference_end": 1790608894.8697016,
  "decision_time": 1790608894.8737123
}
```

### OBS 5028 ? 2026-09-28T23:21:35.969421

Quality: good; scene valid: True; classifier: 0.6845422983169556 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.8738903403282166 | [0.0, 7.45330810546875, 1018.7054443359375, 662.1109619140625] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608891.0956502,
      false
    ],
    [
      1790608892.419438,
      false
    ],
    [
      1790608893.6137006,
      false
    ],
    [
      1790608894.8737123,
      false
    ]
  ],
  "window_after": [
    [
      1790608891.0956502,
      false
    ],
    [
      1790608892.419438,
      false
    ],
    [
      1790608893.6137006,
      false
    ],
    [
      1790608894.8737123,
      false
    ],
    [
      1790608895.9694216,
      false
    ]
  ],
  "window_evaluated_at": 1790608895.9694216,
  "temporal_window_seconds": 5.0,
  "expired_observations": 0,
  "frame_receive_time": 1790608894.824461,
  "inference_start": 1790608894.8773444,
  "inference_end": 1790608895.9694216,
  "decision_time": 1790608895.9694216
}
```

### OBS 5044 ? 2026-09-28T23:21:37.543789

Quality: good; scene valid: True; classifier: 0.9019083380699158 / case threshold 0.9 (PASS); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.8937206864356995 | [209.02804565429688, 5.21826171875, 1157.7216796875, 711.7136840820312] | 0.4 | False | class_not_vehicle |
| 1 | 1 | person | 0.8937206864356995 | [209.02804565429688, 5.21826171875, 1157.7216796875, 711.7136840820312] | 0.15 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608891.0956502,
      false
    ],
    [
      1790608892.419438,
      false
    ],
    [
      1790608893.6137006,
      false
    ],
    [
      1790608894.8737123,
      false
    ],
    [
      1790608895.9694216,
      false
    ]
  ],
  "window_after": [
    [
      1790608893.6137006,
      false
    ],
    [
      1790608894.8737123,
      false
    ],
    [
      1790608895.9694216,
      false
    ],
    [
      1790608897.5437894,
      false
    ]
  ],
  "window_evaluated_at": 1790608897.5437894,
  "temporal_window_seconds": 5.0,
  "expired_observations": 2,
  "frame_receive_time": 1790608895.94134,
  "inference_start": 1790608895.9770947,
  "inference_end": 1790608897.5437894,
  "decision_time": 1790608897.5437894
}
```

### OBS 5068 ? 2026-09-28T23:21:38.597458

Quality: good; scene valid: True; classifier: 0.9139877557754517 / case threshold 0.9 (PASS); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.9131186008453369 | [161.873291015625, 7.987548828125, 1117.642578125, 713.3067626953125] | 0.4 | False | class_not_vehicle |
| 1 | 1 | person | 0.9131186008453369 | [161.873291015625, 7.987548828125, 1117.642578125, 713.3067626953125] | 0.15 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608893.6137006,
      false
    ],
    [
      1790608894.8737123,
      false
    ],
    [
      1790608895.9694216,
      false
    ],
    [
      1790608897.5437894,
      false
    ]
  ],
  "window_after": [
    [
      1790608893.6137006,
      false
    ],
    [
      1790608894.8737123,
      false
    ],
    [
      1790608895.9694216,
      false
    ],
    [
      1790608897.5437894,
      false
    ],
    [
      1790608898.5974584,
      false
    ]
  ],
  "window_evaluated_at": 1790608898.5974584,
  "temporal_window_seconds": 5.0,
  "expired_observations": 0,
  "frame_receive_time": 1790608897.5373333,
  "inference_start": 1790608897.5473037,
  "inference_end": 1790608898.5974584,
  "decision_time": 1790608898.5974584
}
```

### OBS 5083 ? 2026-09-28T23:21:39.235561

Quality: good; scene valid: True; classifier: 0.24489843845367432 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.8992723822593689 | [9.5823974609375, 8.86822509765625, 1103.1165771484375, 713.7633056640625] | 0.4 | False | class_not_vehicle |
| 1 | 0 | other_class | 0.25371652841567993 | [986.7649536132812, 223.03826904296875, 1225.964599609375, 683.9227905273438] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608893.6137006,
      false
    ],
    [
      1790608894.8737123,
      false
    ],
    [
      1790608895.9694216,
      false
    ],
    [
      1790608897.5437894,
      false
    ],
    [
      1790608898.5974584,
      false
    ]
  ],
  "window_after": [
    [
      1790608894.8737123,
      false
    ],
    [
      1790608895.9694216,
      false
    ],
    [
      1790608897.5437894,
      false
    ],
    [
      1790608898.5974584,
      false
    ],
    [
      1790608899.2355611,
      false
    ]
  ],
  "window_evaluated_at": 1790608899.2355611,
  "temporal_window_seconds": 5.0,
  "expired_observations": 1,
  "frame_receive_time": 1790608898.580014,
  "inference_start": 1790608898.600489,
  "inference_end": 1790608899.2355611,
  "decision_time": 1790608899.2355611
}
```

### OBS 5091 ? 2026-09-28T23:21:40.047828

Quality: good; scene valid: True; classifier: 0.7608916163444519 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.9079506993293762 | [156.616943359375, 1.13671875, 1142.74951171875, 711.6971435546875] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608894.8737123,
      false
    ],
    [
      1790608895.9694216,
      false
    ],
    [
      1790608897.5437894,
      false
    ],
    [
      1790608898.5974584,
      false
    ],
    [
      1790608899.2355611,
      false
    ]
  ],
  "window_after": [
    [
      1790608895.9694216,
      false
    ],
    [
      1790608897.5437894,
      false
    ],
    [
      1790608898.5974584,
      false
    ],
    [
      1790608899.2355611,
      false
    ],
    [
      1790608900.0478287,
      false
    ]
  ],
  "window_evaluated_at": 1790608900.0478287,
  "temporal_window_seconds": 5.0,
  "expired_observations": 1,
  "frame_receive_time": 1790608899.1676955,
  "inference_start": 1790608899.2399745,
  "inference_end": 1790608900.0478287,
  "decision_time": 1790608900.0478287
}
```

### OBS 5103 ? 2026-09-28T23:21:41.377111

Quality: good; scene valid: True; classifier: 0.9975341558456421 / case threshold 0.9 (PASS); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.8821061253547668 | [72.70068359375, 4.89422607421875, 1076.153564453125, 709.7442626953125] | 0.4 | False | class_not_vehicle |
| 1 | 1 | person | 0.8821061253547668 | [72.70068359375, 4.89422607421875, 1076.153564453125, 709.7442626953125] | 0.15 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608895.9694216,
      false
    ],
    [
      1790608897.5437894,
      false
    ],
    [
      1790608898.5974584,
      false
    ],
    [
      1790608899.2355611,
      false
    ],
    [
      1790608900.0478287,
      false
    ]
  ],
  "window_after": [
    [
      1790608897.5437894,
      false
    ],
    [
      1790608898.5974584,
      false
    ],
    [
      1790608899.2355611,
      false
    ],
    [
      1790608900.0478287,
      false
    ],
    [
      1790608901.377112,
      false
    ]
  ],
  "window_evaluated_at": 1790608901.377112,
  "temporal_window_seconds": 5.0,
  "expired_observations": 1,
  "frame_receive_time": 1790608899.989992,
  "inference_start": 1790608900.0557177,
  "inference_end": 1790608901.377112,
  "decision_time": 1790608901.377112
}
```

### OBS 5123 ? 2026-09-28T23:21:42.364557

Quality: good; scene valid: True; classifier: 0.661105751991272 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.9389991164207458 | [0.5616455078125, 9.34588623046875, 946.581787109375, 710.7630615234375] | 0.4 | False | class_not_vehicle |
| 1 | 0 | person | 0.25124847888946533 | [1228.9315185546875, 531.4595947265625, 1279.7208251953125, 717.5013427734375] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608897.5437894,
      false
    ],
    [
      1790608898.5974584,
      false
    ],
    [
      1790608899.2355611,
      false
    ],
    [
      1790608900.0478287,
      false
    ],
    [
      1790608901.377112,
      false
    ]
  ],
  "window_after": [
    [
      1790608897.5437894,
      false
    ],
    [
      1790608898.5974584,
      false
    ],
    [
      1790608899.2355611,
      false
    ],
    [
      1790608900.0478287,
      false
    ],
    [
      1790608901.377112,
      false
    ],
    [
      1790608902.3645573,
      false
    ]
  ],
  "window_evaluated_at": 1790608902.3645573,
  "temporal_window_seconds": 5.0,
  "expired_observations": 0,
  "frame_receive_time": 1790608901.2870934,
  "inference_start": 1790608901.3802435,
  "inference_end": 1790608902.360539,
  "decision_time": 1790608902.3645573
}
```

### OBS 5138 ? 2026-09-28T23:21:43.683503

Quality: good; scene valid: True; classifier: 0.9249252080917358 / case threshold 0.9 (PASS); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.8237017393112183 | [3.3045654296875, 14.4532470703125, 945.312255859375, 711.7022705078125] | 0.4 | False | class_not_vehicle |
| 1 | 0 | other_class | 0.27023786306381226 | [283.72021484375, 147.26315307617188, 567.4854736328125, 422.7099304199219] | 0.4 | False | class_not_vehicle |
| 2 | 0 | other_class | 0.2527827322483063 | [304.11090087890625, 147.92620849609375, 569.000244140625, 413.681396484375] | 0.4 | False | class_not_vehicle |
| 3 | 1 | person | 0.8237017393112183 | [3.3045654296875, 14.4532470703125, 945.312255859375, 711.7022705078125] | 0.15 | False | class_not_vehicle |
| 4 | 1 | other_class | 0.27023786306381226 | [283.72021484375, 147.26315307617188, 567.4854736328125, 422.7099304199219] | 0.15 | False | class_not_vehicle |
| 5 | 1 | other_class | 0.2527827322483063 | [304.11090087890625, 147.92620849609375, 569.000244140625, 413.681396484375] | 0.15 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608897.5437894,
      false
    ],
    [
      1790608898.5974584,
      false
    ],
    [
      1790608899.2355611,
      false
    ],
    [
      1790608900.0478287,
      false
    ],
    [
      1790608901.377112,
      false
    ],
    [
      1790608902.3645573,
      false
    ]
  ],
  "window_after": [
    [
      1790608899.2355611,
      false
    ],
    [
      1790608900.0478287,
      false
    ],
    [
      1790608901.377112,
      false
    ],
    [
      1790608902.3645573,
      false
    ],
    [
      1790608903.6835036,
      false
    ]
  ],
  "window_evaluated_at": 1790608903.6835036,
  "temporal_window_seconds": 5.0,
  "expired_observations": 2,
  "frame_receive_time": 1790608902.335755,
  "inference_start": 1790608902.3687334,
  "inference_end": 1790608903.6835036,
  "decision_time": 1790608903.6835036
}
```

### OBS 5157 ? 2026-09-28T23:21:44.610101

Quality: good; scene valid: True; classifier: 0.728289783000946 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.9067829251289368 | [4.82611083984375, 7.48382568359375, 975.9495849609375, 710.85595703125] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608899.2355611,
      false
    ],
    [
      1790608900.0478287,
      false
    ],
    [
      1790608901.377112,
      false
    ],
    [
      1790608902.3645573,
      false
    ],
    [
      1790608903.6835036,
      false
    ]
  ],
  "window_after": [
    [
      1790608900.0478287,
      false
    ],
    [
      1790608901.377112,
      false
    ],
    [
      1790608902.3645573,
      false
    ],
    [
      1790608903.6835036,
      false
    ],
    [
      1790608904.610102,
      false
    ]
  ],
  "window_evaluated_at": 1790608904.610102,
  "temporal_window_seconds": 5.0,
  "expired_observations": 1,
  "frame_receive_time": 1790608903.6514652,
  "inference_start": 1790608903.6919513,
  "inference_end": 1790608904.610102,
  "decision_time": 1790608904.610102
}
```

### OBS 5171 ? 2026-09-28T23:21:45.557650

Quality: good; scene valid: True; classifier: 0.31975656747817993 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.63425612449646 | [0.0, 11.31597900390625, 957.2344970703125, 710.3560180664062] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608900.0478287,
      false
    ],
    [
      1790608901.377112,
      false
    ],
    [
      1790608902.3645573,
      false
    ],
    [
      1790608903.6835036,
      false
    ],
    [
      1790608904.610102,
      false
    ]
  ],
  "window_after": [
    [
      1790608901.377112,
      false
    ],
    [
      1790608902.3645573,
      false
    ],
    [
      1790608903.6835036,
      false
    ],
    [
      1790608904.610102,
      false
    ],
    [
      1790608905.55765,
      false
    ]
  ],
  "window_evaluated_at": 1790608905.55765,
  "temporal_window_seconds": 5.0,
  "expired_observations": 1,
  "frame_receive_time": 1790608904.589407,
  "inference_start": 1790608904.6186485,
  "inference_end": 1790608905.55765,
  "decision_time": 1790608905.55765
}
```

### OBS 5184 ? 2026-09-28T23:21:46.509013

Quality: good; scene valid: True; classifier: 0.5230523943901062 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.8417906761169434 | [51.02978515625, 7.3807373046875, 995.2216796875, 705.137939453125] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608901.377112,
      false
    ],
    [
      1790608902.3645573,
      false
    ],
    [
      1790608903.6835036,
      false
    ],
    [
      1790608904.610102,
      false
    ],
    [
      1790608905.55765,
      false
    ]
  ],
  "window_after": [
    [
      1790608902.3645573,
      false
    ],
    [
      1790608903.6835036,
      false
    ],
    [
      1790608904.610102,
      false
    ],
    [
      1790608905.55765,
      false
    ],
    [
      1790608906.5090137,
      false
    ]
  ],
  "window_evaluated_at": 1790608906.5090137,
  "temporal_window_seconds": 5.0,
  "expired_observations": 1,
  "frame_receive_time": 1790608905.4974375,
  "inference_start": 1790608905.5596652,
  "inference_end": 1790608906.5090137,
  "decision_time": 1790608906.5131464
}
```

### OBS 5199 ? 2026-09-28T23:21:47.737444

Quality: good; scene valid: True; classifier: 0.5376318097114563 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.8827868700027466 | [135.7938232421875, 6.3590087890625, 1026.2581787109375, 711.8077392578125] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608902.3645573,
      false
    ],
    [
      1790608903.6835036,
      false
    ],
    [
      1790608904.610102,
      false
    ],
    [
      1790608905.55765,
      false
    ],
    [
      1790608906.5090137,
      false
    ]
  ],
  "window_after": [
    [
      1790608903.6835036,
      false
    ],
    [
      1790608904.610102,
      false
    ],
    [
      1790608905.55765,
      false
    ],
    [
      1790608906.5090137,
      false
    ],
    [
      1790608907.7374446,
      false
    ]
  ],
  "window_evaluated_at": 1790608907.7374446,
  "temporal_window_seconds": 5.0,
  "expired_observations": 1,
  "frame_receive_time": 1790608906.4874752,
  "inference_start": 1790608906.517035,
  "inference_end": 1790608907.7299318,
  "decision_time": 1790608907.7374446
}
```

### OBS 5217 ? 2026-09-28T23:21:49.507377

Quality: good; scene valid: True; classifier: 0.6006031632423401 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.7524936199188232 | [179.10400390625, 3.336181640625, 1016.8419189453125, 707.3999633789062] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608903.6835036,
      false
    ],
    [
      1790608904.610102,
      false
    ],
    [
      1790608905.55765,
      false
    ],
    [
      1790608906.5090137,
      false
    ],
    [
      1790608907.7374446,
      false
    ]
  ],
  "window_after": [
    [
      1790608904.610102,
      false
    ],
    [
      1790608905.55765,
      false
    ],
    [
      1790608906.5090137,
      false
    ],
    [
      1790608907.7374446,
      false
    ],
    [
      1790608909.5073776,
      false
    ]
  ],
  "window_evaluated_at": 1790608909.5073776,
  "temporal_window_seconds": 5.0,
  "expired_observations": 1,
  "frame_receive_time": 1790608907.7058578,
  "inference_start": 1790608907.738121,
  "inference_end": 1790608909.5073776,
  "decision_time": 1790608909.5073776
}
```

### OBS 5244 ? 2026-09-28T23:21:50.928833

Quality: good; scene valid: True; classifier: 0.4887935221195221 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.9116052389144897 | [0.0963134765625, 4.79833984375, 1041.5794677734375, 710.0037841796875] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608904.610102,
      false
    ],
    [
      1790608905.55765,
      false
    ],
    [
      1790608906.5090137,
      false
    ],
    [
      1790608907.7374446,
      false
    ],
    [
      1790608909.5073776,
      false
    ]
  ],
  "window_after": [
    [
      1790608906.5090137,
      false
    ],
    [
      1790608907.7374446,
      false
    ],
    [
      1790608909.5073776,
      false
    ],
    [
      1790608910.9288337,
      false
    ]
  ],
  "window_evaluated_at": 1790608910.9288337,
  "temporal_window_seconds": 5.0,
  "expired_observations": 2,
  "frame_receive_time": 1790608909.497597,
  "inference_start": 1790608909.5112972,
  "inference_end": 1790608910.9288337,
  "decision_time": 1790608910.9288337
}
```

### OBS 5265 ? 2026-09-28T23:21:53.897166

Quality: good; scene valid: True; classifier: 0.6789574027061462 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.8747829794883728 | [0.0, 5.14013671875, 1012.932373046875, 661.1859130859375] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608906.5090137,
      false
    ],
    [
      1790608907.7374446,
      false
    ],
    [
      1790608909.5073776,
      false
    ],
    [
      1790608910.9288337,
      false
    ]
  ],
  "window_after": [
    [
      1790608909.5073776,
      false
    ],
    [
      1790608910.9288337,
      false
    ],
    [
      1790608913.8971663,
      false
    ]
  ],
  "window_evaluated_at": 1790608913.8971663,
  "temporal_window_seconds": 5.0,
  "expired_observations": 2,
  "frame_receive_time": 1790608910.887531,
  "inference_start": 1790608910.9288337,
  "inference_end": 1790608913.8971663,
  "decision_time": 1790608913.8971663
}
```

### OBS 5309 ? 2026-09-28T23:21:55.692800

Quality: good; scene valid: True; classifier: 0.7724577188491821 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.8902192115783691 | [15.425079345703125, 3.86981201171875, 1026.19970703125, 708.37255859375] | 0.4 | False | class_not_vehicle |
| 1 | 0 | other_class | 0.4075847566127777 | [999.5789794921875, 501.197998046875, 1185.2315673828125, 714.780517578125] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608909.5073776,
      false
    ],
    [
      1790608910.9288337,
      false
    ],
    [
      1790608913.8971663,
      false
    ]
  ],
  "window_after": [
    [
      1790608910.9288337,
      false
    ],
    [
      1790608913.8971663,
      false
    ],
    [
      1790608915.6928,
      false
    ]
  ],
  "window_evaluated_at": 1790608915.6928,
  "temporal_window_seconds": 5.0,
  "expired_observations": 1,
  "frame_receive_time": 1790608913.8875544,
  "inference_start": 1790608913.9082694,
  "inference_end": 1790608915.6928,
  "decision_time": 1790608915.6928
}
```

### OBS 5336 ? 2026-09-28T23:21:57.130834

Quality: good; scene valid: True; classifier: 0.8055778741836548 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.9172884225845337 | [3.75628662109375, 4.93218994140625, 1019.642578125, 702.7557373046875] | 0.4 | False | class_not_vehicle |
| 1 | 1 | person | 0.9172884225845337 | [3.75628662109375, 4.93218994140625, 1019.642578125, 702.7557373046875] | 0.15 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608910.9288337,
      false
    ],
    [
      1790608913.8971663,
      false
    ],
    [
      1790608915.6928,
      false
    ]
  ],
  "window_after": [
    [
      1790608913.8971663,
      false
    ],
    [
      1790608915.6928,
      false
    ],
    [
      1790608917.130834,
      false
    ]
  ],
  "window_evaluated_at": 1790608917.130834,
  "temporal_window_seconds": 5.0,
  "expired_observations": 1,
  "frame_receive_time": 1790608915.6928,
  "inference_start": 1790608915.6974177,
  "inference_end": 1790608917.130834,
  "decision_time": 1790608917.130834
}
```

### OBS 5357 ? 2026-09-28T23:21:58.027143

Quality: good; scene valid: True; classifier: 0.5142751932144165 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.9096742272377014 | [3.31817626953125, 5.43408203125, 1017.898681640625, 708.994873046875] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608913.8971663,
      false
    ],
    [
      1790608915.6928,
      false
    ],
    [
      1790608917.130834,
      false
    ]
  ],
  "window_after": [
    [
      1790608913.8971663,
      false
    ],
    [
      1790608915.6928,
      false
    ],
    [
      1790608917.130834,
      false
    ],
    [
      1790608918.027144,
      false
    ]
  ],
  "window_evaluated_at": 1790608918.027144,
  "temporal_window_seconds": 5.0,
  "expired_observations": 0,
  "frame_receive_time": 1790608917.087594,
  "inference_start": 1790608917.130834,
  "inference_end": 1790608918.027144,
  "decision_time": 1790608918.027144
}
```

### OBS 5370 ? 2026-09-28T23:21:58.950951

Quality: good; scene valid: True; classifier: 0.7805809378623962 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.9108990430831909 | [1.319091796875, 4.74774169921875, 1022.1707153320312, 708.89697265625] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608913.8971663,
      false
    ],
    [
      1790608915.6928,
      false
    ],
    [
      1790608917.130834,
      false
    ],
    [
      1790608918.027144,
      false
    ]
  ],
  "window_after": [
    [
      1790608915.6928,
      false
    ],
    [
      1790608917.130834,
      false
    ],
    [
      1790608918.027144,
      false
    ],
    [
      1790608918.9509513,
      false
    ]
  ],
  "window_evaluated_at": 1790608918.9509513,
  "temporal_window_seconds": 5.0,
  "expired_observations": 1,
  "frame_receive_time": 1790608917.9776733,
  "inference_start": 1790608918.027144,
  "inference_end": 1790608918.9509513,
  "decision_time": 1790608918.9509513
}
```

### OBS 5384 ? 2026-09-28T23:22:01.557323

Quality: good; scene valid: True; classifier: 0.5964586734771729 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.865781843662262 | [0.0, 4.5936279296875, 1029.330322265625, 708.4818115234375] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608915.6928,
      false
    ],
    [
      1790608917.130834,
      false
    ],
    [
      1790608918.027144,
      false
    ],
    [
      1790608918.9509513,
      false
    ]
  ],
  "window_after": [
    [
      1790608917.130834,
      false
    ],
    [
      1790608918.027144,
      false
    ],
    [
      1790608918.9509513,
      false
    ],
    [
      1790608921.557323,
      false
    ]
  ],
  "window_evaluated_at": 1790608921.557323,
  "temporal_window_seconds": 5.0,
  "expired_observations": 1,
  "frame_receive_time": 1790608918.8876576,
  "inference_start": 1790608918.9509513,
  "inference_end": 1790608921.5526948,
  "decision_time": 1790608921.557323
}
```

### OBS 5423 ? 2026-09-28T23:22:04.933989

Quality: good; scene valid: True; classifier: 0.4007154703140259 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.9165019989013672 | [0.6416015625, 3.19464111328125, 1034.054931640625, 713.8848266601562] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608917.130834,
      false
    ],
    [
      1790608918.027144,
      false
    ],
    [
      1790608918.9509513,
      false
    ],
    [
      1790608921.557323,
      false
    ]
  ],
  "window_after": [
    [
      1790608921.557323,
      false
    ],
    [
      1790608924.93399,
      false
    ]
  ],
  "window_evaluated_at": 1790608924.93399,
  "temporal_window_seconds": 5.0,
  "expired_observations": 3,
  "frame_receive_time": 1790608921.5374477,
  "inference_start": 1790608921.567567,
  "inference_end": 1790608924.93399,
  "decision_time": 1790608924.93399
}
```

### OBS 5472 ? 2026-09-28T23:22:05.539026

Quality: good; scene valid: True; classifier: 0.7221269607543945 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.9215599298477173 | [9.33428955078125, 8.0482177734375, 1019.8660278320312, 705.831298828125] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608921.557323,
      false
    ],
    [
      1790608924.93399,
      false
    ]
  ],
  "window_after": [
    [
      1790608921.557323,
      false
    ],
    [
      1790608924.93399,
      false
    ],
    [
      1790608925.5390267,
      false
    ]
  ],
  "window_evaluated_at": 1790608925.5390267,
  "temporal_window_seconds": 5.0,
  "expired_observations": 0,
  "frame_receive_time": 1790608924.8878531,
  "inference_start": 1790608924.9370198,
  "inference_end": 1790608925.5390267,
  "decision_time": 1790608925.5390267
}
```

### OBS 5481 ? 2026-09-28T23:22:07.875451

Quality: good; scene valid: True; classifier: 0.8289238214492798 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.8820222020149231 | [8.9652099609375, 10.37457275390625, 1028.2197265625, 709.4603881835938] | 0.4 | False | class_not_vehicle |
| 1 | 0 | other_class | 0.2983475923538208 | [1229.013916015625, 541.14453125, 1279.656005859375, 717.5859375] | 0.4 | False | class_not_vehicle |
| 2 | 1 | person | 0.8820222020149231 | [8.9652099609375, 10.37457275390625, 1028.2197265625, 709.4603881835938] | 0.15 | False | class_not_vehicle |
| 3 | 1 | other_class | 0.2983475923538208 | [1229.013916015625, 541.14453125, 1279.656005859375, 717.5859375] | 0.15 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608921.557323,
      false
    ],
    [
      1790608924.93399,
      false
    ],
    [
      1790608925.5390267,
      false
    ]
  ],
  "window_after": [
    [
      1790608924.93399,
      false
    ],
    [
      1790608925.5390267,
      false
    ],
    [
      1790608927.875451,
      false
    ]
  ],
  "window_evaluated_at": 1790608927.875451,
  "temporal_window_seconds": 5.0,
  "expired_observations": 1,
  "frame_receive_time": 1790608925.4919603,
  "inference_start": 1790608925.543053,
  "inference_end": 1790608927.875451,
  "decision_time": 1790608927.875451
}
```

### OBS 5516 ? 2026-09-28T23:22:11.677914

Quality: good; scene valid: True; classifier: 0.7307934761047363 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.8716139793395996 | [19.697235107421875, 12.28948974609375, 1029.25537109375, 706.8693237304688] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608924.93399,
      false
    ],
    [
      1790608925.5390267,
      false
    ],
    [
      1790608927.875451,
      false
    ]
  ],
  "window_after": [
    [
      1790608927.875451,
      false
    ],
    [
      1790608931.6814451,
      false
    ]
  ],
  "window_evaluated_at": 1790608931.6814451,
  "temporal_window_seconds": 5.0,
  "expired_observations": 2,
  "frame_receive_time": 1790608927.8357704,
  "inference_start": 1790608927.879553,
  "inference_end": 1790608931.6779149,
  "decision_time": 1790608931.6814451
}
```

### OBS 5573 ? 2026-09-28T23:22:14.807244

Quality: good; scene valid: True; classifier: 0.5956951975822449 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.9236531853675842 | [1.76708984375, 4.1917724609375, 1033.57568359375, 710.4932861328125] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608927.875451,
      false
    ],
    [
      1790608931.6814451,
      false
    ]
  ],
  "window_after": [
    [
      1790608931.6814451,
      false
    ],
    [
      1790608934.8072443,
      false
    ]
  ],
  "window_evaluated_at": 1790608934.8072443,
  "temporal_window_seconds": 5.0,
  "expired_observations": 1,
  "frame_receive_time": 1790608931.6570613,
  "inference_start": 1790608931.6854775,
  "inference_end": 1790608934.8072443,
  "decision_time": 1790608934.8072443
}
```

### OBS 5619 ? 2026-09-28T23:22:17.483208

Quality: good; scene valid: True; classifier: 0.5668437480926514 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.9088969230651855 | [0.0, 11.6014404296875, 1041.886474609375, 708.3438720703125] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608931.6814451,
      false
    ],
    [
      1790608934.8072443,
      false
    ]
  ],
  "window_after": [
    [
      1790608934.8072443,
      false
    ],
    [
      1790608937.483209,
      false
    ]
  ],
  "window_evaluated_at": 1790608937.483209,
  "temporal_window_seconds": 5.0,
  "expired_observations": 1,
  "frame_receive_time": 1790608934.7505617,
  "inference_start": 1790608934.8163836,
  "inference_end": 1790608937.483209,
  "decision_time": 1790608937.483209
}
```

### OBS 5660 ? 2026-09-28T23:22:18.554970

Quality: good; scene valid: True; classifier: 0.742648720741272 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.9233092665672302 | [2.0670166015625, 3.22607421875, 1031.1600341796875, 712.6878662109375] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608934.8072443,
      false
    ],
    [
      1790608937.483209,
      false
    ]
  ],
  "window_after": [
    [
      1790608934.8072443,
      false
    ],
    [
      1790608937.483209,
      false
    ],
    [
      1790608938.5549707,
      false
    ]
  ],
  "window_evaluated_at": 1790608938.5549707,
  "temporal_window_seconds": 5.0,
  "expired_observations": 0,
  "frame_receive_time": 1790608937.457265,
  "inference_start": 1790608937.4873893,
  "inference_end": 1790608938.5549707,
  "decision_time": 1790608938.5549707
}
```

### OBS 5676 ? 2026-09-28T23:22:19.450605

Quality: good; scene valid: True; classifier: 0.29825359582901 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.9040088057518005 | [1.916259765625, 1.57208251953125, 1033.204833984375, 711.1080932617188] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608934.8072443,
      false
    ],
    [
      1790608937.483209,
      false
    ],
    [
      1790608938.5549707,
      false
    ]
  ],
  "window_after": [
    [
      1790608934.8072443,
      false
    ],
    [
      1790608937.483209,
      false
    ],
    [
      1790608938.5549707,
      false
    ],
    [
      1790608939.4506056,
      false
    ]
  ],
  "window_evaluated_at": 1790608939.4506056,
  "temporal_window_seconds": 5.0,
  "expired_observations": 0,
  "frame_receive_time": 1790608938.5422533,
  "inference_start": 1790608938.5591471,
  "inference_end": 1790608939.4506056,
  "decision_time": 1790608939.4506056
}
```

### OBS 5688 ? 2026-09-28T23:22:20.947071

Quality: good; scene valid: True; classifier: 0.6752326488494873 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.9082745909690857 | [0.297607421875, 4.65447998046875, 1038.1357421875, 711.3983764648438] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608934.8072443,
      false
    ],
    [
      1790608937.483209,
      false
    ],
    [
      1790608938.5549707,
      false
    ],
    [
      1790608939.4506056,
      false
    ]
  ],
  "window_after": [
    [
      1790608937.483209,
      false
    ],
    [
      1790608938.5549707,
      false
    ],
    [
      1790608939.4506056,
      false
    ],
    [
      1790608940.9470713,
      false
    ]
  ],
  "window_evaluated_at": 1790608940.9470713,
  "temporal_window_seconds": 5.0,
  "expired_observations": 1,
  "frame_receive_time": 1790608939.3785055,
  "inference_start": 1790608939.4547298,
  "inference_end": 1790608940.9425554,
  "decision_time": 1790608940.9470713
}
```

### OBS 5711 ? 2026-09-28T23:22:23.027282

Quality: good; scene valid: True; classifier: 0.5459827184677124 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.8756508231163025 | [1.895751953125, 5.25372314453125, 1039.423583984375, 714.910888671875] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608937.483209,
      false
    ],
    [
      1790608938.5549707,
      false
    ],
    [
      1790608939.4506056,
      false
    ],
    [
      1790608940.9470713,
      false
    ]
  ],
  "window_after": [
    [
      1790608938.5549707,
      false
    ],
    [
      1790608939.4506056,
      false
    ],
    [
      1790608940.9470713,
      false
    ],
    [
      1790608943.0272825,
      false
    ]
  ],
  "window_evaluated_at": 1790608943.0272825,
  "temporal_window_seconds": 5.0,
  "expired_observations": 1,
  "frame_receive_time": 1790608940.93849,
  "inference_start": 1790608940.9470713,
  "inference_end": 1790608943.0272825,
  "decision_time": 1790608943.0272825
}
```

### OBS 5742 ? 2026-09-28T23:22:24.078271

Quality: good; scene valid: True; classifier: 0.6609065532684326 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.9032601714134216 | [2.15826416015625, 5.20751953125, 1019.4345092773438, 712.9691162109375] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608938.5549707,
      false
    ],
    [
      1790608939.4506056,
      false
    ],
    [
      1790608940.9470713,
      false
    ],
    [
      1790608943.0272825,
      false
    ]
  ],
  "window_after": [
    [
      1790608939.4506056,
      false
    ],
    [
      1790608940.9470713,
      false
    ],
    [
      1790608943.0272825,
      false
    ],
    [
      1790608944.0782714,
      false
    ]
  ],
  "window_evaluated_at": 1790608944.0782714,
  "temporal_window_seconds": 5.0,
  "expired_observations": 1,
  "frame_receive_time": 1790608943.0073445,
  "inference_start": 1790608943.0314083,
  "inference_end": 1790608944.0782714,
  "decision_time": 1790608944.0782714
}
```

### OBS 5757 ? 2026-09-28T23:22:25.190878

Quality: good; scene valid: True; classifier: 0.7081369161605835 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.9198920726776123 | [0.0, 4.9781494140625, 1034.7877197265625, 711.02490234375] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608939.4506056,
      false
    ],
    [
      1790608940.9470713,
      false
    ],
    [
      1790608943.0272825,
      false
    ],
    [
      1790608944.0782714,
      false
    ]
  ],
  "window_after": [
    [
      1790608940.9470713,
      false
    ],
    [
      1790608943.0272825,
      false
    ],
    [
      1790608944.0782714,
      false
    ],
    [
      1790608945.1908782,
      false
    ]
  ],
  "window_evaluated_at": 1790608945.1908782,
  "temporal_window_seconds": 5.0,
  "expired_observations": 1,
  "frame_receive_time": 1790608944.0171037,
  "inference_start": 1790608944.082281,
  "inference_end": 1790608945.1908782,
  "decision_time": 1790608945.1908782
}
```

### OBS 5774 ? 2026-09-28T23:22:26.531268

Quality: good; scene valid: True; classifier: 0.7146630883216858 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.8965149521827698 | [3.9158935546875, 5.00067138671875, 1032.2608642578125, 713.2838745117188] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608940.9470713,
      false
    ],
    [
      1790608943.0272825,
      false
    ],
    [
      1790608944.0782714,
      false
    ],
    [
      1790608945.1908782,
      false
    ]
  ],
  "window_after": [
    [
      1790608943.0272825,
      false
    ],
    [
      1790608944.0782714,
      false
    ],
    [
      1790608945.1908782,
      false
    ],
    [
      1790608946.5312681,
      false
    ]
  ],
  "window_evaluated_at": 1790608946.5312681,
  "temporal_window_seconds": 5.0,
  "expired_observations": 1,
  "frame_receive_time": 1790608945.1744223,
  "inference_start": 1790608945.1974626,
  "inference_end": 1790608946.5312681,
  "decision_time": 1790608946.5312681
}
```

### OBS 5794 ? 2026-09-28T23:22:27.607283

Quality: good; scene valid: True; classifier: 0.5960890650749207 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.8970015645027161 | [6.89605712890625, 3.9580078125, 1022.9569702148438, 707.327880859375] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608943.0272825,
      false
    ],
    [
      1790608944.0782714,
      false
    ],
    [
      1790608945.1908782,
      false
    ],
    [
      1790608946.5312681,
      false
    ]
  ],
  "window_after": [
    [
      1790608943.0272825,
      false
    ],
    [
      1790608944.0782714,
      false
    ],
    [
      1790608945.1908782,
      false
    ],
    [
      1790608946.5312681,
      false
    ],
    [
      1790608947.6072834,
      false
    ]
  ],
  "window_evaluated_at": 1790608947.6072834,
  "temporal_window_seconds": 5.0,
  "expired_observations": 0,
  "frame_receive_time": 1790608946.5312681,
  "inference_start": 1790608946.5372896,
  "inference_end": 1790608947.6072834,
  "decision_time": 1790608947.6072834
}
```

### OBS 5810 ? 2026-09-28T23:22:29.267177

Quality: good; scene valid: True; classifier: 0.4652746617794037 / case threshold 0.9 (FAIL); production rejection: person_only_not_crash.

| Proposal | Pass | Class | Confidence | Raw bbox xyxy | Threshold | Accepted | Rejection |
|---|---|---|---|---|---|---|---|
| 0 | 0 | person | 0.8915365934371948 | [1.057464599609375, 6.15826416015625, 1024.8565673828125, 709.2783813476562] | 0.4 | False | class_not_vehicle |

Accepted vehicles (exact production list, bbox xywh):
```json
[]
```
Evaluated pairs (IoU ? required IoU OR normalized edge distance ? maximum; classification UNDETERMINED for every pair):
```json
[]
```
Temporal window evidence:
```json
{
  "window_before": [
    [
      1790608943.0272825,
      false
    ],
    [
      1790608944.0782714,
      false
    ],
    [
      1790608945.1908782,
      false
    ],
    [
      1790608946.5312681,
      false
    ],
    [
      1790608947.6072834,
      false
    ]
  ],
  "window_after": [
    [
      1790608945.1908782,
      false
    ],
    [
      1790608946.5312681,
      false
    ],
    [
      1790608947.6072834,
      false
    ],
    [
      1790608949.2671778,
      false
    ]
  ],
  "window_evaluated_at": 1790608949.2671778,
  "temporal_window_seconds": 5.0,
  "expired_observations": 2,
  "frame_receive_time": 1790608947.5773175,
  "inference_start": 1790608947.6113024,
  "inference_end": 1790608949.2671778,
  "decision_time": 1790608949.2671778
}
```
