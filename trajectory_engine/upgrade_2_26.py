from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
TRAJECTORY_FILE = PROJECT_DIR / "trajectory.py"
BACKUP_FILE = PROJECT_DIR / "trajectory_step_2_25_backup.py"


STEP_2_26_CODE = r'''

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
'''


def main():

    if not TRAJECTORY_FILE.exists():

        print(
            "ERROR: trajectory.py was not found."
        )

        print(
            f"Expected location: {TRAJECTORY_FILE}"
        )

        return

    # --------------------------------------------------------
    # Create backup
    # --------------------------------------------------------

    original = TRAJECTORY_FILE.read_text(
        encoding="utf-8"
    )

    if not BACKUP_FILE.exists():

        BACKUP_FILE.write_text(
            original,
            encoding="utf-8"
        )

        print(
            "Created backup:"
        )

        print(
            BACKUP_FILE.name
        )

    # --------------------------------------------------------
    # Prevent duplicate upgrade
    # --------------------------------------------------------

    if (
        "STEP 2.26 — BIDIRECTIONAL"
        in original
    ):

        print(
            "Step 2.26 already exists in trajectory.py."
        )

        return

    # --------------------------------------------------------
    # Insert functions before MAIN
    # --------------------------------------------------------

    marker = "\n# ============================================================\n# MAIN\n# ============================================================\n"

    if marker not in original:

        print(
            "ERROR: MAIN section marker was not found."
        )

        print(
            "No changes were made."
        )

        return

    upgraded = original.replace(
        marker,
        STEP_2_26_CODE
        + marker,
        1
    )

    # --------------------------------------------------------
    # Modify main pipeline
    # --------------------------------------------------------

    old_pipeline = '''    confidence_results = (
        apply_confidence_aggregation(
            consistency_results,
            trajectories
        )
    )

    print_confidence_results(
        confidence_results
    )
'''

    new_pipeline = '''    confidence_results = (
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
'''

    if old_pipeline not in upgraded:

        print(
            "ERROR: Step 2.25 pipeline section was not found."
        )

        print(
            "No changes were made."
        )

        return

    upgraded = upgraded.replace(
        old_pipeline,
        new_pipeline,
        1
    )

    # --------------------------------------------------------
    # Add Step 2.26 final status before final status section
    # --------------------------------------------------------

    final_status_marker = '''    # ========================================================
    # FINAL STATUS
    # ========================================================
'''

    replacement = '''    # ========================================================
    # STEP 2.26 FINAL STATUS
    # ========================================================

    print("\\n")
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

''' + final_status_marker

    if final_status_marker not in upgraded:

        print(
            "ERROR: Final status section was not found."
        )

        print(
            "No changes were made."
        )

        return

    upgraded = upgraded.replace(
        final_status_marker,
        replacement,
        1
    )

    # --------------------------------------------------------
    # Write upgraded file
    # --------------------------------------------------------

    TRAJECTORY_FILE.write_text(
        upgraded,
        encoding="utf-8"
    )

    print()
    print("=" * 80)
    print("STEP 2.26 UPGRADE COMPLETE")
    print("=" * 80)

    print(
        "trajectory.py updated successfully."
    )

    print(
        f"Backup preserved as: {BACKUP_FILE.name}"
    )

    print()
    print(
        "Now run:"
    )

    print(
        "python trajectory.py"
    )


if __name__ == "__main__":
    main()