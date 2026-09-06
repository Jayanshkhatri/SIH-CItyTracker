from pathlib import Path
import shutil

# ============================================================
# SIH26127 — STEP 2.28 AUTOMATIC UPGRADE
# Trajectory Quality & Reliability Scoring
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
TRAJECTORY_FILE = BASE_DIR / "trajectory.py"
BACKUP_FILE = BASE_DIR / "trajectory_step_2_27_backup.py"

STEP_2_28_MARKER = "# STEP 2.28 — TRAJECTORY QUALITY & RELIABILITY SCORING"

# ------------------------------------------------------------
# STEP 2.28 CODE
# ------------------------------------------------------------

STEP_2_28_CODE = r'''
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
'''


def main():
    print("=" * 80)
    print("SIH26127 — STEP 2.28 UPGRADE")
    print("=" * 80)

    if not TRAJECTORY_FILE.exists():
        print("ERROR: trajectory.py not found.")
        return

    # --------------------------------------------------------
    # Safety backup
    # --------------------------------------------------------

    print("\nCreating Step 2.27 backup...")

    shutil.copy2(
        TRAJECTORY_FILE,
        BACKUP_FILE
    )

    print(
        f"Backup created: "
        f"{BACKUP_FILE.name}"
    )

    # --------------------------------------------------------
    # Read current trajectory.py
    # --------------------------------------------------------

    source = TRAJECTORY_FILE.read_text(
        encoding="utf-8"
    )

    if STEP_2_28_MARKER in source:
        print(
            "\nStep 2.28 already exists."
        )
        print(
            "No changes made."
        )
        return

    # --------------------------------------------------------
    # Insert Step 2.28 before MAIN
    # --------------------------------------------------------

    main_marker = "# MAIN"

    if main_marker not in source:
        print(
            "\nERROR: MAIN marker not found."
        )
        print(
            "Backup remains available."
        )
        return

    source = source.replace(
        main_marker,
        STEP_2_28_CODE
        + "\n\n"
        + main_marker,
        1
    )

    # --------------------------------------------------------
    # Add Step 2.28 execution inside main()
    # --------------------------------------------------------

    step_2_27_execution = '''step_2_27_pass = verify_step_2_27(
        continuity_results
    )'''

    step_2_28_execution = '''

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
'''

    if step_2_27_execution not in source:
        print(
            "\nERROR: Step 2.27 execution block not found."
        )
        print(
            "Backup remains available."
        )
        return

    source = source.replace(
        step_2_27_execution,
        step_2_27_execution
        + step_2_28_execution,
        1
    )

    # --------------------------------------------------------
    # Add final status before existing Step 2.27 final status
    # --------------------------------------------------------

    final_marker = '''    print("=" * 80)
    print("STEP 2.27 FINAL STATUS")'''

    final_status = '''    print("=" * 80)
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

    print("\\n")

'''

    if final_marker not in source:
        print(
            "\nERROR: Step 2.27 final status marker not found."
        )
        print(
            "Backup remains available."
        )
        return

    source = source.replace(
        final_marker,
        final_status + final_marker,
        1
    )

    # --------------------------------------------------------
    # Write updated file
    # --------------------------------------------------------

    TRAJECTORY_FILE.write_text(
        source,
        encoding="utf-8"
    )

    print("\nStep 2.28 successfully added.")
    print(
        "Existing Step 2.8 - 2.27 logic preserved."
    )
    print(
        "Supabase code/data was not changed."
    )

    print("\nNext command:")
    print("python trajectory.py")


if __name__ == "__main__":
    main()