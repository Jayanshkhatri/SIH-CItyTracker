from database import get_connection


def test_read_events_with_coordinates():
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                plate_events.id,
                plate_events.plate_number,
                plate_events.camera_id,
                cameras.name,
                ST_Y(cameras.location::geometry) AS latitude,
                ST_X(cameras.location::geometry) AS longitude,
                plate_events.event_time,
                plate_events.confidence
            FROM plate_events
            JOIN cameras
                ON plate_events.camera_id = cameras.id
            LIMIT 10;
        """)

        rows = cursor.fetchall()

        events = []

        for row in rows:
            event = {
                "id": row[0],
                "plate_number": row[1],
                "camera_id": row[2],
                "camera_name": row[3],
                "latitude": row[4],
                "longitude": row[5],
                "event_time": row[6],
                "confidence": row[7]
            }

            events.append(event)

        print("\nClean Event Data:")
        print("-" * 80)

        for event in events:
            print(event)

        print("-" * 80)
        print(f"Total events: {len(events)}")

        cursor.close()

    finally:
        connection.close()


if __name__ == "__main__":
    test_read_events_with_coordinates()