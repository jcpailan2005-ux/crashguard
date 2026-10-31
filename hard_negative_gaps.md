# Hard Negative & Edge-Case Deficiencies Audit

## Executive Summary
A reliable crash classification model deployed in physical CCTV environments must avoid false alarms triggered by normal but visually complex traffic situations. In CrashGuard, the binary classifier categorizes frames into `accident` (0) vs `non_accident` (1). 

During our comprehensive audit of the 13,301 images across 583 independent physical events, we evaluated the negative class (`non_accident`) against 24 operational road scenarios. We identified a critical **Hard Negative Deficiency**: while normal moving highway and street traffic is abundantly represented, the dataset severely lacks negative examples of stationary vehicles, dense congestion, roadside operations, and perspective overlaps.

---

## 1. Quantitative Coverage of Hard Negative Scenarios

| Scenario / Hard Negative Category | Present in Dataset? | Estimated Event Count | Current Model Vulnerability | Operational Risk in CCTV |
| :--- | :---: | :---: | :---: | :--- |
| **Normal Free-Flow Traffic** | **YES** | ~230 events | None (well classified, scores < 0.05) | Low |
| **Empty Roads / Intersections** | **YES** | ~45 events | None (well classified, scores < 0.01) | Low |
| **Traffic Jams / Dense Queues** | **PARTIAL** | ~12 events | Moderate (scores 0.25 - 0.55) | High (junction queues flag false alarms) |
| **Vehicles Stopped at Red Light** | **PARTIAL** | ~10 events | Moderate (tight vehicle spacing triggers false positives) | High (frequent alarms at signals) |
| **Diagonal / Curbside Parking** | **NO** | 2 events | **High (Sample `4751` scored 0.8588 crash)** | Critical (urban streets with curbside parking) |
| **Roadside Vehicle Breakdown** | **NO** | 0 events | High (stationary vehicle with hazard lights) | High |
| **Tow Trucks / Flatbed Operations** | **NO** | 0 events | High (looks like vehicle piggyback/collision) | Critical (false alert during active towing) |
| **Construction / Cones / Barriers** | **NO** | 1 event | Moderate (orange cones and barriers) | Moderate |
| **Emergency Vehicles (Police/Ambulance)** | **NO** | 0 events | High (flashing lights, unusual vehicle positions) | High |
| **Perspective Occlusion (Van overtaking Bus)** | **PARTIAL** | ~8 events | **High (Sample `14606` scored 0.9401 crash)** | Critical (high-angle CCTV creates visual overlap) |
| **Heavy Night Headlight Glare** | **PARTIAL** | ~15 events | **High (Sample `13052` scored 0.8609 crash)** | High (lens flare on wet asphalt mimics crash smoke) |
| **Motorcycles Filtering between Cars** | **NO** | 2 events | High (close spatial proximity) | Critical for Metro Manila traffic ("lane splitting") |
| **Wet Road Mirror Reflections** | **NO** | 3 events | Moderate (diffuse highlights confuse bounding cues) | High during rain storms |

---

## 2. Qualitative False Positive Analysis
In our clean, leakage-free evaluation of 43 unseen negative events (643 frames), the classifier produced **20 false positive frames** across **5 distinct events** (event-level specificity = 88.37%):

1. **Perspective Vehicle Overlap (`c2_non_accident_ev_0096` - Max Crash Score: 0.9643)**:
   - A large truck/van passed in front of a bus along a dual-lane road. From the elevated CCTV vantage point, the bounding boxes overlapped by >75%, creating an appearance of side-impact deformation.
2. **Night Headlight Flare & Low Resolution (`c2_non_accident_ev_0077` - Max Crash Score: 0.9824)**:
   - Extreme headlight bloom combined with 320x240 JPEG macroblocking wiped out vehicle outlines, causing the model to mistake diffuse glare for an explosive collision.
3. **Curbside Diagonal Parking (`c2_non_accident_ev_0158` - Max Crash Score: 0.8588)**:
   - Several cars parked perpendicularly along a wide shoulder resembled vehicles stopped post-collision.
4. **Close Bumper-to-Bumper Junction Traffic (`c1_test22_non_accident` - Max Crash Score: 0.8731)**:
   - Two black sedans stopped within inches of each other waiting for a left turn triggered a high-confidence false detection.

---

## 3. Post-Crash Aftermath Representation
The second major gap identified in the positive class is **Stationary Post-Impact Aftermath**:
- **Current Positive Bias**: Over 86% of crash frames in `accident` capture the dynamic moment of impact (dust, glass, flying debris, rapid angular rotation).
- **Aftermath Scarcity**: Only ~14% of frames depict stationary vehicles after impact. Furthermore, these are dominated by dramatic rollovers (overturned cars).
- **Upright Damaged Vehicles**: Collisions where vehicles remain upright and come to a stop with crumpled bumpers or crushed hoods are severely underrepresented.
- **Operational Impact**: When an RTSP camera stream begins recording seconds after an accident has occurred, or when downstream temporal motion slows to zero, a classifier trained only on dynamic impact debris will drop confidence, preventing the Aftermath Path from triggering.

---

## 4. Remediation Priorities for Hard Negatives
To prepare CrashGuard for physical CCTV camera deployment, the following targeted data collection must occur:

1. **Urban Intersection Queues (Philippines / Metro Manila Context)**:
   - High-density stop-and-go traffic, jeepneys stopped at curbs, tricycles and motorcycles filtering between stopped cars.
2. **Roadside Shoulder Activities**:
   - Legitimate parking, tire changes, roadside vendor carts, unloading delivery vans.
3. **Weather & Lighting Hard Negatives**:
   - Heavy rain with windshield wipers, night streets with high sodium-vapor streetlights and asphalt reflections.
4. **Emergency & Service Vehicles**:
   - Tow trucks towing cars, ambulances with flashing beacons, road sweepers.
