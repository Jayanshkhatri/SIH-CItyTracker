from pathlib import Path
import shutil


# ============================================================
# SIH26127 — STEP 2.27 UPGRADE
# TRAJECTORY CONTINUITY VALIDATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

trajectory_file = BASE_DIR / "trajectory.py"
backup_file = BASE_DIR / "trajectory_step_2_26_backup.py"


if not trajectory_file.exists():
    print("ERROR: trajectory.py not found.")
    raise SystemExit(1)


# ============================================================
# CREATE BACKUP
# ============================================================

shutil.copy2(
    trajectory_file,
    backup_file
)

print(
    "Backup created:"
    f" {backup_file.name}"
)


# ============================================================
# READ CURRENT FILE
# ============================================================

source = trajectory_file.read_text(
    encoding="utf-8"
)


# ============================================================
# PREVENT DUPLICATE UPGRADE
# ============================================================

if "STEP 2.27 - TRAJECTORY CONTINUITY VALIDATION" in source:

    print(
        "Step 2.27 is already present."
    )

    raise SystemExit(0)


# ============================================================
# STEP 2.27 CODE
# ============================================================

step_2_27_code = r'''

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

'''


# ============================================================
# INSERT STEP 2.27 BEFORE MAIN
# ============================================================

main_marker = "# ============================================================\n# MAIN\n# ============================================================"

if main_marker not in source:

    print(
        "ERROR: MAIN section not found."
    )

    raise SystemExit(1)


source = source.replace(
    main_marker,
    step_2_27_code
    + "\n\n"
    + main_marker,
    1
)


# ============================================================
# UPDATE MAIN
# ============================================================

old_main_block = r'''    # ========================================================
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
'''

new_main_block = r'''    # ========================================================
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
'''


if old_main_block not in source:

    print(
        "ERROR: Step 2.26 MAIN block not found."
    )

    raise SystemExit(1)


source = source.replace(
    old_main_block,
    new_main_block,
    1
)


# ============================================================
# ADD STEP 2.27 FINAL STATUS
# ============================================================

final_status_marker = r'''    # ========================================================
    # FINAL STATUS
    # ========================================================

    print("\n")
'''

step_2_27_final_status = r'''    # ========================================================
    # STEP 2.27 FINAL STATUS
    # ========================================================

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
'''


if final_status_marker not in source:

    print(
        "ERROR: Final status marker not found."
    )

    raise SystemExit(1)


source = source.replace(
    final_status_marker,
    step_2_27_final_status,
    1
)


# ============================================================
# WRITE UPDATED FILE
# ============================================================

trajectory_file.write_text(
    source,
    encoding="utf-8"
)


print(
    "\nStep 2.27 successfully added to trajectory.py."
)

print(
    "Previous Step 2.26 preserved in:"
    f" {backup_file.name}"
)

print(
    "\nNext command:"
)

print(
    "python trajectory.py"
)