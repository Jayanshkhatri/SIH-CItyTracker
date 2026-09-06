from pathlib import Path
import shutil

# ============================================================
# SIH26127 — STEP 2.29 AUTOMATIC UPGRADE
# Trajectory Usability Classification
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
TRAJECTORY_FILE = BASE_DIR / "trajectory.py"
BACKUP_FILE = BASE_DIR / "trajectory_step_2_28_backup.py"

STEP_2_29_MARKER = (
    "# STEP 2.29 — TRAJECTORY USABILITY CLASSIFICATION"
)

# ------------------------------------------------------------
# STEP 2.29 CODE
# ------------------------------------------------------------

STEP_2_29_CODE = r'''
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
'''


def main():

    print("=" * 80)
    print("SIH26127 — STEP 2.29 UPGRADE")
    print("=" * 80)

    if not TRAJECTORY_FILE.exists():
        print("ERROR: trajectory.py not found.")
        return

    # --------------------------------------------------------
    # Safety backup
    # --------------------------------------------------------

    print("\nCreating Step 2.28 backup...")

    shutil.copy2(
        TRAJECTORY_FILE,
        BACKUP_FILE
    )

    print(
        f"Backup created: "
        f"{BACKUP_FILE.name}"
    )

    # --------------------------------------------------------
    # Read current file
    # --------------------------------------------------------

    source = TRAJECTORY_FILE.read_text(
        encoding="utf-8"
    )

    if STEP_2_29_MARKER in source:
        print(
            "\nStep 2.29 already exists."
        )
        print(
            "No changes made."
        )
        return

    # --------------------------------------------------------
    # Insert Step 2.29 before MAIN
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
        STEP_2_29_CODE
        + "\n\n"
        + main_marker,
        1
    )

    # --------------------------------------------------------
    # Add Step 2.29 execution
    # --------------------------------------------------------

    step_2_28_execution = '''step_2_28_pass = verify_step_2_28(
        quality_results
    )'''

    step_2_29_execution = '''

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
'''

    if step_2_28_execution not in source:
        print(
            "\nERROR: Step 2.28 execution block not found."
        )
        print(
            "Backup remains available."
        )
        return

    source = source.replace(
        step_2_28_execution,
        step_2_28_execution
        + step_2_29_execution,
        1
    )

    # --------------------------------------------------------
    # Add final status
    # --------------------------------------------------------

    final_marker = '''    print("=" * 80)
    print("STEP 2.28 FINAL STATUS")'''

    final_status = '''    print("=" * 80)
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

    print("\\n")

'''

    if final_marker not in source:
        print(
            "\nERROR: Step 2.28 final status marker not found."
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
    # Write file
    # --------------------------------------------------------

    TRAJECTORY_FILE.write_text(
        source,
        encoding="utf-8"
    )

    print("\nStep 2.29 successfully added.")
    print(
        "Existing Step 2.8 - 2.28 logic preserved."
    )
    print(
        "Supabase code/data was not changed."
    )

    print("\nNext command:")
    print("python trajectory.py")


if __name__ == "__main__":
    main()