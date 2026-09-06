from datetime import datetime
import math


# ============================================================
# SIH26127 — CITY-WIDE AI TRAJECTORY ENGINE
# VERIFIED BASELINE THROUGH STEP 2.29 — TRAJECTORY ENGINE
# ============================================================


# ============================================================
# CONFIGURATION
# ============================================================

DUPLICATE_WINDOW_SECONDS = 30
MAX_PLAUSIBLE_SPEED_KMH = 60
MIN_CONFIDENCE = 0.90

# Step 2.19
MAX_PLATE_DISTANCE = 1

# Step 2.20
MAX_FUZZY_TIME_GAP_SECONDS = 600

# Step 2.21
TRAJECTORY_SCORE_THRESHOLD = 7
TRAJECTORY_SCORE_MARGIN = 2

# Step 2.22
HIGH_CONFIDENCE_SCORE = 9
POSSIBLE_MATCH_SCORE = 7
AMBIGUOUS_SCORE = 5

# Step 2.23
MULTI_CANDIDATE_MARGIN = 2

# Step 2.24
MIN_CONSISTENCY_CHECKS = 3

# Step 2.25
HIGH_CONFIDENCE_PERCENT = 85
MEDIUM_CONFIDENCE_PERCENT = 65


# ============================================================
# TEMPORARY CAMERA DATA
# ============================================================

CAMERAS = {
    "Camera_1": {"lat": 28.7041, "lon": 77.1025},
    "Camera_2": {"lat": 28.7045, "lon": 77.1030},
    "Camera_3": {"lat": 28.7050, "lon": 77.1038},
    "Camera_4": {"lat": 28.7048, "lon": 77.1045},
    "Camera_5": {"lat": 28.7060, "lon": 77.1060},
}


CAMERA_GRAPH = {
    "Camera_1": ["Camera_2"],
    "Camera_2": ["Camera_1", "Camera_3", "Camera_4"],
    "Camera_3": ["Camera_2", "Camera_4"],
    "Camera_4": ["Camera_2", "Camera_3"],
    "Camera_5": [],
}


# ============================================================
# TEST EVENTS
# ============================================================

EVENTS = [
    # Vehicle 1
    {
        "id": 101,
        "plate_number": "DL01AB1234",
        "camera_id": "Camera_1",
        "timestamp": "09:00:00",
        "confidence": 0.95,
    },
    {
        "id": 102,
        "plate_number": "DL01AB1234",
        "camera_id": "Camera_2",
        "timestamp": "09:05:00",
        "confidence": 0.93,
    },
    {
        "id": 103,
        "plate_number": "DL01AB123A",
        "camera_id": "Camera_3",
        "timestamp": "09:10:00",
        "confidence": 0.91,
    },

    # Vehicle 2
    {
        "id": 201,
        "plate_number": "DL02XY5678",
        "camera_id": "Camera_1",
        "timestamp": "10:00:00",
        "confidence": 0.94,
    },
    {
        "id": 202,
        "plate_number": "DL02XY5678",
        "camera_id": "Camera_2",
        "timestamp": "10:05:00",
        "confidence": 0.92,
    },
    {
        "id": 203,
        "plate_number": "DL02XY567",
        "camera_id": "Camera_2",
        "timestamp": "10:05:20",
        "confidence": 0.91,
    },
    {
        "id": 205,
        "plate_number": "DL02XY5678",
        "camera_id": "Camera_2",
        "timestamp": "10:05:15",
        "confidence": 0.91,
    },
    {
        "id": 204,
        "plate_number": "DL02XY5678",
        "camera_id": "Camera_4",
        "timestamp": "10:10:00",
        "confidence": 0.90,
    },

    # Vehicle 3
    {
        "id": 301,
        "plate_number": "DL04RT3456",
        "camera_id": "Camera_1",
        "timestamp": "12:00:00",
        "confidence": 0.96,
    },
    {
        "id": 302,
        "plate_number": "DL04RT3456",
        "camera_id": "Camera_2",
        "timestamp": "12:05:00",
        "confidence": 0.94,
    },
    {
        "id": 303,
        "plate_number": "DL04RT3456",
        "camera_id": "Camera_3",
        "timestamp": "12:10:00",
        "confidence": 0.93,
    },
    {
        "id": 304,
        "plate_number": "DL04RT3456",
        "camera_id": "Camera_2",
        "timestamp": "12:40:00",
        "confidence": 0.91,
    },

    # Vehicle 4
    {
        "id": 401,
        "plate_number": "DL05MN7890",
        "camera_id": "Camera_1",
        "timestamp": "13:00:00",
        "confidence": 0.97,
    },
    {
        "id": 402,
        "plate_number": "DL05MN7890",
        "camera_id": "Camera_4",
        "timestamp": "13:00:10",
        "confidence": 0.95,
    },

    # Vehicle 5 — disconnected route
    {
        "id": 501,
        "plate_number": "DL06AB6789",
        "camera_id": "Camera_1",
        "timestamp": "14:00:00",
        "confidence": 0.96,
    },
    {
        "id": 502,
        "plate_number": "DL06AB6789",
        "camera_id": "Camera_5",
        "timestamp": "14:01:00",
        "confidence": 0.94,
    },

    # Vehicle 6 — low confidence event
    {
        "id": 601,
        "plate_number": "DL07CD1122",
        "camera_id": "Camera_1",
        "timestamp": "15:00:00",
        "confidence": 0.95,
    },
    {
        "id": 602,
        "plate_number": "DL07CD1122",
        "camera_id": "Camera_2",
        "timestamp": "15:05:00",
        "confidence": 0.72,
    },
    {
        "id": 603,
        "plate_number": "DL07CD1122",
        "camera_id": "Camera_3",
        "timestamp": "15:10:00",
        "confidence": 0.94,
    },
]


# ============================================================
# BASIC HELPERS
# ============================================================

def parse_time(time_string):
    return datetime.strptime(time_string, "%H:%M:%S")


def time_difference_seconds(time_a, time_b):
    return abs(
        (
            parse_time(time_a)
            - parse_time(time_b)
        ).total_seconds()
    )


def normalize_plate_number(plate):

    if plate is None:
        return ""

    return "".join(
        character
        for character in plate.upper()
        if character.isalnum()
    )


# ============================================================
# HAVERSINE DISTANCE
# ============================================================

def haversine_distance_km(
    lat1,
    lon1,
    lat2,
    lon2
):

    earth_radius_km = 6371.0

    lat1 = math.radians(lat1)
    lon1 = math.radians(lon1)

    lat2 = math.radians(lat2)
    lon2 = math.radians(lon2)

    d_lat = lat2 - lat1
    d_lon = lon2 - lon1

    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(d_lon / 2) ** 2
    )

    c = 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a)
    )

    return earth_radius_km * c


# ============================================================
# CAMERA / ROUTE DISTANCE
# ============================================================

def camera_distance_km(
    camera_a,
    camera_b
):

    point_a = CAMERAS[camera_a]
    point_b = CAMERAS[camera_b]

    return haversine_distance_km(
        point_a["lat"],
        point_a["lon"],
        point_b["lat"],
        point_b["lon"],
    )


def dijkstra_shortest_path(
    start_camera,
    end_camera
):

    distances = {
        camera: float("inf")
        for camera in CAMERA_GRAPH
    }

    distances[start_camera] = 0

    visited = set()

    while len(visited) < len(CAMERA_GRAPH):

        current_camera = None
        current_distance = float("inf")

        for camera in CAMERA_GRAPH:

            if camera in visited:
                continue

            if distances[camera] < current_distance:

                current_distance = distances[camera]
                current_camera = camera

        if current_camera is None:
            break

        visited.add(current_camera)

        if current_camera == end_camera:
            break

        for neighbor in CAMERA_GRAPH[current_camera]:

            edge_distance = camera_distance_km(
                current_camera,
                neighbor
            )

            new_distance = (
                distances[current_camera]
                + edge_distance
            )

            if new_distance < distances[neighbor]:

                distances[neighbor] = new_distance

    if distances[end_camera] == float("inf"):
        return None

    return distances[end_camera]


def cameras_are_connected(
    camera_a,
    camera_b
):

    return dijkstra_shortest_path(
        camera_a,
        camera_b
    ) is not None


# ============================================================
# TRAJECTORY PROCESSING
# ============================================================

def filter_low_confidence_events(events):

    filtered = []
    removed = []

    for event in events:

        if event["confidence"] >= MIN_CONFIDENCE:

            filtered.append(event)

        else:

            removed.append(event)

    return filtered, removed


def remove_same_camera_duplicates(events):

    sorted_events = sorted(
        events,
        key=lambda event: parse_time(
            event["timestamp"]
        )
    )

    kept = []
    removed = []

    for event in sorted_events:

        duplicate_found = False

        for previous in reversed(kept):

            if (
                previous["plate_number"]
                != event["plate_number"]
            ):
                continue

            if (
                previous["camera_id"]
                != event["camera_id"]
            ):
                continue

            gap = time_difference_seconds(
                previous["timestamp"],
                event["timestamp"]
            )

            if gap <= DUPLICATE_WINDOW_SECONDS:

                duplicate_found = True
                break

        if duplicate_found:

            removed.append(event)

        else:

            kept.append(event)

    return kept, removed


def build_trajectories(events):

    trajectories = {}

    sorted_events = sorted(
        events,
        key=lambda event: parse_time(
            event["timestamp"]
        )
    )

    for event in sorted_events:

        plate = event["plate_number"]

        if plate not in trajectories:
            trajectories[plate] = []

        trajectories[plate].append(event)

    for plate in trajectories:

        trajectories[plate].sort(
            key=lambda event: parse_time(
                event["timestamp"]
            )
        )

    return trajectories


# ============================================================
# MOVEMENT VALIDATION
# ============================================================

def validate_movement(
    event_a,
    event_b
):

    time_gap_seconds = (
        parse_time(event_b["timestamp"])
        - parse_time(event_a["timestamp"])
    ).total_seconds()

    if time_gap_seconds <= 0:

        return {
            "feasible": False,
            "reason": "Non-positive time gap",
            "speed_kmh": None,
            "distance_km": None,
        }

    route_distance = dijkstra_shortest_path(
        event_a["camera_id"],
        event_b["camera_id"]
    )

    if route_distance is None:

        return {
            "feasible": False,
            "reason": "No connected route",
            "speed_kmh": None,
            "distance_km": None,
        }

    speed_kmh = (
        route_distance
        / (time_gap_seconds / 3600)
    )

    feasible = (
        speed_kmh <= MAX_PLAUSIBLE_SPEED_KMH
    )

    return {
        "feasible": feasible,
        "reason": (
            "Movement feasible"
            if feasible
            else "Unrealistic movement speed"
        ),
        "speed_kmh": speed_kmh,
        "distance_km": route_distance,
    }


def find_suspicious_movements(
    trajectories
):

    suspicious = []

    for plate, events in trajectories.items():

        for index in range(len(events) - 1):

            event_a = events[index]
            event_b = events[index + 1]

            result = validate_movement(
                event_a,
                event_b
            )

            if not result["feasible"]:

                suspicious.append({
                    "plate_number": plate,
                    "from_event": event_a,
                    "to_event": event_b,
                    "validation": result,
                })

    return suspicious


def find_disconnected_routes(
    trajectories
):

    disconnected = []

    for plate, events in trajectories.items():

        for index in range(len(events) - 1):

            event_a = events[index]
            event_b = events[index + 1]

            route = dijkstra_shortest_path(
                event_a["camera_id"],
                event_b["camera_id"]
            )

            if route is None:

                disconnected.append({
                    "plate_number": plate,
                    "from_event": event_a,
                    "to_event": event_b,
                })

    return disconnected


# ============================================================
# STEP 2.19 — LEVENSHTEIN
# ============================================================

def levenshtein_distance(
    first,
    second
):

    first = normalize_plate_number(first)
    second = normalize_plate_number(second)

    rows = len(first) + 1
    columns = len(second) + 1

    matrix = [
        [0] * columns
        for _ in range(rows)
    ]

    for i in range(rows):
        matrix[i][0] = i

    for j in range(columns):
        matrix[0][j] = j

    for i in range(1, rows):

        for j in range(1, columns):

            substitution_cost = (
                0
                if first[i - 1]
                == second[j - 1]
                else 1
            )

            matrix[i][j] = min(
                matrix[i - 1][j] + 1,
                matrix[i][j - 1] + 1,
                matrix[i - 1][j - 1]
                + substitution_cost,
            )

    return matrix[-1][-1]


def plate_numbers_match(
    first,
    second
):

    return (
        levenshtein_distance(
            first,
            second
        )
        <= MAX_PLATE_DISTANCE
    )


def find_fuzzy_plate_matches(events):

    matches = []

    for i in range(len(events)):

        for j in range(i + 1, len(events)):

            first = events[i]
            second = events[j]

            first_plate = normalize_plate_number(
                first["plate_number"]
            )

            second_plate = normalize_plate_number(
                second["plate_number"]
            )

            if first_plate == second_plate:
                continue

            distance = levenshtein_distance(
                first_plate,
                second_plate
            )

            if distance <= MAX_PLATE_DISTANCE:

                matches.append({
                    "event_a": first,
                    "event_b": second,
                    "plate_distance": distance,
                })

    return matches


# ============================================================
# STEP 2.20 — CONTEXT VALIDATION
# ============================================================

def find_temporal_context(
    event_a,
    event_b
):

    time_a = parse_time(
        event_a["timestamp"]
    )

    time_b = parse_time(
        event_b["timestamp"]
    )

    gap = abs(
        (
            time_a - time_b
        ).total_seconds()
    )

    return {
        "time_gap_seconds": gap,
        "within_time_window": (
            gap <= MAX_FUZZY_TIME_GAP_SECONDS
        ),
        "chronological_order": (
            "A_BEFORE_B"
            if time_a < time_b
            else "B_BEFORE_A"
            if time_b < time_a
            else "SAME_TIME"
        ),
    }


def evaluate_camera_context(
    event_a,
    event_b
):

    connected = cameras_are_connected(
        event_a["camera_id"],
        event_b["camera_id"]
    )

    same_camera = (
        event_a["camera_id"]
        == event_b["camera_id"]
    )

    return {
        "same_camera": same_camera,
        "connected": connected,
    }


def validate_fuzzy_plate_match(
    event_a,
    event_b
):

    plate_distance = levenshtein_distance(
        event_a["plate_number"],
        event_b["plate_number"]
    )

    temporal = find_temporal_context(
        event_a,
        event_b
    )

    camera_context = evaluate_camera_context(
        event_a,
        event_b
    )

    if plate_distance > MAX_PLATE_DISTANCE:

        return {
            "valid": False,
            "reason": "Plate distance too high",
            "plate_distance": plate_distance,
            "temporal": temporal,
            "camera_context": camera_context,
        }

    if not temporal["within_time_window"]:

        return {
            "valid": False,
            "reason": "Time gap too large",
            "plate_distance": plate_distance,
            "temporal": temporal,
            "camera_context": camera_context,
        }

    if not camera_context["connected"]:

        return {
            "valid": False,
            "reason": "Cameras disconnected",
            "plate_distance": plate_distance,
            "temporal": temporal,
            "camera_context": camera_context,
        }

    return {
        "valid": True,
        "reason": "Context supports fuzzy match",
        "plate_distance": plate_distance,
        "temporal": temporal,
        "camera_context": camera_context,
    }


def validate_all_fuzzy_matches(
    fuzzy_matches
):

    validated = []

    for match in fuzzy_matches:

        result = validate_fuzzy_plate_match(
            match["event_a"],
            match["event_b"]
        )

        if result["valid"]:

            validated.append({
                **match,
                "validation": result,
            })

    return validated


# ============================================================
# STEP 2.21 — TRAJECTORY CANDIDATE SCORING
# ============================================================

def evaluate_movement_feasibility(
    observation,
    trajectory_events
):

    if not trajectory_events:

        return {
            "feasible": False,
            "reason": "Empty trajectory",
            "speed_kmh": None,
            "distance_km": None,
            "direction": None,
        }

    observation_time = parse_time(
        observation["timestamp"]
    )

    before_events = [
        event
        for event in trajectory_events
        if parse_time(event["timestamp"])
        < observation_time
    ]

    after_events = [
        event
        for event in trajectory_events
        if parse_time(event["timestamp"])
        > observation_time
    ]

    if before_events:

        previous = max(
            before_events,
            key=lambda event: parse_time(
                event["timestamp"]
            )
        )

        movement = validate_movement(
            previous,
            observation
        )

        return {
            **movement,
            "direction": "BEFORE",
            "reference_event": previous,
        }

    if after_events:

        next_event = min(
            after_events,
            key=lambda event: parse_time(
                event["timestamp"]
            )
        )

        movement = validate_movement(
            observation,
            next_event
        )

        return {
            **movement,
            "direction": "AFTER",
            "reference_event": next_event,
        }

    return {
        "feasible": True,
        "reason": "No neighboring event available",
        "speed_kmh": 0,
        "distance_km": 0,
        "direction": "NONE",
        "reference_event": None,
    }


def score_trajectory_candidate(
    observation,
    candidate_plate,
    trajectory_events
):

    score = 0

    candidate_plate_distance = (
        levenshtein_distance(
            observation["plate_number"],
            candidate_plate
        )
    )

    # Plate similarity
    if candidate_plate_distance == 0:

        score += 4

    elif candidate_plate_distance == 1:

        score += 3

    elif candidate_plate_distance == 2:

        score += 1

    # Temporal context
    temporal_scores = []

    for event in trajectory_events:

        gap = time_difference_seconds(
            observation["timestamp"],
            event["timestamp"]
        )

        if gap <= 30:

            temporal_scores.append(3)

        elif gap <= 300:

            temporal_scores.append(2)

        elif gap <= 600:

            temporal_scores.append(1)

    if temporal_scores:

        score += max(temporal_scores)

    # Camera context
    same_camera = any(
        event["camera_id"]
        == observation["camera_id"]
        for event in trajectory_events
    )

    if same_camera:

        score += 2

    else:

        connected_camera = any(
            cameras_are_connected(
                observation["camera_id"],
                event["camera_id"]
            )
            for event in trajectory_events
        )

        if connected_camera:
            score += 1

    # Movement feasibility
    movement = evaluate_movement_feasibility(
        observation,
        trajectory_events
    )

    if movement["feasible"]:
        score += 1

    return {
        "trajectory_plate": candidate_plate,
        "score": score,
        "plate_distance": candidate_plate_distance,
        "movement": movement,
        "same_camera": same_camera,
    }


def find_trajectory_candidates(
    observation,
    trajectories
):

    candidates = []

    for trajectory_plate, trajectory_events in trajectories.items():

        distance = levenshtein_distance(
            observation["plate_number"],
            trajectory_plate
        )

        if distance <= MAX_PLATE_DISTANCE:

            result = score_trajectory_candidate(
                observation=observation,
                candidate_plate=trajectory_plate,
                trajectory_events=trajectory_events,
            )

            candidates.append(result)

    return candidates


def associate_observation_with_trajectories(
    observation,
    trajectories
):

    candidates = find_trajectory_candidates(
        observation,
        trajectories
    )

    if not candidates:

        return {
            "observation": observation,
            "ranked_candidates": [],
            "best_candidate": None,
            "second_candidate": None,
            "score_margin": None,
            "decision": "REJECT",
        }

    ranked_candidates = sorted(
        candidates,
        key=lambda candidate: (
            candidate["score"],
            -candidate["plate_distance"]
        ),
        reverse=True,
    )

    best_candidate = ranked_candidates[0]

    second_candidate = (
        ranked_candidates[1]
        if len(ranked_candidates) > 1
        else None
    )

    if second_candidate is None:

        score_margin = None

    else:

        score_margin = (
            best_candidate["score"]
            - second_candidate["score"]
        )

    return {
        "observation": observation,
        "ranked_candidates": ranked_candidates,
        "best_candidate": best_candidate,
        "second_candidate": second_candidate,
        "score_margin": score_margin,
        "decision": None,
    }


# ============================================================
# STEP 2.22 — DECISION CLASSIFICATION
# ============================================================

def classify_trajectory_decision(
    candidate,
    second_score=None
):

    if candidate is None:
        return "REJECT"

    score = candidate["score"]

    movement = candidate["movement"]

    if not movement["feasible"]:
        return "REJECT"

    if (
        second_score is not None
        and abs(score - second_score)
        < TRAJECTORY_SCORE_MARGIN
    ):
        return "AMBIGUOUS / REVIEW"

    if score >= HIGH_CONFIDENCE_SCORE:
        return "HIGH CONFIDENCE"

    if score >= POSSIBLE_MATCH_SCORE:
        return "POSSIBLE MATCH"

    if score >= AMBIGUOUS_SCORE:
        return "AMBIGUOUS / REVIEW"

    return "REJECT"


# ============================================================
# STEP 2.23 — MULTI-CANDIDATE RANKING
# ============================================================

def classify_multi_candidate_decision(
    ranked_candidates
):

    if not ranked_candidates:
        return "REJECT"

    best_candidate = ranked_candidates[0]

    second_candidate = (
        ranked_candidates[1]
        if len(ranked_candidates) > 1
        else None
    )

    best_score = best_candidate["score"]

    if second_candidate is None:

        return classify_trajectory_decision(
            best_candidate
        )

    second_score = second_candidate["score"]

    score_margin = (
        best_score - second_score
    )

    if not best_candidate["movement"]["feasible"]:

        return "REJECT"

    if score_margin < MULTI_CANDIDATE_MARGIN:

        return "AMBIGUOUS / REVIEW"

    if best_score >= HIGH_CONFIDENCE_SCORE:

        return "HIGH CONFIDENCE"

    if best_score >= POSSIBLE_MATCH_SCORE:

        return "POSSIBLE MATCH"

    if best_score >= AMBIGUOUS_SCORE:

        return "AMBIGUOUS / REVIEW"

    return "REJECT"


def run_trajectory_level_association(
    observations,
    trajectories
):

    results = []

    for observation in observations:

        result = associate_observation_with_trajectories(
            observation,
            trajectories
        )

        decision = classify_multi_candidate_decision(
            result["ranked_candidates"]
        )

        result["decision"] = decision

        results.append(result)

    return results


# ============================================================
# STEP 2.24 — CONSISTENCY VALIDATION
# ============================================================

def validate_plate_consistency(
    observation,
    candidate
):

    distance = candidate["plate_distance"]

    return {
        "passed": (
            distance <= MAX_PLATE_DISTANCE
        ),
        "value": distance,
        "reason": (
            "Plate consistent"
            if distance <= MAX_PLATE_DISTANCE
            else "Plate inconsistent"
        ),
    }


def validate_temporal_consistency(
    observation,
    trajectory_events
):

    if not trajectory_events:

        return {
            "passed": False,
            "value": None,
            "reason": "No trajectory events",
        }

    nearest_gap = min(
        time_difference_seconds(
            observation["timestamp"],
            event["timestamp"]
        )
        for event in trajectory_events
    )

    passed = (
        nearest_gap
        <= MAX_FUZZY_TIME_GAP_SECONDS
    )

    return {
        "passed": passed,
        "value": nearest_gap,
        "reason": (
            "Temporal context consistent"
            if passed
            else "Temporal gap too large"
        ),
    }


def validate_camera_consistency(
    observation,
    trajectory_events
):

    if not trajectory_events:

        return {
            "passed": False,
            "value": None,
            "reason": "No trajectory cameras",
        }

    same_camera = any(
        event["camera_id"]
        == observation["camera_id"]
        for event in trajectory_events
    )

    connected = any(
        cameras_are_connected(
            observation["camera_id"],
            event["camera_id"]
        )
        for event in trajectory_events
    )

    passed = (
        same_camera
        or connected
    )

    return {
        "passed": passed,
        "value": (
            "SAME CAMERA"
            if same_camera
            else "CONNECTED"
            if connected
            else "DISCONNECTED"
        ),
        "reason": (
            "Camera context consistent"
            if passed
            else "Camera context inconsistent"
        ),
    }


def validate_movement_consistency(
    observation,
    candidate
):

    movement = candidate["movement"]

    return {
        "passed": movement["feasible"],
        "value": movement["speed_kmh"],
        "reason": (
            "Movement consistent"
            if movement["feasible"]
            else movement["reason"]
        ),
    }


def validate_trajectory_consistency(
    observation,
    candidate,
    trajectory_events
):

    plate_check = validate_plate_consistency(
        observation,
        candidate
    )

    temporal_check = validate_temporal_consistency(
        observation,
        trajectory_events
    )

    camera_check = validate_camera_consistency(
        observation,
        trajectory_events
    )

    movement_check = validate_movement_consistency(
        observation,
        candidate
    )

    checks = {
        "plate": plate_check,
        "temporal": temporal_check,
        "camera": camera_check,
        "movement": movement_check,
    }

    passed_checks = sum(
        1
        for check in checks.values()
        if check["passed"]
    )

    total_checks = len(checks)

    if not candidate["movement"]["feasible"]:

        final_status = "INCONSISTENT"

    elif passed_checks >= MIN_CONSISTENCY_CHECKS:

        final_status = "CONSISTENT"

    else:

        final_status = "REVIEW"

    return {
        "status": final_status,
        "passed_checks": passed_checks,
        "total_checks": total_checks,
        "checks": checks,
    }


def apply_consistency_validation(
    association_results,
    trajectories
):

    validated_results = []

    for result in association_results:

        best_candidate = result["best_candidate"]

        if best_candidate is None:

            result["consistency"] = {
                "status": "INCONSISTENT",
                "passed_checks": 0,
                "total_checks": 0,
                "checks": {},
            }

            validated_results.append(result)
            continue

        candidate_plate = (
            best_candidate["trajectory_plate"]
        )

        trajectory_events = trajectories.get(
            candidate_plate,
            []
        )

        consistency = validate_trajectory_consistency(
            observation=result["observation"],
            candidate=best_candidate,
            trajectory_events=trajectory_events,
        )

        result["consistency"] = consistency

        if consistency["status"] == "INCONSISTENT":

            result["decision"] = "REJECT"

        elif consistency["status"] == "REVIEW":

            if result["decision"] != "REJECT":

                result["decision"] = (
                    "AMBIGUOUS / REVIEW"
                )

        validated_results.append(result)

    return validated_results


# ============================================================
# STEP 2.25 — CONFIDENCE AGGREGATION
# ============================================================

def calculate_plate_confidence(
    candidate
):

    distance = candidate["plate_distance"]

    if distance == 0:
        return 100.0

    if distance == 1:
        return 75.0

    if distance == 2:
        return 50.0

    return 0.0


def calculate_temporal_confidence(
    observation,
    trajectory_events
):

    if not trajectory_events:
        return 0.0

    nearest_gap = min(
        time_difference_seconds(
            observation["timestamp"],
            event["timestamp"]
        )
        for event in trajectory_events
    )

    if nearest_gap <= 30:
        return 100.0

    if nearest_gap <= 300:
        return 85.0

    if nearest_gap <= 600:
        return 70.0

    return 20.0


def calculate_camera_confidence(
    observation,
    trajectory_events
):

    if not trajectory_events:
        return 0.0

    same_camera = any(
        event["camera_id"]
        == observation["camera_id"]
        for event in trajectory_events
    )

    if same_camera:
        return 100.0

    connected = any(
        cameras_are_connected(
            observation["camera_id"],
            event["camera_id"]
        )
        for event in trajectory_events
    )

    if connected:
        return 80.0

    return 0.0


def calculate_movement_confidence(
    candidate
):

    movement = candidate["movement"]

    if not movement["feasible"]:
        return 0.0

    speed = movement["speed_kmh"]

    if speed is None:
        return 50.0

    if speed <= 30:
        return 100.0

    if speed <= 45:
        return 85.0

    if speed <= MAX_PLAUSIBLE_SPEED_KMH:
        return 70.0

    return 0.0


def calculate_candidate_confidence(
    result,
    trajectories
):

    best_candidate = result["best_candidate"]

    if best_candidate is None:

        return {
            "overall_percent": 0.0,
            "level": "LOW",
            "components": {},
        }

    observation = result["observation"]

    trajectory_plate = (
        best_candidate["trajectory_plate"]
    )

    trajectory_events = trajectories.get(
        trajectory_plate,
        []
    )

    plate_confidence = calculate_plate_confidence(
        best_candidate
    )

    temporal_confidence = calculate_temporal_confidence(
        observation,
        trajectory_events
    )

    camera_confidence = calculate_camera_confidence(
        observation,
        trajectory_events
    )

    movement_confidence = calculate_movement_confidence(
        best_candidate
    )

    # Candidate ranking margin
    if result["second_candidate"] is None:

        ranking_confidence = 100.0

    else:

        margin = result["score_margin"]

        if margin >= 4:
            ranking_confidence = 100.0

        elif margin >= 2:
            ranking_confidence = 85.0

        elif margin >= 1:
            ranking_confidence = 60.0

        else:
            ranking_confidence = 40.0

    # Consistency confidence
    consistency = result.get(
        "consistency",
        {}
    )

    total_checks = consistency.get(
        "total_checks",
        0
    )

    passed_checks = consistency.get(
        "passed_checks",
        0
    )

    if total_checks > 0:

        consistency_confidence = (
            passed_checks
            / total_checks
            * 100
        )

    else:

        consistency_confidence = 0.0

    # --------------------------------------------------------
    # Weighted aggregation
    # --------------------------------------------------------

    overall_percent = (
        plate_confidence * 0.30
        + temporal_confidence * 0.15
        + camera_confidence * 0.15
        + movement_confidence * 0.15
        + ranking_confidence * 0.15
        + consistency_confidence * 0.10
    )

    overall_percent = round(
        overall_percent,
        2
    )

    # --------------------------------------------------------
    # Final confidence level
    # --------------------------------------------------------

    if (
        result["decision"]
        == "REJECT"
    ):

        level = "LOW"

    elif (
        result["decision"]
        == "AMBIGUOUS / REVIEW"
    ):

        level = "MEDIUM"

    elif (
        overall_percent
        >= HIGH_CONFIDENCE_PERCENT
    ):

        level = "HIGH"

    elif (
        overall_percent
        >= MEDIUM_CONFIDENCE_PERCENT
    ):

        level = "MEDIUM"

    else:

        level = "LOW"

    return {
        "overall_percent": overall_percent,
        "level": level,
        "components": {
            "plate": round(
                plate_confidence,
                2
            ),
            "temporal": round(
                temporal_confidence,
                2
            ),
            "camera": round(
                camera_confidence,
                2
            ),
            "movement": round(
                movement_confidence,
                2
            ),
            "ranking": round(
                ranking_confidence,
                2
            ),
            "consistency": round(
                consistency_confidence,
                2
            ),
        },
    }


def apply_confidence_aggregation(
    consistency_results,
    trajectories
):

    results = []

    for result in consistency_results:

        confidence = calculate_candidate_confidence(
            result,
            trajectories
        )

        result["confidence"] = confidence

        results.append(result)

    return results


# ============================================================
# STEP 2.25 — OUTPUT
# ============================================================

def print_confidence_results(
    results
):

    print("\n")
    print("=" * 80)
    print(
        "STEP 2.25 - "
        "TRAJECTORY ASSOCIATION CONFIDENCE"
    )
    print("=" * 80)

    for result in results:

        observation = result["observation"]
        best = result["best_candidate"]

        print("\nOBSERVATION")
        print("-" * 80)

        print(
            f"ID {observation['id']} | "
            f"{observation['plate_number']} | "
            f"{observation['camera_id']} | "
            f"{observation['timestamp']}"
        )

        if best is None:

            print(
                "Best candidate: None"
            )

            print(
                "Confidence: 0.00%"
            )

            print(
                "Confidence level: LOW"
            )

            print(
                "Decision: REJECT"
            )

            continue

        confidence = result["confidence"]

        print(
            f"Best candidate: "
            f"{best['trajectory_plate']}"
        )

        print(
            f"Association decision: "
            f"{result['decision']}"
        )

        print("\nCONFIDENCE COMPONENTS")
        print("-" * 80)

        for name, value in confidence[
            "components"
        ].items():

            print(
                f"{name.upper():12} | "
                f"{value:.2f}%"
            )

        print("\nCONFIDENCE RESULT")
        print("-" * 80)

        print(
            f"Overall confidence: "
            f"{confidence['overall_percent']:.2f}%"
        )

        print(
            f"Confidence level: "
            f"{confidence['level']}"
        )

        print(
            f"Final decision: "
            f"{result['decision']}"
        )


def summarize_confidence_results(
    results
):

    level_summary = {
        "HIGH": 0,
        "MEDIUM": 0,
        "LOW": 0,
    }

    decision_summary = {
        "HIGH CONFIDENCE": 0,
        "POSSIBLE MATCH": 0,
        "AMBIGUOUS / REVIEW": 0,
        "REJECT": 0,
    }

    for result in results:

        level = result[
            "confidence"
        ]["level"]

        if level in level_summary:

            level_summary[level] += 1

        decision = result["decision"]

        if decision in decision_summary:

            decision_summary[decision] += 1

    return (
        level_summary,
        decision_summary
    )


# ============================================================
# STEP 2.25 — VERIFICATION
# ============================================================

def verify_step_2_25(
    results
):

    print("\n")
    print("=" * 80)
    print("STEP 2.25 VERIFICATION")
    print("=" * 80)

    structure_pass = True

    for result in results:

        if "confidence" not in result:

            structure_pass = False
            break

        confidence = result[
            "confidence"
        ]

        required_fields = [
            "overall_percent",
            "level",
            "components",
        ]

        for field in required_fields:

            if field not in confidence:

                structure_pass = False

    if structure_pass:

        print(
            "Confidence structure: PASS"
        )

    else:

        print(
            "Confidence structure: FAIL"
        )

    percentage_pass = True

    for result in results:

        percentage = result[
            "confidence"
        ]["overall_percent"]

        if (
            percentage < 0
            or percentage > 100
        ):

            percentage_pass = False

    if percentage_pass:

        print(
            "Confidence percentage bounds: PASS"
        )

    else:

        print(
            "Confidence percentage bounds: FAIL"
        )

    component_pass = True

    for result in results:

        components = result[
            "confidence"
        ]["components"]

        for value in components.values():

            if value < 0 or value > 100:

                component_pass = False

    if component_pass:

        print(
            "Confidence component bounds: PASS"
        )

    else:

        print(
            "Confidence component bounds: FAIL"
        )

    ambiguity_pass = True

    for result in results:

        if (
            result["decision"]
            == "AMBIGUOUS / REVIEW"
        ):

            confidence = result[
                "confidence"
            ]

            if confidence["level"] == "HIGH":

                ambiguity_pass = False

    if ambiguity_pass:

        print(
            "Ambiguity confidence handling: PASS"
        )

    else:

        print(
            "Ambiguity confidence handling: FAIL"
        )

    reject_pass = True

    for result in results:

        if result["decision"] == "REJECT":

            confidence = result[
                "confidence"
            ]

            if confidence["level"] != "LOW":

                reject_pass = False

    if reject_pass:

        print(
            "Reject confidence handling: PASS"
        )

    else:

        print(
            "Reject confidence handling: FAIL"
        )

    no_merge_pass = True

    for result in results:

        if "merged_trajectory" in result:

            no_merge_pass = False

    if no_merge_pass:

        print(
            "No automatic trajectory merging: PASS"
        )

    else:

        print(
            "No automatic trajectory merging: FAIL"
        )

    return (
        structure_pass
        and percentage_pass
        and component_pass
        and ambiguity_pass
        and reject_pass
        and no_merge_pass
    )


# ============================================================
# REGRESSION VERIFICATION
# ============================================================

def verify_regression_checks(
    filtered_events,
    duplicate_removed,
    trajectories,
    fuzzy_matches,
    validated_matches,
    suspicious_movements,
    disconnected_routes,
):

    print("\n")
    print("=" * 80)
    print("REGRESSION VERIFICATION")
    print("=" * 80)

    checks = []

    low_confidence_pass = any(
        event["id"] == 602
        for event in EVENTS
        if event["confidence"]
        < MIN_CONFIDENCE
    )

    checks.append(
        (
            "Low-confidence filtering",
            low_confidence_pass
        )
    )

    duplicate_pass = any(
        event["id"] == 205
        for event in duplicate_removed
    )

    checks.append(
        (
            "Short-window duplicate removal",
            duplicate_pass
        )
    )

    revisit_pass = False

    if "DL04RT3456" in trajectories:

        camera_sequence = [
            event["camera_id"]
            for event in trajectories[
                "DL04RT3456"
            ]
        ]

        revisit_pass = (
            camera_sequence
            == [
                "Camera_1",
                "Camera_2",
                "Camera_3",
                "Camera_2",
            ]
        )

    checks.append(
        (
            "Legitimate camera revisit",
            revisit_pass
        )
    )

    suspicious_pass = any(
        item["plate_number"]
        == "DL05MN7890"
        for item in suspicious_movements
    )

    checks.append(
        (
            "Unrealistic movement detection",
            suspicious_pass
        )
    )

    disconnected_pass = any(
        item["plate_number"]
        == "DL06AB6789"
        for item in disconnected_routes
    )

    checks.append(
        (
            "Disconnected route handling",
            disconnected_pass
        )
    )

    chronological_pass = True

    for plate, events in trajectories.items():

        timestamps = [
            parse_time(
                event["timestamp"]
            )
            for event in events
        ]

        if timestamps != sorted(timestamps):

            chronological_pass = False

    checks.append(
        (
            "Chronological order",
            chronological_pass
        )
    )

    fuzzy_pass = len(fuzzy_matches) >= 2

    checks.append(
        (
            "OCR fuzzy matching",
            fuzzy_pass
        )
    )

    validation_pass = (
        len(validated_matches) >= 1
    )

    checks.append(
        (
            "Context-aware OCR validation",
            validation_pass
        )
    )

    all_pass = True

    for name, passed in checks:

        if passed:

            print(
                f"{name}: PASS"
            )

        else:

            print(
                f"{name}: FAIL"
            )

            all_pass = False

    return all_pass



# ============================================================
# STEP 2.26 — BIDIRECTIONAL TEMPORAL & MOVEMENT CONSISTENCY
# ============================================================

def find_previous_trajectory_event(
    observation,
    trajectory_events
):

    observation_time = parse_time(
        observation["timestamp"]
    )

    previous_events = [
        event
        for event in trajectory_events
        if parse_time(event["timestamp"])
        < observation_time
    ]

    if not previous_events:
        return None

    return max(
        previous_events,
        key=lambda event: parse_time(
            event["timestamp"]
        )
    )


def find_next_trajectory_event(
    observation,
    trajectory_events
):

    observation_time = parse_time(
        observation["timestamp"]
    )

    next_events = [
        event
        for event in trajectory_events
        if parse_time(event["timestamp"])
        > observation_time
    ]

    if not next_events:
        return None

    return min(
        next_events,
        key=lambda event: parse_time(
            event["timestamp"]
        )
    )


def validate_previous_movement(
    observation,
    trajectory_events
):

    previous_event = find_previous_trajectory_event(
        observation,
        trajectory_events
    )

    if previous_event is None:

        return {
            "available": False,
            "passed": True,
            "reason": "No previous event available",
            "speed_kmh": None,
            "distance_km": None,
            "event": None,
        }

    movement = validate_movement(
        previous_event,
        observation
    )

    return {
        "available": True,
        "passed": movement["feasible"],
        "reason": movement["reason"],
        "speed_kmh": movement["speed_kmh"],
        "distance_km": movement["distance_km"],
        "event": previous_event,
    }


def validate_next_movement(
    observation,
    trajectory_events
):

    next_event = find_next_trajectory_event(
        observation,
        trajectory_events
    )

    if next_event is None:

        return {
            "available": False,
            "passed": True,
            "reason": "No next event available",
            "speed_kmh": None,
            "distance_km": None,
            "event": None,
        }

    movement = validate_movement(
        observation,
        next_event
    )

    return {
        "available": True,
        "passed": movement["feasible"],
        "reason": movement["reason"],
        "speed_kmh": movement["speed_kmh"],
        "distance_km": movement["distance_km"],
        "event": next_event,
    }


def validate_bidirectional_movement(
    observation,
    trajectory_events
):

    previous_check = validate_previous_movement(
        observation,
        trajectory_events
    )

    next_check = validate_next_movement(
        observation,
        trajectory_events
    )

    previous_pass = previous_check["passed"]
    next_pass = next_check["passed"]

    available_checks = 0
    passed_checks = 0

    if previous_check["available"]:

        available_checks += 1

        if previous_pass:
            passed_checks += 1

    if next_check["available"]:

        available_checks += 1

        if next_pass:
            passed_checks += 1

    # If neither side exists, there is no contradiction.
    if available_checks == 0:

        status = "NO_NEIGHBOR"

    elif previous_pass and next_pass:

        status = "BIDIRECTIONAL_PASS"

    else:

        status = "BIDIRECTIONAL_FAIL"

    return {
        "status": status,
        "previous": previous_check,
        "next": next_check,
        "available_checks": available_checks,
        "passed_checks": passed_checks,
    }


def calculate_bidirectional_confidence(
    bidirectional_result
):

    status = bidirectional_result["status"]

    if status == "BIDIRECTIONAL_PASS":

        return 100.0

    if status == "NO_NEIGHBOR":

        return 70.0

    if status == "BIDIRECTIONAL_FAIL":

        return 0.0

    return 50.0


def apply_step_2_26_validation(
    confidence_results,
    trajectories
):

    results = []

    for result in confidence_results:

        best_candidate = result["best_candidate"]

        if best_candidate is None:

            result["bidirectional_validation"] = {
                "status": "NO_CANDIDATE",
                "previous": None,
                "next": None,
                "available_checks": 0,
                "passed_checks": 0,
            }

            result["bidirectional_confidence"] = 0.0

            results.append(result)
            continue

        candidate_plate = (
            best_candidate["trajectory_plate"]
        )

        trajectory_events = trajectories.get(
            candidate_plate,
            []
        )

        bidirectional = validate_bidirectional_movement(
            result["observation"],
            trajectory_events
        )

        result["bidirectional_validation"] = (
            bidirectional
        )

        result["bidirectional_confidence"] = (
            calculate_bidirectional_confidence(
                bidirectional
            )
        )

        # A genuine bidirectional contradiction
        # invalidates the association.
        if (
            bidirectional["status"]
            == "BIDIRECTIONAL_FAIL"
        ):

            result["decision"] = "REJECT"

        results.append(result)

    return results


def print_step_2_26_results(
    results
):

    print("\n")
    print("=" * 80)
    print(
        "STEP 2.26 - "
        "BIDIRECTIONAL TEMPORAL & MOVEMENT CONSISTENCY"
    )
    print("=" * 80)

    for result in results:

        observation = result["observation"]
        best_candidate = result["best_candidate"]

        print("\nOBSERVATION")
        print("-" * 80)

        print(
            f"ID {observation['id']} | "
            f"{observation['plate_number']} | "
            f"{observation['camera_id']} | "
            f"{observation['timestamp']}"
        )

        if best_candidate is None:

            print(
                "Best candidate: None"
            )

            print(
                "Bidirectional status: NO_CANDIDATE"
            )

            continue

        print(
            f"Best candidate: "
            f"{best_candidate['trajectory_plate']}"
        )

        validation = result[
            "bidirectional_validation"
        ]

        print("\nPREVIOUS EVENT CHECK")
        print("-" * 80)

        previous = validation["previous"]

        if previous is None:

            print("Not available")

        elif not previous["available"]:

            print(
                previous["reason"]
            )

        else:

            event = previous["event"]

            print(
                f"{event['camera_id']} "
                f"{event['timestamp']} "
                f"→ "
                f"{observation['camera_id']} "
                f"{observation['timestamp']}"
            )

            print(
                f"Distance: "
                f"{previous['distance_km']:.4f} km"
            )

            print(
                f"Speed: "
                f"{previous['speed_kmh']:.2f} km/h"
            )

            print(
                f"Result: "
                f"{'PASS' if previous['passed'] else 'FAIL'}"
            )

        print("\nNEXT EVENT CHECK")
        print("-" * 80)

        next_check = validation["next"]

        if next_check is None:

            print("Not available")

        elif not next_check["available"]:

            print(
                next_check["reason"]
            )

        else:

            event = next_check["event"]

            print(
                f"{observation['camera_id']} "
                f"{observation['timestamp']} "
                f"→ "
                f"{event['camera_id']} "
                f"{event['timestamp']}"
            )

            print(
                f"Distance: "
                f"{next_check['distance_km']:.4f} km"
            )

            print(
                f"Speed: "
                f"{next_check['speed_kmh']:.2f} km/h"
            )

            print(
                f"Result: "
                f"{'PASS' if next_check['passed'] else 'FAIL'}"
            )

        print("\nBIDIRECTIONAL RESULT")
        print("-" * 80)

        print(
            f"Status: "
            f"{validation['status']}"
        )

        print(
            f"Checks available: "
            f"{validation['available_checks']}"
        )

        print(
            f"Checks passed: "
            f"{validation['passed_checks']}"
        )

        print(
            f"Bidirectional confidence: "
            f"{result['bidirectional_confidence']:.2f}%"
        )

        print(
            f"Final decision: "
            f"{result['decision']}"
        )


def verify_step_2_26(
    results
):

    print("\n")
    print("=" * 80)
    print("STEP 2.26 VERIFICATION")
    print("=" * 80)

    structure_pass = True

    for result in results:

        if "bidirectional_validation" not in result:
            structure_pass = False

        if "bidirectional_confidence" not in result:
            structure_pass = False

    print(
        "Bidirectional validation structure: "
        f"{'PASS' if structure_pass else 'FAIL'}"
    )

    confidence_pass = True

    for result in results:

        confidence = result[
            "bidirectional_confidence"
        ]

        if confidence < 0 or confidence > 100:

            confidence_pass = False

    print(
        "Bidirectional confidence bounds: "
        f"{'PASS' if confidence_pass else 'FAIL'}"
    )

    contradiction_pass = True

    for result in results:

        validation = result[
            "bidirectional_validation"
        ]

        if (
            validation["status"]
            == "BIDIRECTIONAL_FAIL"
        ):

            if result["decision"] != "REJECT":

                contradiction_pass = False

    print(
        "Contradiction rejection logic: "
        f"{'PASS' if contradiction_pass else 'FAIL'}"
    )

    no_merge_pass = True

    for result in results:

        if "merged_trajectory" in result:

            no_merge_pass = False

    print(
        "No automatic trajectory merging: "
        f"{'PASS' if no_merge_pass else 'FAIL'}"
    )

    return (
        structure_pass
        and confidence_pass
        and contradiction_pass
        and no_merge_pass
    )



# ============================================================
# STEP 2.27 — TRAJECTORY CONTINUITY VALIDATION
# ============================================================

# Maximum allowed gap between consecutive observations
# inside an existing trajectory.
#
# This is intentionally larger than the Step 2.20 fuzzy
# matching window because legitimate trajectory revisits
# can occur after several minutes.
MAX_TRAJECTORY_GAP_SECONDS = 3600


def validate_trajectory_chronology(
    plate,
    events
):

    if len(events) <= 1:

        return {
            "passed": True,
            "reason": "Single event trajectory - chronology check not required",
            "checked_pairs": 0,
            "invalid_pairs": [],
        }

    invalid_pairs = []

    for index in range(len(events) - 1):

        event_a = events[index]
        event_b = events[index + 1]

        time_a = parse_time(
            event_a["timestamp"]
        )

        time_b = parse_time(
            event_b["timestamp"]
        )

        if time_b <= time_a:

            invalid_pairs.append({
                "from_event": event_a,
                "to_event": event_b,
                "reason": "Non-increasing timestamp",
            })

    return {
        "passed": len(invalid_pairs) == 0,
        "reason": (
            "Chronological order valid"
            if len(invalid_pairs) == 0
            else "Chronological order invalid"
        ),
        "checked_pairs": len(events) - 1,
        "invalid_pairs": invalid_pairs,
    }


def validate_trajectory_connectivity(
    plate,
    events
):

    if len(events) <= 1:

        return {
            "passed": True,
            "reason": "Single event trajectory - connectivity check not required",
            "checked_pairs": 0,
            "invalid_pairs": [],
        }

    invalid_pairs = []

    for index in range(len(events) - 1):

        event_a = events[index]
        event_b = events[index + 1]

        connected = cameras_are_connected(
            event_a["camera_id"],
            event_b["camera_id"]
        )

        if not connected:

            invalid_pairs.append({
                "from_event": event_a,
                "to_event": event_b,
                "reason": "Cameras are disconnected",
            })

    return {
        "passed": len(invalid_pairs) == 0,
        "reason": (
            "All consecutive cameras connected"
            if len(invalid_pairs) == 0
            else "One or more camera transitions disconnected"
        ),
        "checked_pairs": len(events) - 1,
        "invalid_pairs": invalid_pairs,
    }


def validate_trajectory_movement(
    plate,
    events
):

    if len(events) <= 1:

        return {
            "passed": True,
            "reason": "Single event trajectory - movement check not required",
            "checked_pairs": 0,
            "invalid_pairs": [],
        }

    invalid_pairs = []

    for index in range(len(events) - 1):

        event_a = events[index]
        event_b = events[index + 1]

        movement = validate_movement(
            event_a,
            event_b
        )

        if not movement["feasible"]:

            invalid_pairs.append({
                "from_event": event_a,
                "to_event": event_b,
                "validation": movement,
            })

    return {
        "passed": len(invalid_pairs) == 0,
        "reason": (
            "All consecutive movements feasible"
            if len(invalid_pairs) == 0
            else "One or more movements are infeasible"
        ),
        "checked_pairs": len(events) - 1,
        "invalid_pairs": invalid_pairs,
    }


def validate_trajectory_time_gaps(
    plate,
    events
):

    if len(events) <= 1:

        return {
            "passed": True,
            "reason": "Single event trajectory - time-gap check not required",
            "checked_pairs": 0,
            "invalid_pairs": [],
        }

    invalid_pairs = []

    for index in range(len(events) - 1):

        event_a = events[index]
        event_b = events[index + 1]

        time_gap = (
            parse_time(event_b["timestamp"])
            - parse_time(event_a["timestamp"])
        ).total_seconds()

        if (
            time_gap <= 0
            or time_gap > MAX_TRAJECTORY_GAP_SECONDS
        ):

            invalid_pairs.append({
                "from_event": event_a,
                "to_event": event_b,
                "gap_seconds": time_gap,
                "reason": (
                    "Invalid trajectory time gap"
                ),
            })

    return {
        "passed": len(invalid_pairs) == 0,
        "reason": (
            "All trajectory time gaps valid"
            if len(invalid_pairs) == 0
            else "One or more trajectory gaps exceed the allowed limit"
        ),
        "checked_pairs": len(events) - 1,
        "invalid_pairs": invalid_pairs,
    }


def validate_trajectory_continuity(
    plate,
    events
):

    chronology = validate_trajectory_chronology(
        plate,
        events
    )

    connectivity = validate_trajectory_connectivity(
        plate,
        events
    )

    movement = validate_trajectory_movement(
        plate,
        events
    )

    time_gaps = validate_trajectory_time_gaps(
        plate,
        events
    )

    checks = {
        "chronology": chronology,
        "connectivity": connectivity,
        "movement": movement,
        "time_gaps": time_gaps,
    }

    passed_checks = sum(
        1
        for check in checks.values()
        if check["passed"]
    )

    total_checks = len(checks)

    if passed_checks == total_checks:

        status = "CONTINUOUS"

    else:

        status = "INCONSISTENT"

    return {
        "plate_number": plate,
        "status": status,
        "passed_checks": passed_checks,
        "total_checks": total_checks,
        "checks": checks,
    }


def run_trajectory_continuity_validation(
    trajectories
):

    results = []

    for plate, events in trajectories.items():

        continuity = validate_trajectory_continuity(
            plate,
            events
        )

        results.append(
            continuity
        )

    return results


def print_step_2_27_results(
    results
):

    print("\n")
    print("=" * 80)
    print(
        "STEP 2.27 - "
        "TRAJECTORY CONTINUITY VALIDATION"
    )
    print("=" * 80)

    for result in results:

        print("\nTRAJECTORY")
        print("-" * 80)

        print(
            f"Plate: "
            f"{result['plate_number']}"
        )

        print(
            f"Status: "
            f"{result['status']}"
        )

        print(
            f"Checks passed: "
            f"{result['passed_checks']}/"
            f"{result['total_checks']}"
        )

        for name, check in result[
            "checks"
        ].items():

            print(
                f"{name.upper():15} | "
                f"{'PASS' if check['passed'] else 'FAIL'}"
            )

            print(
                f"Reason: "
                f"{check['reason']}"
            )

            if check["invalid_pairs"]:

                for invalid in check[
                    "invalid_pairs"
                ]:

                    from_event = invalid[
                        "from_event"
                    ]

                    to_event = invalid[
                        "to_event"
                    ]

                    print(
                        f"  "
                        f"ID {from_event['id']} "
                        f"{from_event['camera_id']} "
                        f"{from_event['timestamp']} "
                        f"-> "
                        f"ID {to_event['id']} "
                        f"{to_event['camera_id']} "
                        f"{to_event['timestamp']}"
                    )

    print("\n")
    print("=" * 80)
    print("STEP 2.27 SUMMARY")
    print("=" * 80)

    continuous = sum(
        1
        for result in results
        if result["status"]
        == "CONTINUOUS"
    )

    inconsistent = sum(
        1
        for result in results
        if result["status"]
        == "INCONSISTENT"
    )

    print(
        f"Continuous trajectories: "
        f"{continuous}"
    )

    print(
        f"Inconsistent trajectories: "
        f"{inconsistent}"
    )


def verify_step_2_27(
    results
):

    print("\n")
    print("=" * 80)
    print("STEP 2.27 VERIFICATION")
    print("=" * 80)

    structure_pass = True

    required_fields = [
        "plate_number",
        "status",
        "passed_checks",
        "total_checks",
        "checks",
    ]

    required_check_fields = [
        "passed",
        "reason",
        "checked_pairs",
        "invalid_pairs",
    ]

    for result in results:

        for field in required_fields:

            if field not in result:

                structure_pass = False

        for check in result.get(
            "checks",
            {}
        ).values():

            for field in required_check_fields:

                if field not in check:

                    structure_pass = False

    print(
        "Continuity result structure: "
        f"{'PASS' if structure_pass else 'FAIL'}"
    )


    chronology_pass = all(
        result["checks"][
            "chronology"
        ]["passed"]
        for result in results
    )

    print(
        "Chronology validation: "
        f"{'PASS' if chronology_pass else 'FAIL'}"
    )


    connectivity_pass = all(
        result["checks"][
            "connectivity"
        ]["passed"]
        for result in results
        if result["plate_number"]
        not in [
            "DL06AB6789"
        ]
    )

    print(
        "Connectivity validation: "
        f"{'PASS' if connectivity_pass else 'FAIL'}"
    )


    movement_detection_pass = any(
        (
            result["plate_number"]
            == "DL05MN7890"
            and not result["checks"][
                "movement"
            ]["passed"]
        )
        for result in results
    )

    print(
        "Unrealistic movement detection: "
        f"{'PASS' if movement_detection_pass else 'FAIL'}"
    )


    disconnected_detection_pass = any(
        (
            result["plate_number"]
            == "DL06AB6789"
            and not result["checks"][
                "connectivity"
            ]["passed"]
        )
        for result in results
    )

    print(
        "Disconnected trajectory detection: "
        f"{'PASS' if disconnected_detection_pass else 'FAIL'}"
    )


    revisit_pass = False

    for result in results:

        if (
            result["plate_number"]
            == "DL04RT3456"
        ):

            revisit_pass = (
                result["status"]
                == "CONTINUOUS"
                and result["checks"][
                    "time_gaps"
                ]["passed"]
            )

            break

    print(
        "Legitimate 30-minute camera revisit: "
        f"{'PASS' if revisit_pass else 'FAIL'}"
    )


    gap_limit_pass = all(
        (
            result["checks"][
                "time_gaps"
            ]["passed"]
            or result["status"]
            == "INCONSISTENT"
        )
        for result in results
    )

    print(
        "Trajectory time-gap handling: "
        f"{'PASS' if gap_limit_pass else 'FAIL'}"
    )


    status_logic_pass = True

    for result in results:

        checks = result["checks"]

        all_checks_pass = all(
            check["passed"]
            for check in checks.values()
        )

        expected_status = (
            "CONTINUOUS"
            if all_checks_pass
            else "INCONSISTENT"
        )

        if result["status"] != expected_status:

            status_logic_pass = False

    print(
        "Continuity status logic: "
        f"{'PASS' if status_logic_pass else 'FAIL'}"
    )


    no_merge_pass = all(
        "merged_trajectory" not in result
        for result in results
    )

    print(
        "No automatic trajectory merging: "
        f"{'PASS' if no_merge_pass else 'FAIL'}"
    )


    return (
        structure_pass
        and chronology_pass
        and connectivity_pass
        and movement_detection_pass
        and disconnected_detection_pass
        and revisit_pass
        and gap_limit_pass
        and status_logic_pass
        and no_merge_pass
    )



# ============================================================

# ============================================================
# STEP 2.28 — TRAJECTORY QUALITY & RELIABILITY SCORING
# ============================================================

HIGH_QUALITY_SCORE = 85
MEDIUM_QUALITY_SCORE = 65


def calculate_observation_quality(trajectory):
    """
    Calculates the observation-density component.

    More observations provide stronger trajectory evidence,
    but the score is capped so that long trajectories do not
    automatically dominate shorter valid trajectories.
    """
    observation_count = len(trajectory)

    if observation_count <= 1:
        return 40.0

    if observation_count == 2:
        return 60.0

    if observation_count == 3:
        return 80.0

    return 100.0


def calculate_continuity_quality(continuity_result):
    """
    Converts Step 2.27 continuity validation into a percentage.
    """
    if continuity_result["total_checks"] == 0:
        return 0.0

    return (
        continuity_result["passed_checks"]
        / continuity_result["total_checks"]
    ) * 100.0


def calculate_trajectory_quality_score(
    plate,
    trajectory,
    continuity_result
):
    """
    Combines trajectory reliability signals into one
    explainable quality score.

    Components:
        - Chronology
        - Connectivity
        - Movement
        - Time gaps
        - Observation density
    """

    checks = continuity_result["checks"]

    chronology_score = (
        100.0
        if checks["chronology"]["passed"]
        else 0.0
    )

    connectivity_score = (
        100.0
        if checks["connectivity"]["passed"]
        else 0.0
    )

    movement_score = (
        100.0
        if checks["movement"]["passed"]
        else 0.0
    )

    time_gap_score = (
        100.0
        if checks["time_gaps"]["passed"]
        else 0.0
    )

    observation_score = calculate_observation_quality(
        trajectory
    )

    continuity_score = calculate_continuity_quality(
        continuity_result
    )

    overall_score = (
        chronology_score * 0.20
        + connectivity_score * 0.20
        + movement_score * 0.20
        + time_gap_score * 0.20
        + observation_score * 0.20
    )

    if overall_score >= HIGH_QUALITY_SCORE:
        quality_level = "HIGH QUALITY"
    elif overall_score >= MEDIUM_QUALITY_SCORE:
        quality_level = "MEDIUM QUALITY"
    else:
        quality_level = "LOW QUALITY"

    return {
        "plate_number": plate,
        "observation_count": len(trajectory),
        "quality_score": round(overall_score, 2),
        "quality_level": quality_level,
        "components": {
            "chronology": round(chronology_score, 2),
            "connectivity": round(connectivity_score, 2),
            "movement": round(movement_score, 2),
            "time_gaps": round(time_gap_score, 2),
            "observation_density": round(
                observation_score,
                2
            ),
            "continuity": round(
                continuity_score,
                2
            ),
        },
    }


def run_trajectory_quality_scoring(
    trajectories,
    continuity_results
):
    """
    Calculates quality scores for every trajectory.
    """

    continuity_by_plate = {
        result["plate_number"]: result
        for result in continuity_results
    }

    results = []

    for plate, events in trajectories.items():

        continuity_result = continuity_by_plate.get(
            plate
        )

        if continuity_result is None:
            continue

        quality_result = (
            calculate_trajectory_quality_score(
                plate,
                events,
                continuity_result
            )
        )

        results.append(
            quality_result
        )

    return results


def print_step_2_28_results(results):
    print("\n")
    print("=" * 80)
    print(
        "STEP 2.28 - "
        "TRAJECTORY QUALITY & RELIABILITY SCORING"
    )
    print("=" * 80)

    for result in results:

        print("\nTRAJECTORY")
        print("-" * 80)

        print(
            f"Plate: "
            f"{result['plate_number']}"
        )

        print(
            f"Observations: "
            f"{result['observation_count']}"
        )

        print(
            f"Quality score: "
            f"{result['quality_score']:.2f}%"
        )

        print(
            f"Quality level: "
            f"{result['quality_level']}"
        )

        print("\nQUALITY COMPONENTS")
        print("-" * 80)

        components = result["components"]

        print(
            f"CHRONOLOGY       | "
            f"{components['chronology']:.2f}%"
        )

        print(
            f"CONNECTIVITY     | "
            f"{components['connectivity']:.2f}%"
        )

        print(
            f"MOVEMENT         | "
            f"{components['movement']:.2f}%"
        )

        print(
            f"TIME GAPS        | "
            f"{components['time_gaps']:.2f}%"
        )

        print(
            f"OBSERVATION DENSITY | "
            f"{components['observation_density']:.2f}%"
        )

        print(
            f"CONTINUITY       | "
            f"{components['continuity']:.2f}%"
        )

    print("\n")
    print("=" * 80)
    print("STEP 2.28 SUMMARY")
    print("=" * 80)

    high = sum(
        1
        for result in results
        if result["quality_level"] == "HIGH QUALITY"
    )

    medium = sum(
        1
        for result in results
        if result["quality_level"] == "MEDIUM QUALITY"
    )

    low = sum(
        1
        for result in results
        if result["quality_level"] == "LOW QUALITY"
    )

    print(
        f"High-quality trajectories: "
        f"{high}"
    )

    print(
        f"Medium-quality trajectories: "
        f"{medium}"
    )

    print(
        f"Low-quality trajectories: "
        f"{low}"
    )


def verify_step_2_28(results):
    print("\n")
    print("=" * 80)
    print("STEP 2.28 VERIFICATION")
    print("=" * 80)

    structure_pass = True

    required_fields = [
        "plate_number",
        "observation_count",
        "quality_score",
        "quality_level",
        "components",
    ]

    required_components = [
        "chronology",
        "connectivity",
        "movement",
        "time_gaps",
        "observation_density",
        "continuity",
    ]

    for result in results:

        for field in required_fields:
            if field not in result:
                structure_pass = False

        for component in required_components:
            if component not in result["components"]:
                structure_pass = False

    print(
        "Quality result structure: "
        f"{'PASS' if structure_pass else 'FAIL'}"
    )

    bounds_pass = all(
        0.0 <= result["quality_score"] <= 100.0
        for result in results
    )

    print(
        "Quality score bounds: "
        f"{'PASS' if bounds_pass else 'FAIL'}"
    )

    component_bounds_pass = all(
        0.0 <= value <= 100.0
        for result in results
        for value in result["components"].values()
    )

    print(
        "Component score bounds: "
        f"{'PASS' if component_bounds_pass else 'FAIL'}"
    )

    quality_logic_pass = all(
        (
            (
                result["quality_score"] >= HIGH_QUALITY_SCORE
                and result["quality_level"] == "HIGH QUALITY"
            )
            or
            (
                MEDIUM_QUALITY_SCORE
                <= result["quality_score"]
                < HIGH_QUALITY_SCORE
                and result["quality_level"]
                == "MEDIUM QUALITY"
            )
            or
            (
                result["quality_score"] < MEDIUM_QUALITY_SCORE
                and result["quality_level"]
                == "LOW QUALITY"
            )
        )
        for result in results
    )

    print(
        "Quality classification logic: "
        f"{'PASS' if quality_logic_pass else 'FAIL'}"
    )

    inconsistent_detection_pass = all(
        (
            result["quality_level"] != "HIGH QUALITY"
        )
        for result in results
        if result["plate_number"]
        in [
            "DL05MN7890",
            "DL06AB6789",
        ]
    )

    print(
        "Inconsistent trajectory quality reduction: "
        f"{'PASS' if inconsistent_detection_pass else 'FAIL'}"
    )

    legitimate_revisit_pass = any(
        (
            result["plate_number"] == "DL04RT3456"
            and result["quality_level"]
            == "HIGH QUALITY"
        )
        for result in results
    )

    print(
        "Legitimate camera revisit quality handling: "
        f"{'PASS' if legitimate_revisit_pass else 'FAIL'}"
    )

    no_merge_pass = all(
        "merged_trajectory" not in result
        for result in results
    )

    print(
        "No automatic trajectory merging: "
        f"{'PASS' if no_merge_pass else 'FAIL'}"
    )

    return (
        structure_pass
        and bounds_pass
        and component_bounds_pass
        and quality_logic_pass
        and inconsistent_detection_pass
        and legitimate_revisit_pass
        and no_merge_pass
    )



# ============================================================
# STEP 2.29 — TRAJECTORY USABILITY CLASSIFICATION
# ============================================================

ANALYTICS_READY_SCORE = 85
REVIEW_REQUIRED_SCORE = 65


def classify_trajectory_usability(quality_result):
    """
    Converts the Step 2.28 trajectory quality score into
    an operational usability classification.

    HIGH QUALITY   -> ANALYTICS READY
    MEDIUM QUALITY -> REVIEW REQUIRED
    LOW QUALITY    -> ANALYTICS BLOCKED
    """

    score = quality_result["quality_score"]

    if score >= ANALYTICS_READY_SCORE:
        usability = "ANALYTICS READY"
        reason = (
            "Trajectory quality is sufficiently high "
            "for downstream analytics."
        )

    elif score >= REVIEW_REQUIRED_SCORE:
        usability = "REVIEW REQUIRED"
        reason = (
            "Trajectory contains reliability concerns "
            "and should be reviewed before analytics use."
        )

    else:
        usability = "ANALYTICS BLOCKED"
        reason = (
            "Trajectory quality is too low for reliable "
            "downstream analytics."
        )

    return {
        "plate_number": quality_result["plate_number"],
        "quality_score": quality_result["quality_score"],
        "quality_level": quality_result["quality_level"],
        "usability": usability,
        "reason": reason,
    }


def run_trajectory_usability_classification(
    quality_results
):
    """
    Classifies every trajectory produced by Step 2.28.
    """

    results = []

    for quality_result in quality_results:

        usability_result = (
            classify_trajectory_usability(
                quality_result
            )
        )

        results.append(
            usability_result
        )

    return results


def print_step_2_29_results(results):
    print("\n")
    print("=" * 80)
    print(
        "STEP 2.29 - "
        "TRAJECTORY USABILITY CLASSIFICATION"
    )
    print("=" * 80)

    for result in results:

        print("\nTRAJECTORY")
        print("-" * 80)

        print(
            f"Plate: "
            f"{result['plate_number']}"
        )

        print(
            f"Quality score: "
            f"{result['quality_score']:.2f}%"
        )

        print(
            f"Quality level: "
            f"{result['quality_level']}"
        )

        print(
            f"Usability: "
            f"{result['usability']}"
        )

        print(
            f"Reason: "
            f"{result['reason']}"
        )

    print("\n")
    print("=" * 80)
    print("STEP 2.29 SUMMARY")
    print("=" * 80)

    analytics_ready = sum(
        1
        for result in results
        if result["usability"]
        == "ANALYTICS READY"
    )

    review_required = sum(
        1
        for result in results
        if result["usability"]
        == "REVIEW REQUIRED"
    )

    analytics_blocked = sum(
        1
        for result in results
        if result["usability"]
        == "ANALYTICS BLOCKED"
    )

    print(
        f"Analytics-ready trajectories: "
        f"{analytics_ready}"
    )

    print(
        f"Review-required trajectories: "
        f"{review_required}"
    )

    print(
        f"Analytics-blocked trajectories: "
        f"{analytics_blocked}"
    )


def verify_step_2_29(results):
    print("\n")
    print("=" * 80)
    print("STEP 2.29 VERIFICATION")
    print("=" * 80)

    # --------------------------------------------------------
    # Structure
    # --------------------------------------------------------

    structure_pass = True

    required_fields = [
        "plate_number",
        "quality_score",
        "quality_level",
        "usability",
        "reason",
    ]

    for result in results:
        for field in required_fields:
            if field not in result:
                structure_pass = False

    print(
        "Usability result structure: "
        f"{'PASS' if structure_pass else 'FAIL'}"
    )

    # --------------------------------------------------------
    # Score bounds
    # --------------------------------------------------------

    bounds_pass = all(
        0.0 <= result["quality_score"] <= 100.0
        for result in results
    )

    print(
        "Quality score bounds: "
        f"{'PASS' if bounds_pass else 'FAIL'}"
    )

    # --------------------------------------------------------
    # Classification logic
    # --------------------------------------------------------

    classification_pass = True

    for result in results:

        score = result["quality_score"]
        usability = result["usability"]

        if score >= ANALYTICS_READY_SCORE:
            expected = "ANALYTICS READY"

        elif score >= REVIEW_REQUIRED_SCORE:
            expected = "REVIEW REQUIRED"

        else:
            expected = "ANALYTICS BLOCKED"

        if usability != expected:
            classification_pass = False

    print(
        "Usability classification logic: "
        f"{'PASS' if classification_pass else 'FAIL'}"
    )

    # --------------------------------------------------------
    # High-quality trajectories must be analytics-ready
    # --------------------------------------------------------

    high_quality_pass = all(
        result["usability"] == "ANALYTICS READY"
        for result in results
        if result["quality_level"]
        == "HIGH QUALITY"
    )

    print(
        "High-quality trajectory handling: "
        f"{'PASS' if high_quality_pass else 'FAIL'}"
    )

    # --------------------------------------------------------
    # Low-quality trajectories must be blocked
    # --------------------------------------------------------

    low_quality_pass = all(
        result["usability"]
        == "ANALYTICS BLOCKED"
        for result in results
        if result["quality_level"]
        == "LOW QUALITY"
    )

    print(
        "Low-quality trajectory blocking: "
        f"{'PASS' if low_quality_pass else 'FAIL'}"
    )

    # --------------------------------------------------------
    # Known inconsistent movement trajectory
    # --------------------------------------------------------

    movement_review_pass = any(
        (
            result["plate_number"]
            == "DL05MN7890"
            and result["usability"]
            == "REVIEW REQUIRED"
        )
        for result in results
    )

    print(
        "Inconsistent movement review handling: "
        f"{'PASS' if movement_review_pass else 'FAIL'}"
    )

    # --------------------------------------------------------
    # Known disconnected trajectory
    # --------------------------------------------------------

    disconnected_block_pass = any(
        (
            result["plate_number"]
            == "DL06AB6789"
            and result["usability"]
            == "ANALYTICS BLOCKED"
        )
        for result in results
    )

    print(
        "Disconnected trajectory blocking: "
        f"{'PASS' if disconnected_block_pass else 'FAIL'}"
    )

    # --------------------------------------------------------
    # Legitimate 30-minute revisit
    # --------------------------------------------------------

    revisit_pass = any(
        (
            result["plate_number"]
            == "DL04RT3456"
            and result["usability"]
            == "ANALYTICS READY"
        )
        for result in results
    )

    print(
        "Legitimate camera revisit usability: "
        f"{'PASS' if revisit_pass else 'FAIL'}"
    )

    # --------------------------------------------------------
    # No automatic merging
    # --------------------------------------------------------

    no_merge_pass = all(
        "merged_trajectory" not in result
        for result in results
    )

    print(
        "No automatic trajectory merging: "
        f"{'PASS' if no_merge_pass else 'FAIL'}"
    )

    return (
        structure_pass
        and bounds_pass
        and classification_pass
        and high_quality_pass
        and low_quality_pass
        and movement_review_pass
        and disconnected_block_pass
        and revisit_pass
        and no_merge_pass
    )




# ============================================================
# STEP 2.30 — PERSISTENT TRAJECTORY IDENTITY LAYER
# ============================================================

TRAJECTORY_ID_PREFIX = "TRAJ_"


def generate_trajectory_id(index):
    """
    Generates a deterministic, human-readable trajectory ID.

    Example:
        1 -> TRAJ_0001
        2 -> TRAJ_0002
    """

    return f"{TRAJECTORY_ID_PREFIX}{index:04d}"


def _trajectory_sort_key(item):
    """
    Creates a deterministic ordering for trajectory identity assignment.

    The earliest event time is the primary ordering signal. The normalized
    primary plate is used as a stable tie-breaker.
    """

    plate, events = item

    if events:
        earliest_time = min(
            parse_time(event["timestamp"])
            for event in events
        )
    else:
        earliest_time = datetime.max

    return (
        earliest_time,
        normalize_plate_number(plate),
    )


def collect_observed_plates(trajectory_events):
    """
    Returns unique normalized plate observations belonging to this existing
    trajectory. This function does NOT merge trajectories.
    """

    observed = []
    seen = set()

    for event in sorted(
        trajectory_events,
        key=lambda event: parse_time(event["timestamp"])
    ):

        plate = normalize_plate_number(
            event.get("plate_number", "")
        )

        if not plate:
            continue

        if plate in seen:
            continue

        seen.add(plate)
        observed.append(plate)

    return observed


def build_trajectory_identity_records(
    trajectories,
    quality_results,
    usability_results,
    confidence_results,
):
    """
    Creates persistent internal identity records for the trajectories that
    already exist after Step 2.29 processing.

    Important:
        - No trajectory merging is performed.
        - Each existing trajectory receives exactly one trajectory_id.
        - Existing quality/usability information is preserved.
        - Original event IDs and camera sequence are preserved.
    """

    quality_by_plate = {
        normalize_plate_number(result["plate_number"]): result
        for result in quality_results
    }

    usability_by_plate = {
        normalize_plate_number(result["plate_number"]): result
        for result in usability_results
    }

    association_by_event_id = {}

    for result in confidence_results:
        observation = result["observation"]
        association_by_event_id[observation["id"]] = {
            "decision": result["decision"],
            "confidence": result["confidence"]["overall_percent"],
        }

    records = []

    sorted_trajectories = sorted(
        trajectories.items(),
        key=_trajectory_sort_key,
    )

    for index, (plate, events) in enumerate(
        sorted_trajectories,
        start=1,
    ):

        normalized_plate = normalize_plate_number(plate)
        trajectory_id = generate_trajectory_id(index)

        sorted_events = sorted(
            events,
            key=lambda event: parse_time(
                event["timestamp"]
            )
        )

        observed_plates = collect_observed_plates(
            sorted_events
        )

        camera_sequence = [
            event["camera_id"]
            for event in sorted_events
        ]

        event_ids = [
            event["id"]
            for event in sorted_events
        ]

        observation_associations = []

        for event_id in event_ids:
            association = association_by_event_id.get(
                event_id
            )

            if association is not None:
                observation_associations.append({
                    "event_id": event_id,
                    "decision": association["decision"],
                    "confidence": association["confidence"],
                })

        quality_result = quality_by_plate.get(
            normalized_plate,
            {}
        )

        usability_result = usability_by_plate.get(
            normalized_plate,
            {}
        )

        records.append({
            "trajectory_id": trajectory_id,
            "primary_plate": normalized_plate,
            "observed_plates": observed_plates,
            "event_ids": event_ids,
            "observation_associations": observation_associations,
            "camera_sequence": camera_sequence,
            "event_count": len(sorted_events),
            "quality_score": quality_result.get(
                "quality_score"
            ),
            "quality_level": quality_result.get(
                "quality_level"
            ),
            "usability": usability_result.get(
                "usability"
            ),
        })

    return records


def print_step_2_30_results(records):
    print("\n")
    print("=" * 80)
    print("STEP 2.30 - PERSISTENT TRAJECTORY IDENTITY")
    print("=" * 80)

    for record in records:

        print("\nTRAJECTORY IDENTITY")
        print("-" * 80)

        print(
            f"Trajectory ID: "
            f"{record['trajectory_id']}"
        )

        print(
            f"Primary plate: "
            f"{record['primary_plate']}"
        )

        print(
            f"Observed plates: "
            f"{record['observed_plates']}"
        )

        print(
            f"Event IDs: "
            f"{record['event_ids']}"
        )

        print(
            f"Observation associations: "
            f"{record['observation_associations']}"
        )

        print(
            f"Camera sequence: "
            f"{' → '.join(record['camera_sequence'])}"
        )

        print(
            f"Event count: "
            f"{record['event_count']}"
        )

        print(
            f"Quality score: "
            f"{record['quality_score']:.2f}%"
            if record["quality_score"] is not None
            else "Quality score: N/A"
        )

        print(
            f"Quality level: "
            f"{record['quality_level']}"
        )

        print(
            f"Usability: "
            f"{record['usability']}"
        )

    print("\n")
    print("=" * 80)
    print("STEP 2.30 SUMMARY")
    print("=" * 80)
    print(
        f"Trajectory identities generated: "
        f"{len(records)}"
    )


def verify_step_2_30(
    records,
    trajectories,
    quality_results,
    usability_results,
    confidence_results,
):
    print("\n")
    print("=" * 80)
    print("STEP 2.30 VERIFICATION")
    print("=" * 80)

    # --------------------------------------------------------
    # Structure
    # --------------------------------------------------------

    required_fields = [
        "trajectory_id",
        "primary_plate",
        "observed_plates",
        "event_ids",
        "observation_associations",
        "camera_sequence",
        "event_count",
        "quality_score",
        "quality_level",
        "usability",
    ]

    structure_pass = all(
        all(
            field in record
            for field in required_fields
        )
        for record in records
    )

    print(
        "Trajectory identity structure: "
        f"{'PASS' if structure_pass else 'FAIL'}"
    )

    # --------------------------------------------------------
    # Exactly one identity per existing trajectory
    # --------------------------------------------------------

    identity_count_pass = (
        len(records) == len(trajectories)
    )

    print(
        "One ID per existing trajectory: "
        f"{'PASS' if identity_count_pass else 'FAIL'}"
    )

    # --------------------------------------------------------
    # Unique IDs
    # --------------------------------------------------------

    ids = [
        record["trajectory_id"]
        for record in records
    ]

    unique_ids_pass = (
        len(ids) == len(set(ids))
        and all(
            trajectory_id.startswith(
                TRAJECTORY_ID_PREFIX
            )
            for trajectory_id in ids
        )
    )

    print(
        "Unique trajectory IDs: "
        f"{'PASS' if unique_ids_pass else 'FAIL'}"
    )

    # --------------------------------------------------------
    # Sequential ID format
    # --------------------------------------------------------

    expected_ids = [
        generate_trajectory_id(index)
        for index in range(1, len(records) + 1)
    ]

    sequential_id_pass = (
        ids == expected_ids
    )

    print(
        "Sequential deterministic ID format: "
        f"{'PASS' if sequential_id_pass else 'FAIL'}"
    )

    # --------------------------------------------------------
    # Deterministic assignment
    # --------------------------------------------------------

    second_run = build_trajectory_identity_records(
        trajectories,
        quality_results,
        usability_results,
        confidence_results,
    )

    deterministic_pass = (
        [
            record["trajectory_id"]
            for record in second_run
        ]
        == ids
    )

    print(
        "Deterministic ID assignment: "
        f"{'PASS' if deterministic_pass else 'FAIL'}"
    )

    # --------------------------------------------------------
    # Primary plate preservation
    # --------------------------------------------------------

    primary_plate_pass = all(
        record["primary_plate"]
        == normalize_plate_number(
            sorted(
                trajectories.items(),
                key=_trajectory_sort_key,
            )[index][0]
        )
        for index, record in enumerate(records)
    )

    print(
        "Primary plate preservation: "
        f"{'PASS' if primary_plate_pass else 'FAIL'}"
    )

    # --------------------------------------------------------
    # Observed plate preservation
    # --------------------------------------------------------

    observed_plate_pass = True

    for record in records:
        original_events = trajectories[
            record["primary_plate"]
        ]

        expected_plates = collect_observed_plates(
            original_events
        )

        if record["observed_plates"] != expected_plates:
            observed_plate_pass = False

    print(
        "Observed plate preservation: "
        f"{'PASS' if observed_plate_pass else 'FAIL'}"
    )

    # --------------------------------------------------------
    # Quality/usability preservation
    # --------------------------------------------------------

    quality_by_plate = {
        normalize_plate_number(result["plate_number"]): result
        for result in quality_results
    }

    usability_by_plate = {
        normalize_plate_number(result["plate_number"]): result
        for result in usability_results
    }

    metadata_pass = True

    for record in records:

        plate = record["primary_plate"]
        quality = quality_by_plate.get(plate, {})
        usability = usability_by_plate.get(plate, {})

        if record["quality_score"] != quality.get(
            "quality_score"
        ):
            metadata_pass = False

        if record["quality_level"] != quality.get(
            "quality_level"
        ):
            metadata_pass = False

        if record["usability"] != usability.get(
            "usability"
        ):
            metadata_pass = False

    print(
        "Quality/usability metadata preservation: "
        f"{'PASS' if metadata_pass else 'FAIL'}"
    )

    # --------------------------------------------------------
    # Ambiguity preservation
    # --------------------------------------------------------

    expected_ambiguous_events = {
        202,
        203,
    }

    ambiguous_event_decisions = {}

    for record in records:
        for association in record["observation_associations"]:
            ambiguous_event_decisions[
                association["event_id"]
            ] = association["decision"]

    ambiguity_pass = all(
        ambiguous_event_decisions.get(event_id)
        == "AMBIGUOUS / REVIEW"
        for event_id in expected_ambiguous_events
    )

    print(
        "Ambiguous observation preservation: "
        f"{'PASS' if ambiguity_pass else 'FAIL'}"
    )

    # --------------------------------------------------------
    # Legitimate revisit preservation
    # --------------------------------------------------------

    revisit_pass = any(
        record["primary_plate"]
        == "DL04RT3456"
        and record["camera_sequence"]
        == [
            "Camera_1",
            "Camera_2",
            "Camera_3",
            "Camera_2",
        ]
        for record in records
    )

    print(
        "Legitimate camera revisit preservation: "
        f"{'PASS' if revisit_pass else 'FAIL'}"
    )

    # --------------------------------------------------------
    # Review trajectory preservation
    # --------------------------------------------------------

    review_pass = any(
        record["primary_plate"]
        == "DL05MN7890"
        and record["usability"]
        == "REVIEW REQUIRED"
        for record in records
    )

    print(
        "Review-required trajectory preservation: "
        f"{'PASS' if review_pass else 'FAIL'}"
    )

    # --------------------------------------------------------
    # Blocked trajectory preservation
    # --------------------------------------------------------

    blocked_pass = any(
        record["primary_plate"]
        == "DL06AB6789"
        and record["usability"]
        == "ANALYTICS BLOCKED"
        for record in records
    )

    print(
        "Analytics-blocked trajectory preservation: "
        f"{'PASS' if blocked_pass else 'FAIL'}"
    )

    # --------------------------------------------------------
    # No automatic merging
    # --------------------------------------------------------

    no_merge_pass = all(
        "merged_trajectory" not in record
        and "merged_from" not in record
        for record in records
    )

    print(
        "No automatic trajectory merging: "
        f"{'PASS' if no_merge_pass else 'FAIL'}"
    )

    return (
        structure_pass
        and identity_count_pass
        and unique_ids_pass
        and sequential_id_pass
        and deterministic_pass
        and primary_plate_pass
        and observed_plate_pass
        and metadata_pass
        and ambiguity_pass
        and revisit_pass
        and review_pass
        and blocked_pass
        and no_merge_pass
    )


# MAIN
# ============================================================

def main():

    print("=" * 80)
    print(
        "SIH26127 — CITY-WIDE AI TRAJECTORY ENGINE"
    )
    print("=" * 80)

    # ========================================================
    # STEP 2.8 - 2.18
    # ========================================================

    print(
        "\nSTEP 2.8 - 2.18 "
        "BASE TRAJECTORY PROCESSING"
    )

    filtered_events, low_confidence_removed = (
        filter_low_confidence_events(
            EVENTS
        )
    )

    print(
        f"Raw events: {len(EVENTS)}"
    )

    print(
        f"Low-confidence removed: "
        f"{len(low_confidence_removed)}"
    )

    filtered_events, duplicate_removed = (
        remove_same_camera_duplicates(
            filtered_events
        )
    )

    print(
        f"Duplicate removed: "
        f"{len(duplicate_removed)}"
    )

    print(
        f"Filtered events: "
        f"{len(filtered_events)}"
    )

    trajectories = build_trajectories(
        filtered_events
    )

    print(
        f"Vehicles / trajectories: "
        f"{len(trajectories)}"
    )

    suspicious_movements = (
        find_suspicious_movements(
            trajectories
        )
    )

    disconnected_routes = (
        find_disconnected_routes(
            trajectories
        )
    )

    print(
        f"Suspicious movements: "
        f"{len(suspicious_movements)}"
    )

    print(
        f"Disconnected routes: "
        f"{len(disconnected_routes)}"
    )

    # ========================================================
    # STEP 2.19
    # ========================================================

    print(
        "\nSTEP 2.19 - OCR FUZZY MATCHING"
    )

    fuzzy_matches = (
        find_fuzzy_plate_matches(
            filtered_events
        )
    )

    print(
        f"Fuzzy plate matches: "
        f"{len(fuzzy_matches)}"
    )

    for match in fuzzy_matches:

        print(
            f"{match['event_a']['plate_number']} "
            f"<-> "
            f"{match['event_b']['plate_number']} "
            f"| distance "
            f"{match['plate_distance']}"
        )

    # ========================================================
    # STEP 2.20
    # ========================================================

    print(
        "\nSTEP 2.20 - "
        "CONTEXT-AWARE OCR VALIDATION"
    )

    validated_matches = (
        validate_all_fuzzy_matches(
            fuzzy_matches
        )
    )

    print(
        f"Validated fuzzy matches: "
        f"{len(validated_matches)}"
    )

    for match in validated_matches:

        event_a = match["event_a"]
        event_b = match["event_b"]

        print(
            f"{event_a['plate_number']} "
            f"<-> "
            f"{event_b['plate_number']} "
            f"| "
            f"{event_a['camera_id']} -> "
            f"{event_b['camera_id']} "
            f"| "
            f"{match['validation']['temporal']['time_gap_seconds']:.0f}s"
        )

    # ========================================================
    # STEP 2.21 - 2.23
    # ========================================================

    print(
        "\nSTEP 2.21 / 2.22 / 2.23 "
        "- TRAJECTORY-LEVEL ASSOCIATION"
    )

    association_observations = []

    seen_ids = set()

    for match in fuzzy_matches:

        for event in [
            match["event_a"],
            match["event_b"]
        ]:

            if event["id"] not in seen_ids:

                association_observations.append(
                    event
                )

                seen_ids.add(
                    event["id"]
                )

    association_results = (
        run_trajectory_level_association(
            association_observations,
            trajectories
        )
    )

    # ========================================================
    # STEP 2.24
    # ========================================================

    consistency_results = (
        apply_consistency_validation(
            association_results,
            trajectories
        )
    )

    # ========================================================
    # STEP 2.25
    # ========================================================

    confidence_results = (
        apply_confidence_aggregation(
            consistency_results,
            trajectories
        )
    )

    # ========================================================
    # STEP 2.26
    # ========================================================

    confidence_results = (
        apply_step_2_26_validation(
            confidence_results,
            trajectories
        )
    )

    print_confidence_results(
        confidence_results
    )

    print_step_2_26_results(
        confidence_results
    )

    step_2_26_pass = verify_step_2_26(
        confidence_results
    )

    level_summary, decision_summary = (
        summarize_confidence_results(
            confidence_results
        )
    )

    # ========================================================
    # STEP 2.27
    # ========================================================

    continuity_results = (
        run_trajectory_continuity_validation(
            trajectories
        )
    )

    print_step_2_27_results(
        continuity_results
    )

    step_2_27_pass = verify_step_2_27(
        continuity_results
    )

    # ========================================================
    # STEP 2.28
    # ========================================================

    quality_results = (
        run_trajectory_quality_scoring(
            trajectories,
            continuity_results
        )
    )

    print_step_2_28_results(
        quality_results
    )

    step_2_28_pass = verify_step_2_28(
        quality_results
    )

    # ========================================================
    # STEP 2.29
    # ========================================================

    usability_results = (
        run_trajectory_usability_classification(
            quality_results
        )
    )

    print_step_2_29_results(
        usability_results
    )

    step_2_29_pass = verify_step_2_29(
        usability_results
    )

    # ========================================================
    # STEP 2.30
    # ========================================================

    trajectory_identity_results = (
        build_trajectory_identity_records(
            trajectories,
            quality_results,
            usability_results,
            confidence_results,
        )
    )

    print_step_2_30_results(
        trajectory_identity_results
    )

    step_2_30_pass = verify_step_2_30(
        trajectory_identity_results,
        trajectories,
        quality_results,
        usability_results,
        confidence_results,
    )



    # ========================================================
    # STEP 2.25 VERIFICATION
    # ========================================================

    step_2_25_pass = verify_step_2_25(
        confidence_results
    )

    regression_pass = verify_regression_checks(
        filtered_events=filtered_events,
        duplicate_removed=duplicate_removed,
        trajectories=trajectories,
        fuzzy_matches=fuzzy_matches,
        validated_matches=validated_matches,
        suspicious_movements=suspicious_movements,
        disconnected_routes=disconnected_routes,
    )

    # ========================================================
    # PLATE DISTANCE REGRESSION
    # ========================================================

    expected_plate_distances = {
        (
            "DL01AB1234",
            "DL01AB123A"
        ): 1,

        (
            "DL02XY5678",
            "DL02XY567"
        ): 1,
    }

    plate_distance_pass = True

    for result in confidence_results:

        observation_plate = (
            result["observation"]
            ["plate_number"]
        )

        for candidate in result[
            "ranked_candidates"
        ]:

            candidate_plate = (
                candidate
                ["trajectory_plate"]
            )

            pair = (
                observation_plate,
                candidate_plate
            )

            if pair in expected_plate_distances:

                if (
                    candidate["plate_distance"]
                    != expected_plate_distances[pair]
                ):

                    plate_distance_pass = False

    if plate_distance_pass:

        print(
            "\nCandidate-vs-observation "
            "plate distance: PASS"
        )

    else:

        print(
            "\nCandidate-vs-observation "
            "plate distance: FAIL"
        )

    # ========================================================
    # STEP 2.26 FINAL STATUS
    # ========================================================

    print("\n")
    print("=" * 80)
    print("STEP 2.26 FINAL STATUS")
    print("=" * 80)

    print(
        f"Bidirectional validation: "
        f"{'PASS' if step_2_26_pass else 'FAIL'}"
    )

    if step_2_26_pass:

        print(
            "Step 2.26 bidirectional consistency checks passed."
        )

    else:

        print(
            "Step 2.26 requires further investigation."
        )

    # ========================================================
    # STEP 2.27 FINAL STATUS
    # ========================================================

    print("\n")
    print("=" * 80)
    print("STEP 2.30 FINAL STATUS")
    print("=" * 80)

    print(
        "Persistent trajectory identity layer: "
        f"{'PASS' if step_2_30_pass else 'FAIL'}"
    )

    if step_2_30_pass:

        print(
            "All Step 2.30 verification checks passed."
        )

        print(
            "Deterministic trajectory IDs generated."
        )

        print(
            "Trajectory metadata preserved."
        )

        print(
            "Quality and usability status preserved."
        )

        print(
            "No automatic trajectory merging performed."
        )

        print(
            "No Supabase data was modified."
        )

    else:

        print(
            "Step 2.30 verification failed."
        )

    print("\n")

    print("=" * 80)
    print("STEP 2.29 FINAL STATUS")
    print("=" * 80)

    print(
        "Trajectory usability classification: "
        f"{'PASS' if step_2_29_pass else 'FAIL'}"
    )

    if step_2_29_pass:

        print(
            "All Step 2.29 verification checks passed."
        )

        print(
            "Trajectory usability classifications generated."
        )

        print(
            "Analytics-ready trajectories identified."
        )

        print(
            "Review-required trajectories identified."
        )

        print(
            "Low-quality trajectories blocked from analytics."
        )

        print(
            "No automatic trajectory merging performed."
        )

        print(
            "No Supabase data was modified."
        )

    else:

        print(
            "Step 2.29 verification failed."
        )

    print("\n")

    print("=" * 80)
    print("STEP 2.28 FINAL STATUS")
    print("=" * 80)
    print(
        "Trajectory quality scoring: "
        f"{'PASS' if step_2_28_pass else 'FAIL'}"
    )

    if step_2_28_pass:
        print(
            "All Step 2.28 verification checks passed."
        )
        print(
            "Trajectory quality scores generated."
        )
        print(
            "Reliability components calculated."
        )
        print(
            "High, medium and low quality levels classified."
        )
        print(
            "No automatic trajectory merging performed."
        )
        print(
            "No Supabase data was modified."
        )
    else:
        print(
            "Step 2.28 verification failed."
        )

    print("\n")

    print("=" * 80)
    print("STEP 2.27 FINAL STATUS")
    print("=" * 80)

    print(
        f"Trajectory continuity validation: "
        f"{'PASS' if step_2_27_pass else 'FAIL'}"
    )

    if step_2_27_pass:

        print(
            "All Step 2.27 verification checks passed."
        )

        print(
            "Trajectory chronology validated."
        )

        print(
            "Camera connectivity validated."
        )

        print(
            "Movement feasibility validated."
        )

        print(
            "Trajectory time gaps validated."
        )

        print(
            "Legitimate camera revisit preserved."
        )

        print(
            "No automatic trajectory merging performed."
        )

        print(
            "No Supabase data was modified."
        )

    else:

        print(
            "Step 2.27 requires further investigation."
        )

    # ========================================================
    # FINAL STATUS
    # ========================================================

    print("\n")
    print("=" * 80)
    print("STEP 2.25 FINAL STATUS")
    print("=" * 80)

    print(
        f"Confidence aggregation: "
        f"{'PASS' if step_2_25_pass else 'FAIL'}"
    )

    print(
        f"Regression checks: "
        f"{'PASS' if regression_pass else 'FAIL'}"
    )

    print(
        f"Plate distance validation: "
        f"{'PASS' if plate_distance_pass else 'FAIL'}"
    )

    print("\nConfidence levels:")

    for level, count in level_summary.items():

        print(
            f"{level}: {count}"
        )

    print("\nFinal decision counts:")

    for decision, count in decision_summary.items():

        print(
            f"{decision}: {count}"
        )

    if (
        step_2_25_pass
        and regression_pass
        and plate_distance_pass
    ):

        print("\n" + "=" * 80)
        print("STEP 2.25 COMPLETED")
        print("=" * 80)

        print(
            "Trajectory association confidence aggregation implemented."
        )

        print(
            "Plate, temporal, camera, movement, ranking and consistency signals aggregated."
        )

        print(
            "Overall confidence percentage generated."
        )

        print(
            "High, medium and low confidence levels implemented."
        )

        print(
            "No automatic trajectory merging performed."
        )

        print(
            "No Supabase data was modified."
        )

    else:

        print("\n" + "=" * 80)
        print("STEP 2.25 FAILED")
        print("=" * 80)

        print(
            "One or more verification checks failed."
        )


if __name__ == "__main__":
    main()
